"""Zentrale Konfiguration.

Alle Umgebungsvariablen werden hier einmalig eingelesen und von main.py
(Indexer) sowie api.py (API-Mode) importiert.
"""

import os

# --- Paperless-ngx ---
PAPERLESS_URL = os.environ.get("PAPERLESS_URL", "http://paperless:8000")
PAPERLESS_TOKEN = os.environ["PAPERLESS_TOKEN"]

# --- Embedding-Service (OpenAI-kompatibel) ---
EMBEDDING_URL = os.environ.get("EMBEDDING_URL", "http://embedding:8080")
EMBEDDING_MODEL = os.environ["EMBEDDING_MODEL"]
VECTOR_SIZE = int(os.environ.get("VECTOR_SIZE", 1024))
# Vorlagen fuer den Text, der eingebettet wird: {text} = Anfrage bzw. Chunk,
# {title} = Dokumenttitel (nur Dokumente). Modelle wie EmbeddingGemma 2
# erwarten Aufgaben-Praefixe; ohne Angabe wird der Text unveraendert gesendet.
EMBEDDING_QUERY_TEMPLATE = os.environ.get("EMBEDDING_QUERY_TEMPLATE", "{text}")
EMBEDDING_DOCUMENT_TEMPLATE = os.environ.get("EMBEDDING_DOCUMENT_TEMPLATE", "{text}")

# --- Qdrant ---
QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant:6333")
QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", "paperless")

# --- Chunking ---
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", 800))
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", 150))

# --- HTTP ---
HTTP_TIMEOUT = int(os.environ.get("HTTP_TIMEOUT", 60))

# --- Logging ---
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

# --- API-Mode ---
API_ENABLED = os.environ.get("API_ENABLED", "false").lower() == "true"
API_HOST = os.environ.get("API_HOST", "0.0.0.0")
API_PORT = int(os.environ.get("API_PORT", 8080))
# Schluessel fuer /search und /document. Ohne Schluessel startet die API nur,
# wenn API_ALLOW_NO_AUTH=true ausdruecklich gesetzt ist.
API_KEY = os.environ.get("API_KEY") or None
API_ALLOW_NO_AUTH = os.environ.get("API_ALLOW_NO_AUTH", "false").lower() == "true"
# Eigener Schluessel fuer POST /index/<id> (Post-Consume-Script von Paperless).
# Nicht gesetzt = Endpunkt abgeschaltet.
INDEX_API_KEY = os.environ.get("INDEX_API_KEY") or None
SEARCH_MODE = os.environ.get("SEARCH_MODE", "vector")  # vector|hybrid
