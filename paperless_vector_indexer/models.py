from dataclasses import dataclass, field
from typing import Optional

@dataclass
class SearchResult:
    score: float
    document_id: int
    title: Optional[str]
    text: Optional[str]
    chunk_index: Optional[int]

@dataclass
class Document:
    document_id: int
    title: Optional[str]
    created: Optional[str]
    tags: list = field(default_factory=list)
    document_type: Optional[str] = None
    correspondent: Optional[str] = None
