"""Read-only REST-API (API-Mode).

Schlanke Flask-API fuer die Suche und Dokument-Metadaten. Keine LLM-Logik,
kein Schreibzugriff auf Qdrant.
"""

import logging

from flask import Flask, request, jsonify, abort
from qdrant_client.models import Filter, FieldCondition, MatchValue

from clients import get_qdrant
from search import search as do_search
from config import (
    API_HOST,
    API_PORT,
    API_KEY,
    SEARCH_MODE,
    QDRANT_COLLECTION,
    LOG_LEVEL,
)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("api")

app = Flask(__name__)


def _check_auth():
    """Optionaler API-Key-Check via X-API-Key-Header."""
    if API_KEY and request.headers.get("X-API-Key") != API_KEY:
        abort(401, "Unauthorized")


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/search")
def search():
    _check_auth()
    body = request.get_json(force=True)
    query = body.get("query", "").strip()
    if not query:
        abort(400, "query required")
    limit = int(body.get("limit", 5))
    mode = body.get("mode", SEARCH_MODE)
    if mode not in ("vector", "hybrid"):
        abort(400, "mode must be vector or hybrid")
    log.info("search query=%r limit=%d mode=%s", query, limit, mode)
    results = do_search(query, limit, mode)
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


if __name__ == "__main__":
    log.info("API starting on %s:%d", API_HOST, API_PORT)
    app.run(host=API_HOST, port=API_PORT)
