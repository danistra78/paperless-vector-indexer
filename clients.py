"""Gemeinsame Clients.

Qdrant-Client und Embedding-Funktion. Wird von main.py (Indexer) und
search.py (API) genutzt, damit kein Code dupliziert wird.
"""

import requests
from qdrant_client import QdrantClient

from config import QDRANT_URL, EMBEDDING_URL, EMBEDDING_MODEL


def get_qdrant() -> QdrantClient:
    """Neuen Qdrant-Client erzeugen."""
    return QdrantClient(url=QDRANT_URL)


def embed(text: str) -> list[float]:
    """Embedding fuer einen Text via OpenAI-kompatiblen Endpunkt holen."""
    resp = requests.post(
        f"{EMBEDDING_URL}/v1/embeddings",
        json={"model": EMBEDDING_MODEL, "input": text},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]
