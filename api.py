"""REST-API (API-Mode).

Schlanke Flask-API fuer die Suche und Dokument-Metadaten. Keine LLM-Logik.
Einziger schreibender Endpunkt ist POST /index/<id>: Er stoesst die
Indexierung eines Dokuments an (Post-Consume-Script von Paperless) und hat
einen eigenen Schluessel (INDEX_API_KEY).
"""

import hmac
import logging
import sys
from concurrent.futures import ThreadPoolExecutor

from flask import Flask, request, jsonify, abort
from qdrant_client.models import Filter, FieldCondition, MatchValue

from clients import get_qdrant
from main import index_document
from search import search as do_search
from config import (
    API_HOST,
    API_PORT,
    API_KEY,
    API_ALLOW_NO_AUTH,
    INDEX_API_KEY,
    SEARCH_MODE,
    QDRANT_COLLECTION,
    LOG_LEVEL,
)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("api")

app = Flask(__name__)

# Ein Worker: Indexierungen laufen nacheinander und blockieren den Request nicht.
_index_worker = ThreadPoolExecutor(max_workers=1)


def _key_matches(expected: str) -> bool:
    given = request.headers.get("X-API-Key", "")
    return hmac.compare_digest(given.encode(), expected.encode())


def _check_auth():
    """API-Key-Check via X-API-Key-Header (entfaellt nur mit API_ALLOW_NO_AUTH)."""
    if API_KEY and not _key_matches(API_KEY):
        abort(401, "Unauthorized")


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/search")
def search():
    _check_auth()
    body = request.get_json(force=True)
    if not isinstance(body, dict):
        abort(400, "invalid JSON body")
    query = body.get("query", "").strip()
    if not query:
        abort(400, "query required")
    try:
        limit = int(body.get("limit", 5))
    except (TypeError, ValueError):
        abort(400, "limit must be an integer")
    mode = body.get("mode", SEARCH_MODE)
    if mode not in ("vector", "hybrid"):
        abort(400, "mode must be vector or hybrid")
    log.info("search query=%r limit=%d mode=%s", query, limit, mode)
    try:
        results = do_search(query, limit, mode)
    except RuntimeError as exc:
        log.error("search failed: %s", exc)
        abort(502, "embedding service returned an unexpected response")
    return jsonify({"results": results})


@app.get("/document/<int:doc_id>")
def document(doc_id: int):
    _check_auth()
    qdrant = get_qdrant()
    hits, _ = qdrant.scroll(
        collection_name=QDRANT_COLLECTION,
        scroll_filter=Filter(
            must=[FieldCondition(key="paperless_id", match=MatchValue(value=doc_id))]
        ),
        limit=1,
        with_payload=True,
        with_vectors=False,
    )
    if not hits:
        abort(404, f"Document {doc_id} not found")
    p = hits[0].payload
    return jsonify({
        "document_id": p.get("paperless_id"),
        "title": p.get("title"),
        "created": p.get("created_date"),
        "tags": p.get("tags", []),
        "document_type": p.get("document_type"),
        "correspondent": p.get("correspondent"),
    })


def _index_in_background(doc_id: int):
    try:
        index_document(doc_id)
    except Exception as exc:  # Fehler nur loggen, der naechtliche Volllauf holt nach
        log.error("Indexierung von Dokument %d fehlgeschlagen: %s", doc_id, exc)


@app.post("/index/<int:doc_id>")
def index(doc_id: int):
    if not INDEX_API_KEY:
        abort(404)
    if not _key_matches(INDEX_API_KEY):
        abort(401, "Unauthorized")
    log.info("index document=%d", doc_id)
    _index_worker.submit(_index_in_background, doc_id)
    return jsonify({"status": "queued", "document_id": doc_id}), 202


if __name__ == "__main__":
    if not API_KEY and not API_ALLOW_NO_AUTH:
        log.error(
            "API_KEY ist nicht gesetzt - Abbruch. Ohne Schluessel waeren alle "
            "Dokumentinhalte fuer jeden im Netz lesbar (API_ALLOW_NO_AUTH=true erzwingt es)."
        )
        sys.exit(1)
    log.info("API starting on %s:%d", API_HOST, API_PORT)
    app.run(host=API_HOST, port=API_PORT)
