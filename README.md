# Paperless-Vector-Indexer

![Python](https://img.shields.io/badge/Python-3.11-blue.svg?logo=python&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED.svg?logo=docker&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-API-000000.svg?logo=flask&logoColor=white)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)

Überführt Dokumente aus [Paperless-ngx](https://docs.paperless-ngx.com/) in eine
[Qdrant](https://qdrant.tech/)-Vektordatenbank und ermöglicht damit **semantische Suche** und
**RAG-Anwendungen** über dein Dokumentenarchiv. Das Projekt bietet **zwei Betriebsmodi**:

- 🔄 **Indexer (One-Shot)** – gleicht alle Dokumente ab (z. B. nächtlich per Cron), indexiert
  neue/geänderte Dokumente in Qdrant und beendet sich danach wieder. Kein Polling-Loop,
  keine State-Dateien – der einzige Zustand lebt in Qdrant.
- 🌐 **API (HTTP-Service)** – ein schlanker Flask-Dienst, der semantische bzw. hybride
  Suche und Dokument-Metadaten über eine REST-API bereitstellt, geschützt per Schlüssel. Über
  `POST /index/{id}` meldet Paperless neue Dokumente, die dann sofort indexiert werden. Keine
  LLM-Logik.

Beide Modi teilen sich die gemeinsamen Komponenten `config.py` (Konfiguration) und `clients.py`
(Qdrant- und Embedding-Client), es gibt also keine Code-Duplizierung.

## Architektur-Übersicht

```
                          (1) Dokument aufgenommen
                              Webhook / Post-consume
   ┌───────────────┐                                     ┌──────────────────────┐        ┌──────────────────────┐
   │  Paperless-ngx │ ──────────────────────────────────▶│  Indexer (One-Shot)   │ ─────▶ │  Embedding-API        │
   │  (REST-API)    │      (2) Dokumente + Volltext        │  main.py              │        │  (OpenAI-kompatibel)   │
   └───────────────┘                                     └──────────┬───────────┘        │  Ollama / LocalAI      │
                                                                     │                    └───────────┬──────────┘
                                                    (3) Chunk+Vektor  │                                │
                                                                     ▼                                │ Vektor
                                                          ┌──────────────────────┐ ◀─────────────────┘
                                                          │  Qdrant               │
                                                          │  (Vektor-Datenbank)   │
                                                          └──────────┬───────────┘
                                                                     ▲
                                                    (Suche/Lesen)     │  ┌──────────────────────┐
   ┌───────────────┐                                                 └──│  API                  │
   │  HTTP-Client   │ ───────────────────────────────────────────────  │  api.py (Flask)       │ ──▶ Embedding-API
   │  (curl / App)  │              /search, /document/{id}              └──────────────────────┘     (nur für Query-Embedding)
   └───────────────┘
```

**Indexer-Ablauf:**

1. Paperless-ngx nimmt ein Dokument auf und meldet es per `post_consume.sh` an
   `POST /index/{id}`; die API indexiert genau dieses Dokument.
2. Der Volllauf (`main.py`, z. B. nächtlich) ruft alle Dokumente samt Volltext paginiert über die
   REST-API ab.
3. Neue/geänderte Dokumente werden in überlappende Chunks zerlegt, embeddet und als Points mit
   Metadaten in Qdrant gespeichert.
4. Am Ende jedes Laufs findet ein Abgleich statt: Alle Qdrant-IDs, die nicht mehr in Paperless
   existieren, werden gelöscht (Lösch-Synchronisation).

**API-Ablauf:**

- Ein HTTP-Client stellt eine Suchanfrage an `/search`. Die API embeddet die Query über die
  Embedding-API und sucht in Qdrant (vector oder hybrid). Über `/document/{id}` lassen sich
  Metadaten eines Dokuments abrufen.

## Features

- 🚀 **One-Shot-Indexer** – kein Polling-Loop, kein Dauerdienst; läuft, wenn er gebraucht wird.
- 🌐 **API-Mode** – Flask-Service mit `/health`, `/search`, `/document/{id}` und `/index/{id}`.
- 🔁 **Inkrementelle Indexierung** – Änderungserkennung per SHA-256-`content_hash`; unveränderte Dokumente werden übersprungen.
- 🗑️ **Lösch-Synchronisation** – in Paperless gelöschte Dokumente werden automatisch aus Qdrant entfernt.
- 🔎 **Vector- & Hybrid-Suche** – rein semantisch oder kombiniert mit Volltext-Filter.
- 🔐 **Schlüssel-Pflicht** – `/search` und `/document` nur mit `API_KEY`, `/index` mit eigenem `INDEX_API_KEY`.
- ♻️ **Idempotent** – deterministische Point-IDs (`uuid5`), wiederholte Läufe erzeugen keine Duplikate.
- ✂️ **Recursive Split Chunking (Absatz → Satz → Wort)** – Text wird hierarchisch an natürlichen Grenzen mit konfigurierbarer Überlappung geteilt.
- 🔌 **OpenAI-kompatible Embeddings** – funktioniert mit Ollama, LocalAI, LM Studio & Co.
- 🗂️ **Reichhaltige Metadaten** – Titel, Korrespondent, Dokumenttyp, Tags und Datumsangaben landen im Qdrant-Payload.
- 🧠 **Zustandslos** – keine State-Dateien; der einzige Zustand ist der `content_hash` in Qdrant.
- 🐳 **Docker-ready** – minimales Image, beide Modi über `docker compose`.
- 💻 **CPU-only tauglich** – benötigt selbst keine GPU (Embeddings erledigt der externe Service).

## Voraussetzungen

- **Paperless-ngx** mit erreichbarer REST-API und einem API-Token (Einstellungen → API-Token).
- **Qdrant** (z. B. als Docker-Container `qdrant/qdrant`), erreichbar über HTTP.
- **Ein OpenAI-kompatibler Embedding-Endpunkt** mit Route `POST /v1/embeddings`, z. B.:
  - [Ollama](https://ollama.com/) (z. B. Modell `nomic-embed-text`)
  - [LocalAI](https://localai.io/)
  - [LM Studio](https://lmstudio.ai/) oder jeder andere kompatible Dienst.
- **Docker** & **Docker Compose**.

> ℹ️ Die Dimension der Vektoren (`VECTOR_SIZE`) muss zum verwendeten Embedding-Modell passen
> (z. B. `768` für `embeddinggemma-2` oder `nomic-embed-text`, `1024` für `bge-m3`). Weicht sie ab,
> bricht der Indexer mit einer klaren Fehlermeldung ab.

### Empfohlenes Modell: EmbeddingGemma 2

[EmbeddingGemma 2](https://huggingface.co/google/embeddinggemma-2) (Google, Apache 2.0) hat
270 Mio. Parameter für Text, 768 Dimensionen, 8k Token Kontext und deckt über 100 Sprachen ab,
darunter Deutsch. Es erwartet Aufgaben-Präfixe, die über `EMBEDDING_QUERY_TEMPLATE` und
`EMBEDDING_DOCUMENT_TEMPLATE` gesetzt werden (siehe `.env.example`).

Bereitstellen z. B. mit llama.cpp und dem GGUF von `ggml-org/embeddinggemma-2-GGUF`:

```bash
llama-server --model embeddinggemma-2-BF16.gguf --embeddings --alias embeddinggemma-2 \
  --ctx-size 8192 --batch-size 8192 --ubatch-size 8192 --n-gpu-layers 99 --port 8080
```

> ⚠️ Ollama führt EmbeddingGemma 2 über MLX aus. Auf älteren NVIDIA-GPUs (z. B. Pascal) steht
> MLX nicht zur Verfügung; llama.cpp läuft dort.

Beim Wechsel des Modells eine **neue** `QDRANT_COLLECTION` verwenden und den Indexer einmal
vollständig laufen lassen; Vektoren verschiedener Modelle sind nicht vergleichbar.

## Schnellstart

### 1. `.env`-Datei anlegen

```bash
cp .env.example .env
```

Werte in `.env` eintragen, insbesondere `PAPERLESS_TOKEN`, `API_KEY` und `INDEX_API_KEY`.
Die Datei ist per `.gitignore` ausgeschlossen. **Schlüssel gehören nie in die
`docker-compose.yaml`** – sie lädt alle Werte per `env_file: .env`.

Schlüssel erzeugen:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Eigene Anpassungen an der Compose-Datei (z. B. `network_mode: host`) gehören in eine
`docker-compose.override.yaml`; auch sie ist ausgeschlossen.

### 2. Indexer einmalig ausführen

```bash
docker compose run --rm indexer
```

Der Container läuft genau einmal durch, verarbeitet alle neuen/geänderten Dokumente und beendet
sich anschließend (`restart: "no"`). Wiederhole den Aufruf jederzeit – bereits indexierte,
unveränderte Dokumente werden automatisch übersprungen.

### 3. API starten (optional)

```bash
docker compose up -d api
```

## Umgebungsvariablen

### Indexer & gemeinsame Variablen

| Variable            | Beschreibung                                                              | Default                                 |
|---------------------|---------------------------------------------------------------------------|-----------------------------------------|
| `PAPERLESS_URL`     | Basis-URL der Paperless-ngx-Instanz                                       | `http://paperless:8000`                 |
| `PAPERLESS_TOKEN`   | API-Token aus Paperless (**erforderlich**, sonst Abbruch)                 | *(leer)*                                |
| `EMBEDDING_URL`     | Basis-URL des OpenAI-kompatiblen Embedding-Dienstes (Pfad `/v1/embeddings` wird angehängt) | `http://embedding:8080`   |
| `EMBEDDING_MODEL`   | Modellname, wird im Embedding-Request mitgeschickt                        | *(leer)*                                |
| `VECTOR_SIZE`       | Dimension der Embedding-Vektoren (muss zum Modell passen)                 | `1024`                                  |
| `EMBEDDING_QUERY_TEMPLATE` | Vorlage für Suchanfragen, `{text}` = Anfrage                       | `{text}`                                |
| `EMBEDDING_DOCUMENT_TEMPLATE` | Vorlage für Chunks, `{title}` = Dokumenttitel, `{text}` = Chunk  | `{text}`                                |
| `QDRANT_URL`        | Basis-URL der Qdrant-Instanz                                              | `http://qdrant:6333`                    |
| `QDRANT_COLLECTION` | Name der Qdrant-Collection (wird bei Bedarf automatisch angelegt)         | `paperless`                             |
| `CHUNK_SIZE`        | Maximale Chunk-Größe in Zeichen (Recursive Split)                         | `800`                                   |
| `CHUNK_OVERLAP`     | Überlappung zwischen aufeinanderfolgenden Chunks in Zeichen (Recursive Split) | `150`                               |
| `LOG_LEVEL`         | Log-Level (`INFO` oder `DEBUG`)                                           | `INFO`                                  |

### API-Variablen

| Variable       | Beschreibung                                                                  | Default   |
|----------------|-------------------------------------------------------------------------------|-----------|
| `API_ENABLED`  | Schalter für den API-Mode (`true`/`false`)                                    | `false`   |
| `API_HOST`     | Bind-Adresse des HTTP-Servers                                                 | `0.0.0.0` |
| `API_PORT`     | Port des HTTP-Servers                                                         | `8080`    |
| `API_KEY`      | Schlüssel für `/search` und `/document`. **Pflicht** – ohne ihn startet die API nicht | *(leer)*  |
| `API_ALLOW_NO_AUTH` | `true` erlaubt den Start ohne `API_KEY` (nur für isolierte Testumgebungen) | `false` |
| `INDEX_API_KEY` | Eigener Schlüssel für `POST /index/{id}`; leer = Endpunkt abgeschaltet       | *(leer)*  |
| `SEARCH_MODE`  | Standard-Suchmodus (`vector` oder `hybrid`), falls im Request nicht angegeben  | `vector`  |

## Betriebsmodi

### Indexer (One-Shot)

```bash
docker compose run --rm indexer
```

Startet einen einmaligen Indexierungslauf und beendet sich danach. Ideal für Webhook- oder
Cron-getriggerte Ausführung.

### API (HTTP-Service)

```bash
docker compose up -d api
```

Startet den Flask-Service dauerhaft im Hintergrund (`restart: unless-stopped`), lauschend auf dem
über `API_PORT` konfigurierten Port (Default `8080`).

## API-Endpunkte

| Methode | Pfad                | Beschreibung                                             | Auth                           |
|---------|---------------------|---------------------------------------------------------|--------------------------------|
| `GET`   | `/health`           | Health-Check, liefert `{"status": "ok"}`                | nein                           |
| `POST`  | `/search`           | Suche über die indexierten Chunks (vector oder hybrid)  | `X-API-Key: <API_KEY>`         |
| `GET`   | `/document/{id}`    | Metadaten eines Dokuments anhand der Paperless-ID       | `X-API-Key: <API_KEY>`         |
| `POST`  | `/index/{id}`       | Dokument im Hintergrund (neu) indexieren, Antwort `202` | `X-API-Key: <INDEX_API_KEY>`   |

`/search` und `/document/{id}` liefern Dokumentinhalte und verlangen darum immer den Header
`X-API-Key`. `/index/{id}` hat einen eigenen Schlüssel, damit das Post-Consume-Script von
Paperless nur indexieren, aber nicht suchen kann. `/health` benötigt keine Authentifizierung.

### `GET /health`

```bash
curl http://localhost:8080/health
```

Antwort:

```json
{"status": "ok"}
```

### `POST /search`

Das Feld `mode` ist **optional** – fehlt es, wird der über `SEARCH_MODE` konfigurierte
Standardmodus verwendet.

Vector-Suche (semantisch):

```bash
curl -X POST http://localhost:8080/search \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dein_api_key" \
  -d '{"query": "Kündigungsfrist Mietvertrag", "limit": 5, "mode": "vector"}'
```

Hybrid-Suche (semantisch + Volltext):

```bash
curl -X POST http://localhost:8080/search \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dein_api_key" \
  -d '{"query": "Kündigungsfrist Mietvertrag", "limit": 5, "mode": "hybrid"}'
```

Beispiel-Antwort:

```json
{
  "results": [
    {
      "score": 0.8123,
      "document_id": 42,
      "title": "Mietvertrag Musterstraße",
      "text": "Die Kündigungsfrist beträgt drei Monate ...",
      "chunk_index": 2
    }
  ]
}
```

### `GET /document/{id}`

```bash
curl http://localhost:8080/document/42 \
  -H "X-API-Key: dein_api_key"
```

Beispiel-Antwort:

```json
{
  "document_id": 42,
  "title": "Mietvertrag Musterstraße",
  "created": "2024-05-01T10:00:00Z",
  "tags": [3, 7],
  "document_type": 2,
  "correspondent": 5
}
```

### Suchmodi

| Modus    | Beschreibung                                                                       |
|----------|------------------------------------------------------------------------------------|
| `vector` | Rein semantische Suche über die Embedding-Vektoren (Cosine-Ähnlichkeit).           |
| `hybrid` | Kombination aus semantischer Suche und Volltext-Filter; Ergebnisse werden gemerged (dedupliziert nach Point-ID) und nach Score sortiert. |

## Chunking-Algorithmus

Der Indexer verwendet einen hierarchischen **Recursive-Split-Algorithmus** statt eines einfachen
Fixed-Size-Chunkers. Der Text wird zunächst entlang der gröbsten natürlichen Grenze getrennt und
fällt nur dann auf die nächstfeinere Ebene zurück, wenn ein Abschnitt weiterhin zu groß ist. Die
Separator-Hierarchie lautet:

1. `\n\n` (Absatz)
2. `\n` (Zeile)
3. `. ` (Satz)
4. ` ` (Wort)

Für Normen, Weisungen und Verordnungen ist dies besser geeignet, da deren explizite
Dokumentstruktur (Artikel, Absätze, Sätze) erhalten bleibt und semantische Einheiten nicht mitten
im Satz zerschnitten werden. Chunk-Größe und Überlappung sind über `CHUNK_SIZE` und
`CHUNK_OVERLAP` steuerbar.

## Paperless Webhook-Integration

Nach jedem aufgenommenen Dokument ruft Paperless das mitgelieferte `post_consume.sh` auf. Es
meldet das Dokument per `curl` an `POST /index/{id}` der API, die es im Hintergrund indexiert.
Paperless braucht dafür **keinen Docker-Socket** – ein eingebundener Socket gäbe einem
kompromittierten Paperless Root-Rechte auf dem Host.

1. Das Repository in den Paperless-Container einbinden (nur lesend) und das Script eintragen:

   ```yaml
   volumes:
     - /pfad/zu/paperless-vector-indexer:/scripts/indexer:ro
   environment:
     PAPERLESS_POST_CONSUME_SCRIPT: /scripts/indexer/post_consume.sh
     INDEXER_URL: http://indexer-api:8080
     INDEXER_API_KEY: ${INDEXER_API_KEY}   # gleicher Wert wie INDEX_API_KEY der API
   ```

2. In der `.env` des Indexers `INDEX_API_KEY` setzen und die API neu starten.

Schlägt der Aufruf fehl, bricht das Script die Aufnahme nicht ab. Ein regelmäßiger Volllauf
(`docker compose run --rm indexer`, z. B. nächtlich per Cron) holt verpasste Dokumente nach und
gleicht Löschungen ab.

Einzelnes Dokument von Hand indexieren:

```bash
docker compose run --rm indexer python main.py --doc 42
```

## Python Client

Das Projekt enthält einen **offiziellen Python-Client** (`paperless_vector_indexer/`), der die
API bequem aus Python heraus ansprechbar macht. Da der Client im selben Repository lebt, bleibt er
**immer synchron mit der API** – Änderungen an Endpunkten oder Response-Strukturen werden zusammen
mit dem Client gepflegt.

### Installation

Es wird **kein `pip`** benötigt. Sobald das Repository im Python-Path liegt (z. B. weil du dich im
Projektverzeichnis befindest oder es zum `PYTHONPATH` hinzufügst), ist das Package direkt
importierbar:

```python
from paperless_vector_indexer import Client
```

### Verwendung

```python
from paperless_vector_indexer import (
    Client,
    IndexerConnectionError,
    AuthenticationError,
    SearchError,
    DocumentNotFoundError,
)

# Client initialisieren (api_key nur nötig, wenn die API mit API_KEY läuft)
client = Client(base_url="http://localhost:8080", api_key="dein_api_key")

# 1. Health-Check
if not client.health():
    raise SystemExit("API nicht erreichbar")

# 2. Suche (mode ist optional -> Default der API greift, sonst "vector"/"hybrid")
try:
    results = client.search("Kündigungsfrist Mietvertrag", limit=5, mode="hybrid")
    for r in results:
        print(f"[{r.score:.3f}] Dok {r.document_id} · {r.title}")
        print(f"   {r.text}")
except AuthenticationError:
    print("Ungültiger API-Key")
except SearchError as e:
    print(f"Suche fehlgeschlagen: {e}")

# 3. Dokument-Metadaten abrufen
try:
    doc = client.get_document(42)
    print(doc.title, doc.created, doc.tags)
except DocumentNotFoundError:
    print("Dokument existiert nicht")
except IndexerConnectionError as e:
    print(f"Verbindungsfehler: {e}")
```

### Client-Parameter

| Parameter  | Typ           | Beschreibung                                                | Default                   |
|------------|---------------|-------------------------------------------------------------|---------------------------|
| `base_url` | `str`         | Basis-URL der API (trailing Slash wird entfernt)            | `http://localhost:8080`   |
| `api_key`  | `str \| None` | API-Schlüssel; wird als `X-API-Key`-Header gesendet         | `None` (kein Header)      |
| `timeout`  | `int`         | HTTP-Timeout in Sekunden                                    | `10`                      |

### Methoden

| Methode                                          | Rückgabe             | Beschreibung                                                    |
|--------------------------------------------------|----------------------|----------------------------------------------------------------|
| `health()`                                       | `bool`               | `True`, wenn die API erreichbar ist und `{"status": "ok"}` liefert. |
| `search(query, limit=5, mode=None)`              | `list[SearchResult]` | Führt eine Suche aus; `mode` optional (`vector`/`hybrid`).      |
| `get_document(document_id)`                      | `Document`           | Liefert die Metadaten eines Dokuments.                         |

### Exceptions

| Exception                 | Ausgelöst bei                                                          |
|---------------------------|------------------------------------------------------------------------|
| `IndexerConnectionError`  | Server nicht erreichbar oder Netzwerk-/Timeout-Fehler.                 |
| `AuthenticationError`     | Ungültiger oder fehlender API-Key (HTTP 401).                         |
| `SearchError`             | Fehler bei der Suchanfrage (HTTP 4xx/5xx außer 401/404).              |
| `DocumentNotFoundError`   | Dokument mit dieser ID existiert nicht (HTTP 404).                    |

### Hermes-Kompatibilität

Der Client ist bewusst schlank und **Hermes-kompatibel**: Ein einzelner Import genügt, um ihn in
Hermes-Skills, Tools oder Agenten einzubinden:

```python
from paperless_vector_indexer import Client
```

Es sind keine zusätzlichen Abhängigkeiten außer `requests` erforderlich.

## Datenmodell (Qdrant-Payload)

Jeder Chunk wird als eigener Point in Qdrant gespeichert. Die Point-ID wird deterministisch über
`uuid5(namespace, "{paperless_id}_{chunk_index}")` erzeugt, sodass wiederholte Läufe idempotent sind.
Der Payload je Point:

| Feld            | Typ    | Beschreibung                                    |
|-----------------|--------|-------------------------------------------------|
| `paperless_id`  | int    | Dokument-ID in Paperless (indiziert)            |
| `chunk_index`   | int    | Laufender Index des Chunks innerhalb des Dokuments |
| `content`       | string | Text des Chunks                                 |
| `content_hash`  | string | SHA-256 des gesamten Dokumenttextes (Änderungserkennung) |
| `title`         | string | Dokumenttitel                                   |
| `correspondent` | int    | Korrespondent-ID                                |
| `document_type` | int    | Dokumenttyp-ID                                  |
| `tags`          | list   | Liste der Tag-IDs                               |
| `created_date`  | string | Erstellungsdatum des Dokuments                  |
| `modified_date` | string | Änderungsdatum des Dokuments                    |

Die Collection wird mit **Cosine-Distanz** und der über `VECTOR_SIZE` konfigurierten Dimension
automatisch angelegt; auf `paperless_id` wird ein Payload-Index für effizientes Filtern erstellt.

## Lizenz

Veröffentlicht unter der **MIT-Lizenz**. Die Nutzung, Änderung und Weiterverbreitung ist frei
gestattet; der Software wird keinerlei Gewährleistung beigelegt.
