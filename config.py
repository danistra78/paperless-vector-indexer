"""Zentrale Konfiguration.

Alle Umgebungsvariablen werden hier einmalig eingelesen und von main.py
(Indexer) sowie api.py (API-Mode) importiert.
"""

import os

# --- Paperless-ngx ---
PAPERLESS_URL = os.environ["PAPERLESS_URL"]
PAPERLESS_TOKEN = os.environ["PAPERLESS_TOKEN"]

# --- Embedding-Service (OpenAI-kompatibel) ---
EMBEDDING_URL = os.environ["EMBEDDING_URL"]
EMBEDDING_MODEL = os.environ["EMBEDDING_MODEL"]
VECTOR_SIZE = int(os.environ.get("VECTOR_SIZE", 1024))

# --- Qdrant ---
QDRANT_URL = os.environ["QDRANT_URL"]
QDRANT_COLLECTION = os.environ["QDRANT_COLLECTION"]

# --- Chunking ---
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", 800))
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", 150))

# --- Logging ---
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

# --- API-Mode ---
API_ENABLED = os.environ.get("API_ENABLED", "false").lower() == "true"
API_HOST = os.environ.get("API_HOST", "0.0.0.0")
API_PORT = int(os.environ.get("API_PORT", 8080))
API_KEY = os.environ.get("API_KEY")  # optional, None = kein Auth
SEARCH_MODE = os.environ.get("SEARCH_MODE", "vector")  # vector|hybrid
