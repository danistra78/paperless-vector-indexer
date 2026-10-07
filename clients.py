"""Gemeinsame Clients.

Qdrant-Client und Embedding-Funktionen. Wird von main.py (Indexer) und
search.py (API) genutzt, damit kein Code dupliziert wird.
"""

import requests
from qdrant_client import QdrantClient

from config import (
    QDRANT_URL,
    EMBEDDING_URL,
    EMBEDDING_MODEL,
    EMBEDDING_QUERY_TEMPLATE,
    EMBEDDING_DOCUMENT_TEMPLATE,
    VECTOR_SIZE,
    HTTP_TIMEOUT,
)


def get_qdrant() -> QdrantClient:
    """Neuen Qdrant-Client erzeugen."""
    return QdrantClient(url=QDRANT_URL, timeout=HTTP_TIMEOUT)


def embed(text: str) -> list[float]:
    """Embedding fuer einen Text via OpenAI-kompatiblen Endpunkt holen."""
    resp = requests.post(
        f"{EMBEDDING_URL}/v1/embeddings",
        json={"model": EMBEDDING_MODEL, "input": text},
        timeout=HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    try:
        vector = resp.json()["data"][0]["embedding"]
    except (KeyError, IndexError, ValueError) as exc:
        raise RuntimeError(f"Unerwartete Embedding-Antwort: {exc}") from exc
    # Falsche Dimension faellt sonst erst beim Upsert in Qdrant auf.
    if len(vector) != VECTOR_SIZE:
        raise RuntimeError(
            f"Embedding hat {len(vector)} Dimensionen, VECTOR_SIZE ist {VECTOR_SIZE}"
        )
    return vector


def embed_query(query: str) -> list[float]:
    """Suchanfrage einbetten (mit EMBEDDING_QUERY_TEMPLATE)."""
    return embed(EMBEDDING_QUERY_TEMPLATE.replace("{text}", query))


def embed_document(text: str, title: str | None) -> list[float]:
    """Dokument-Chunk einbetten (mit EMBEDDING_DOCUMENT_TEMPLATE).

    {title} zuerst ersetzen, damit Klammern im Chunk-Text unangetastet bleiben.
    """
    prompt = EMBEDDING_DOCUMENT_TEMPLATE.replace("{title}", title or "none")
    return embed(prompt.replace("{text}", text))
