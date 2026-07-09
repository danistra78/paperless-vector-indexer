# Paperless-Vector-Indexer

![Python](https://img.shields.io/badge/Python-3.11-blue.svg?logo=python&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED.svg?logo=docker&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-API-000000.svg?logo=flask&logoColor=white)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)

Überführt Dokumente aus [Paperless-ngx](https://docs.paperless-ngx.com/) in eine
[Qdrant](https://qdrant.tech/)-Vektordatenbank und ermöglicht damit **semantische Suche** und
**RAG-Anwendungen** über dein Dokumentenarchiv. Das Projekt bietet **zwei Betriebsmodi**:

- 🔄 **Indexer (One-Shot)** – wird ereignisgesteuert (Webhook / Post-consumption-Script) gestartet,
  indexiert neue/geänderte Dokumente in Qdrant und beendet sich danach wieder. Kein Polling-Loop,
  keine State-Dateien – der einzige Zustand lebt in Qdrant.
- 🌐 **API (read-only HTTP-Service)** – ein schlanker Flask-Dienst, der semantische bzw. hybride
  Suche und Dokument-Metadaten über eine REST-API bereitstellt. Kein Schreibzugriff, keine
  LLM-Logik – liest ausschließlich aus der vom Indexer befüllten Collection.

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
   ┌───────────────┐                                                 └──│  API (read-only)      │
   │  HTTP-Client   │ ───────────────────────────────────────────────  │  api.py (Flask)       │ ──▶ Embedding-API
   │  (curl / App)  │              /search, /document/{id}              └──────────────────────┘     (nur für Query-Embedding)
   └───────────────┘
```

**Indexer-Ablauf:**

1. Paperless-ngx nimmt ein Dokument auf und stößt den Indexer an.
2. Der Indexer ruft alle Dokumente samt Volltext paginiert über die REST-API ab.
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
- 🌐 **Read-only API-Mode** – Flask-Service mit `/health`, `/search`, `/document/{id}`.
- 🔁 **Inkrementelle Indexierung** – Änderungserkennung per SHA-256-`content_hash`; unveränderte Dokumente werden übersprungen.
- 🗑️ **Lösch-Synchronisation** – in Paperless gelöschte Dokumente werden automatisch aus Qdrant entfernt.
- 🔎 **Vector- & Hybrid-Suche** – rein semantisch oder kombiniert mit Volltext-Filter.
- 🔐 **API_KEY-Authentifizierung** – optionaler Schutz der Endpunkte per `X-API-Key`-Header.
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
> (z. B. `768` für `nomic-embed-text`, `1024` für `bge-m3`).

## Schnellstart

### 1. `.env`-Datei anlegen

Lege im Projektverzeichnis eine Datei `.env` an (sie ist per `.gitignore` von der Versionskontrolle
ausgeschlossen, da sie Secrets enthält):

```dotenv
# --- Paperless-ngx ---
PAPERLESS_URL=http://paperless:8000
PAPERLESS_TOKEN=dein_paperless_api_token

# --- Embedding-Service (OpenAI-kompatibel, Basis-URL ohne /v1/embeddings) ---
EMBEDDING_URL=http://embedding:8080
EMBEDDING_MODEL=nomic-embed-text
VECTOR_SIZE=768

# --- Qdrant ---
QDRANT_URL=http://qdrant:6333
QDRANT_COLLECTION=paperless

# --- Chunking ---
CHUNK_SIZE=800
CHUNK_OVERLAP=150

# --- Logging ---
LOG_LEVEL=INFO

# --- API-Mode (optional) ---
API_ENABLED=true
API_HOST=0.0.0.0
API_PORT=8080
API_KEY=dein_api_key
SEARCH_MODE=vector
```

Damit `docker compose` die Werte lädt, referenziere die Datei in der `docker-compose.yaml`
(`env_file: .env`) oder übergib sie per `--env-file`.

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
| `API_KEY`      | Optionaler API-Schlüssel; leer/nicht gesetzt = keine Authentifizierung        | *(leer)*  |
| `SEARCH_MODE`  | Standard-Suchmodus (`vector` oder `hybrid`), falls im Request nicht angegeben  | `vector`  |

## Betriebsmodi

### Indexer (One-Shot)

```bash
docker compose run --rm indexer
```

Startet einen einmaligen Indexierungslauf und beendet sich danach. Ideal für Webhook- oder
Cron-getriggerte Ausführung.

### API (read-only HTTP-Service)

```bash
docker compose up -d api
```

Startet den Flask-Service dauerhaft im Hintergrund (`restart: unless-stopped`), lauschend auf dem
über `API_PORT` konfigurierten Port (Default `8080`).

## API-Endpunkte

| Methode | Pfad                | Beschreibung                                             | Auth (falls `API_KEY` gesetzt) |
|---------|---------------------|---------------------------------------------------------|--------------------------------|
| `GET`   | `/health`           | Health-Check, liefert `{"status": "ok"}`                | nein                           |
| `POST`  | `/search`           | Suche über die indexierten Chunks (vector oder hybrid)  | ja                             |
| `GET`   | `/document/{id}`    | Metadaten eines Dokuments anhand der Paperless-ID       | ja                             |

Ist `API_KEY` gesetzt, müssen `/search` und `/document/{id}` den Header `X-API-Key` mitschicken.
`/health` benötigt niemals eine Authentifizierung.

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

Da der Indexer als One-Shot-Prozess läuft, lässt er sich direkt nach jeder Dokumenten-Aufnahme
durch Paperless-ngx anstoßen. Es gibt zwei erprobte Varianten.

### Variante A – Workflow-Trigger (Paperless-ngx ≥ 2.x)

1. In Paperless öffnen: **Einstellungen → Workflows → Workflow hinzufügen**.
2. Als **Trigger-Typ** `Dokument hinzugefügt` (bzw. `Consumption abgeschlossen`) wählen.
3. Optional Filter setzen (z. B. nur bestimmte Tags/Korrespondenten indexieren).
4. Eine **Aktion vom Typ „Webhook"** hinzufügen, die einen kleinen HTTP-Endpunkt aufruft,
   der seinerseits den Indexer startet:

   ```bash
   docker compose run --rm indexer
   ```

   Da Paperless-Workflows nur einen HTTP-Request auslösen, benötigst du dafür einen minimalen
   Webhook-Empfänger (z. B. ein kleines Skript hinter einem Reverse-Proxy), der den obigen Befehl
   ausführt. Der Indexer selbst braucht **keinen** dauerhaft laufenden Server, weil er ohnehin alle
   Dokumente prüft und nur die Deltas verarbeitet.

### Variante B – Post-consumption-Script

Paperless kann nach jedem konsumierten Dokument ein Skript ausführen
(`PAPERLESS_POST_CONSUME_SCRIPT`). Hinterlege ein kleines Wrapper-Skript, das den Indexer-Container
startet:

```bash
#!/usr/bin/env bash
# /usr/src/paperless/scripts/post_consume_indexer.sh
set -euo pipefail
docker compose \
  -f /pfad/zu/paperless-vector-indexer/docker-compose.yaml \
  --env-file /pfad/zu/paperless-vector-indexer/.env \
  run --rm indexer
```

Skript ausführbar machen und in der Paperless-Konfiguration eintragen
(`docker-compose.env` bzw. `paperless.conf`):

```bash
chmod +x /usr/src/paperless/scripts/post_consume_indexer.sh
```

```dotenv
PAPERLESS_POST_CONSUME_SCRIPT=/usr/src/paperless/scripts/post_consume_indexer.sh
```

> ⚠️ Damit das Skript den Docker-Host erreichen kann, muss der Docker-Socket im Paperless-Container
> verfügbar sein (Mount von `/var/run/docker.sock`).

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
