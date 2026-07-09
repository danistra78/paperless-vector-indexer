class IndexerConnectionError(Exception):
    """Server nicht erreichbar oder Netzwerkfehler."""

class AuthenticationError(Exception):
    """Ungültiger oder fehlender API-Key (HTTP 401)."""

class SearchError(Exception):
    """Fehler bei der Suchanfrage (HTTP 4xx/5xx ausser 401/404)."""

class DocumentNotFoundError(Exception):
    """Dokument mit dieser ID existiert nicht (HTTP 404)."""
