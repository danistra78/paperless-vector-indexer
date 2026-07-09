import requests
from .models import SearchResult, Document
from .exceptions import IndexerConnectionError, AuthenticationError, SearchError, DocumentNotFoundError

class Client:
    def __init__(self, base_url: str = "http://localhost:8080", api_key: str = None, timeout: int = 10):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._headers = {"X-API-Key": api_key} if api_key else {}

    def _get(self, path: str) -> dict:
        try:
            resp = requests.get(f"{self._base_url}{path}", headers=self._headers, timeout=self._timeout)
        except requests.ConnectionError as e:
            raise IndexerConnectionError(str(e)) from e
        except requests.Timeout as e:
            raise IndexerConnectionError(f"Timeout after {self._timeout}s") from e
        self._raise_for_status(resp)
        return resp.json()

    def _post(self, path: str, body: dict) -> dict:
        try:
            resp = requests.post(f"{self._base_url}{path}", json=body, headers=self._headers, timeout=self._timeout)
        except requests.ConnectionError as e:
            raise IndexerConnectionError(str(e)) from e
        except requests.Timeout as e:
            raise IndexerConnectionError(f"Timeout after {self._timeout}s") from e
        self._raise_for_status(resp)
        return resp.json()

    def _raise_for_status(self, resp: requests.Response):
        if resp.status_code == 401:
            raise AuthenticationError("Ungültiger oder fehlender API-Key")
        if resp.status_code == 404:
            raise DocumentNotFoundError(resp.text)
        if resp.status_code >= 400:
            raise SearchError(f"HTTP {resp.status_code}: {resp.text}")

    def health(self) -> bool:
        try:
            data = self._get("/health")
            return data.get("status") == "ok"
        except (IndexerConnectionError, SearchError):
            return False

    def search(self, query: str, limit: int = 5, mode: str = None) -> list[SearchResult]:
        body = {"query": query, "limit": limit}
        if mode is not None:
            body["mode"] = mode
        data = self._post("/search", body)
        return [
            SearchResult(
                score=r["score"],
                document_id=r["document_id"],
                title=r.get("title"),
                text=r.get("text"),
                chunk_index=r.get("chunk_index"),
            )
            for r in data.get("results", [])
        ]

    def get_document(self, document_id: int) -> Document:
        data = self._get(f"/document/{document_id}")
        return Document(
            document_id=data["document_id"],
            title=data.get("title"),
            created=data.get("created"),
            tags=data.get("tags", []),
            document_type=data.get("document_type"),
            correspondent=data.get("correspondent"),
        )
