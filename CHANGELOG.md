# Changelog

## [Unreleased]

### Sicherheit
- API startet nur noch mit `API_KEY` (Ausnahme: `API_ALLOW_NO_AUTH=true`); Schlüsselvergleich zeitkonstant
- Neuer Endpunkt `POST /index/{id}` mit eigenem `INDEX_API_KEY`; `post_consume.sh` ruft ihn per `curl` auf, Paperless braucht keinen Docker-Socket mehr
- `docker-compose.yaml` lädt alle Werte aus `.env` (Vorlage `.env.example`), keine Schlüssel mehr in der Compose-Datei
- Agent-Logs (`.logs/`) aus dem Repository entfernt

### Hinzugefügt
- Unterstützung für EmbeddingGemma 2: `EMBEDDING_QUERY_TEMPLATE` und `EMBEDDING_DOCUMENT_TEMPLATE` für Aufgaben-Präfixe
- `main.py --doc ID` indexiert ein einzelnes Dokument
- Prüfung der Embedding-Dimension gegen `VECTOR_SIZE`

### Geändert
- Der Dokumenttitel fließt in den `content_hash` ein: ein neuer Titel löst eine Neuindexierung aus (einmalige Neuindexierung bestehender Collections)
- `qdrant-client<1.12` gepinnt

### Hinzugefügt
- Offizieller Python-Client (paperless_vector_indexer/) mit Client, SearchResult, Document und typisierten Exceptions
- Hermes-kompatible Schnittstelle: from paperless_vector_indexer import Client
- API-Mode: optionaler HTTP-Service (GET /health, POST /search, GET /document/{id})
- Suchmodi: vector (semantisch) und hybrid (semantisch + Volltext)
- Gemeinsame Komponenten in config.py und clients.py (DRY)
- API_KEY-Authentifizierung (optional)
- Neuer docker-compose Service `api` (restart: unless-stopped)
- Lösch-Synchronisation: Dokumente die in Paperless gelöscht wurden, werden automatisch auch aus Qdrant entfernt

### Geändert
- Chunking-Algorithmus von Fixed-Size auf Recursive Split umgestellt

### Details
Ersetzt den bisherigen zeichenbasierten Fixed-Size-Chunker durch einen hierarchischen Recursive-Split-Algorithmus. Dieser versucht Text entlang natürlicher Grenzen zu trennen (`\n\n` → `\n` → `. ` → ` `), bevor er auf die nächste feinere Ebene zurückfällt.

**Motivation:** Normen, Weisungen und Verordnungen besitzen eine explizite Dokumentstruktur (Artikel, Absätze, Sätze). Der Fixed-Size-Chunker schnitt semantische Einheiten blind bei Zeichengrenze ab, was die Retrieval-Qualität in RAG-Szenarien verschlechterte.

**Auswirkung:**
- Chunks respektieren Absatz- und Satzgrenzen
- Overlap-Mechanismus bleibt erhalten
- ENV-Variablen `CHUNK_SIZE` und `CHUNK_OVERLAP` unverändert
- Keine neue Abhängigkeit (nur stdlib)
