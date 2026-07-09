#!/usr/bin/env python3
"""Paperless-Vector-Indexer (One-Shot).

Wird als Webhook / Post-consumption-Script von Paperless-ngx gestartet.
Ruft alle Dokumente ab, indexiert neue/geaenderte Dokumente in Qdrant
und beendet sich anschliessend. Kein Polling-Loop, keine State-Dateien.
"""

import hashlib
import logging
import os
import sys
import uuid

import requests
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

# ---------------------------------------------------------------------------
# Konfiguration (ausschliesslich ueber Umgebungsvariablen)
# ---------------------------------------------------------------------------
PAPERLESS_URL = os.environ.get("PAPERLESS_URL", "http://paperless:8000").rstrip("/")
PAPERLESS_TOKEN = os.environ.get("PAPERLESS_TOKEN", "")

EMBEDDING_URL = os.environ.get("EMBEDDING_URL", "http://embedding:8080/v1/embeddings")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "")
VECTOR_SIZE = int(os.environ.get("VECTOR_SIZE", "1024"))

QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant:6333").rstrip("/")
QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", "paperless")

CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "150"))

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

# Fester Namespace fuer deterministische Point-IDs (uuid5).
UUID_NAMESPACE = uuid.UUID("6f9b1d2e-3c4a-5b6c-7d8e-9f0a1b2c3d4e")

# HTTP-Timeouts (Sekunden)
HTTP_TIMEOUT = 60

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("indexer")


# ---------------------------------------------------------------------------
# Paperless-ngx REST API
# ---------------------------------------------------------------------------
def paperless_headers():
    """Authorization-Header fuer die Paperless-API."""
    return {"Authorization": f"Token {PAPERLESS_TOKEN}"}


def fetch_all_documents():
    """Alle Dokumente paginiert abrufen (page_size=100).

    Liefert eine Liste von Dokument-Objekten (Roh-JSON von Paperless).
    """
    documents = []
    page = 1
    while True:
        url = f"{PAPERLESS_URL}/api/documents/?page_size=100&page={page}"
        log.debug("Rufe Dokumentenseite ab: %s", url)
        resp = requests.get(url, headers=paperless_headers(), timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        documents.extend(results)
        log.debug("Seite %d: %d Dokumente", page, len(results))
        if not data.get("next"):
            break
        page += 1
    log.info("Insgesamt %d Dokumente von Paperless abgerufen", len(documents))
    return documents


def fetch_document_content(doc_id):
    """Volltext eines einzelnen Dokuments laden (Feld `content`)."""
    url = f"{PAPERLESS_URL}/api/documents/{doc_id}/"
    resp = requests.get(url, headers=paperless_headers(), timeout=HTTP_TIMEOUT)
    resp.raise_for_status()
    return resp.json().get("content", "") or ""


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------
def content_hash(text):
    """SHA-256-Hash des Volltextes zur Aenderungserkennung."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def recursive_split(text: str, chunk_size: int, chunk_overlap: int, separators: list[str]) -> list[str]:
    if not text:
        return []
    sep = separators[0]
    next_seps = separators[1:]
    parts = text.split(sep) if sep else list(text)
    chunks = []
    current = ""
    for part in parts:
        candidate = (current + sep + part).strip() if current else part.strip()
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current)
            if len(part.strip()) > chunk_size and next_seps:
                chunks.extend(recursive_split(part.strip(), chunk_size, chunk_overlap, next_seps))
                current = ""
            else:
                current = part.strip()
    if current:
        chunks.append(current)
    # Overlap: Prefix vom vorherigen Chunk anhängen
    if chunk_overlap > 0 and len(chunks) > 1:
        overlapped = [chunks[0]]
        for i in range(1, len(chunks)):
            prefix = chunks[i-1][-chunk_overlap:]
            merged = (prefix + " " + chunks[i]).strip()
            overlapped.append(merged if len(merged) <= chunk_size * 1.2 else chunks[i])
        return overlapped
    return chunks

def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    return recursive_split(text, chunk_size, chunk_overlap, ["\n\n", "\n", ". ", " "])


def embed(text):
    """Embedding fuer einen einzelnen Chunk via POST /v1/embeddings holen."""
    payload = {"input": text}
    if EMBEDDING_MODEL:
        payload["model"] = EMBEDDING_MODEL
    resp = requests.post(EMBEDDING_URL, json=payload, timeout=HTTP_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    return data["data"][0]["embedding"]


# ---------------------------------------------------------------------------
# Qdrant
# ---------------------------------------------------------------------------
def ensure_collection(client):
    """Collection anlegen, falls sie noch nicht existiert."""
    existing = [c.name for c in client.get_collections().collections]
    if QDRANT_COLLECTION in existing:
        log.debug("Collection '%s' existiert bereits", QDRANT_COLLECTION)
        return
    log.info("Erstelle Collection '%s' (Vektorgroesse=%d)", QDRANT_COLLECTION, VECTOR_SIZE)
    client.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config=qmodels.VectorParams(
            size=VECTOR_SIZE,
            distance=qmodels.Distance.COSINE,
        ),
    )
    # Index auf paperless_id fuer effizientes Filtern.
    client.create_payload_index(
        collection_name=QDRANT_COLLECTION,
        field_name="paperless_id",
        field_schema=qmodels.PayloadSchemaType.INTEGER,
    )


def existing_hash(client, paperless_id):
    """Vorhandenen content_hash fuer eine paperless_id aus Qdrant lesen.

    Liefert den Hash-String oder None, falls das Dokument noch nicht
    indexiert ist.
    """
    points, _ = client.scroll(
        collection_name=QDRANT_COLLECTION,
        scroll_filter=qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="paperless_id",
                    match=qmodels.MatchValue(value=paperless_id),
                )
            ]
        ),
        limit=1,
        with_payload=True,
        with_vectors=False,
    )
    if points:
        return points[0].payload.get("content_hash")
    return None


def delete_document_points(client, paperless_id):
    """Alle bestehenden Chunks eines Dokuments aus Qdrant loeschen."""
    client.delete(
        collection_name=QDRANT_COLLECTION,
        points_selector=qmodels.FilterSelector(
            filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="paperless_id",
                        match=qmodels.MatchValue(value=paperless_id),
                    )
                ]
            )
        ),
    )


def point_id(paperless_id, chunk_index):
    """Deterministische Point-ID via uuid5."""
    return str(uuid.uuid5(UUID_NAMESPACE, f"{paperless_id}_{chunk_index}"))


# ---------------------------------------------------------------------------
# Verarbeitung eines Dokuments
# ---------------------------------------------------------------------------
def process_document(client, doc):
    """Ein einzelnes Dokument indexieren (neu oder geaendert)."""
    paperless_id = doc["id"]
    content = fetch_document_content(paperless_id)
    chash = content_hash(content)

    # Status-Check: bereits identisch indexiert -> ueberspringen.
    prev_hash = existing_hash(client, paperless_id)
    if prev_hash == chash:
        log.info("Dokument %d unveraendert -> uebersprungen", paperless_id)
        return

    if prev_hash is not None:
        log.info("Dokument %d geaendert -> alte Chunks werden geloescht", paperless_id)
        delete_document_points(client, paperless_id)
    else:
        log.info("Dokument %d ist neu -> wird indexiert", paperless_id)

    chunks = chunk_text(content, CHUNK_SIZE, CHUNK_OVERLAP)
    if not chunks:
        log.info("Dokument %d hat keinen Textinhalt -> nichts zu indexieren", paperless_id)
        return

    # Gemeinsame Metadaten fuer alle Chunks.
    base_payload = {
        "paperless_id": paperless_id,
        "content_hash": chash,
        "title": doc.get("title"),
        "correspondent": doc.get("correspondent"),
        "document_type": doc.get("document_type"),
        "tags": doc.get("tags", []),
        "created_date": doc.get("created"),
        "modified_date": doc.get("modified"),
    }

    points = []
    for idx, chunk in enumerate(chunks):
        vector = embed(chunk)
        payload = dict(base_payload)
        payload["chunk_index"] = idx
        payload["content"] = chunk
        points.append(
            qmodels.PointStruct(
                id=point_id(paperless_id, idx),
                vector=vector,
                payload=payload,
            )
        )

    client.upsert(collection_name=QDRANT_COLLECTION, points=points)
    log.info("Dokument %d indexiert (%d Chunks)", paperless_id, len(points))


# ---------------------------------------------------------------------------
# Einstiegspunkt
# ---------------------------------------------------------------------------
def main():
    if not PAPERLESS_TOKEN:
        log.error("PAPERLESS_TOKEN ist nicht gesetzt - Abbruch")
        sys.exit(1)

    log.info("Starte Paperless-Vector-Indexer (One-Shot)")
    client = QdrantClient(url=QDRANT_URL, timeout=HTTP_TIMEOUT)
    ensure_collection(client)

    documents = fetch_all_documents()

    processed = 0
    failed = 0
    for doc in documents:
        try:
            process_document(client, doc)
            processed += 1
        except Exception as exc:  # pro Dokument: loggen und weitermachen
            failed += 1
            log.error("Fehler bei Dokument %s: %s", doc.get("id"), exc)

    log.info(
        "Fertig. Verarbeitet=%d, Fehler=%d (von %d Dokumenten)",
        processed,
        failed,
        len(documents),
    )


if __name__ == "__main__":
    main()
