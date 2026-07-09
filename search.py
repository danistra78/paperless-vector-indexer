"""SearchService.

Kapselt die Vektor- und Hybrid-Suche gegen Qdrant. Read-only, keine
LLM-Logik.
"""

from qdrant_client.models import Filter, FieldCondition, MatchText

from clients import get_qdrant, embed
from config import QDRANT_COLLECTION


def _payload_to_result(hit) -> dict:
    """Qdrant-Treffer in ein schlankes Ergebnis-Dict umwandeln."""
    p = hit.payload
    return {
        "score": round(hit.score, 4) if hit.score is not None else None,
        "document_id": p.get("paperless_id"),
        "title": p.get("title"),
        "text": p.get("content"),
        "chunk_index": p.get("chunk_index"),
    }


def vector_search(query: str, limit: int) -> list[dict]:
    """Rein semantische Suche."""
    qdrant = get_qdrant()
    vector = embed(query)
    hits = qdrant.search(
        collection_name=QDRANT_COLLECTION,
        query_vector=vector,
        limit=limit,
        with_payload=True,
    )
    return [_payload_to_result(h) for h in hits]


def hybrid_search(query: str, limit: int) -> list[dict]:
    """Kombination aus semantischer Suche und Volltext-Filter."""
    qdrant = get_qdrant()
    vector = embed(query)

    # Semantische Suche
    vec_hits = qdrant.search(
        collection_name=QDRANT_COLLECTION,
        query_vector=vector,
        limit=limit,
        with_payload=True,
    )

    # Volltextsuche via Payload-Filter
    text_hits, _ = qdrant.scroll(
        collection_name=QDRANT_COLLECTION,
        scroll_filter=Filter(
            must=[FieldCondition(key="content", match=MatchText(text=query))]
        ),
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )

    # Merge: deduplizieren nach point id, hoeheren Score behalten
    seen = {}
    for h in vec_hits:
        seen[h.id] = _payload_to_result(h)
    for h in text_hits:
        if h.id not in seen:
            # Texttreffer ohne Vektorscore
            seen[h.id] = {**_payload_to_result(h), "score": 0.5}

    results = sorted(seen.values(), key=lambda x: x["score"], reverse=True)
    return results[:limit]


def search(query: str, limit: int, mode: str) -> list[dict]:
    """Sucheinstiegspunkt: waehlt zwischen vector und hybrid."""
    if mode == "hybrid":
        return hybrid_search(query, limit)
    return vector_search(query, limit)
