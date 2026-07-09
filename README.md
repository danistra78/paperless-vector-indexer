# Paperless-Vector-Indexer

![Python](https://img.shields.io/badge/Python-3.11-blue.svg?logo=python&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED.svg?logo=docker&logoColor=white)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)

Ein schlanker **One-Shot-Indexer**, der Dokumente aus [Paperless-ngx](https://docs.paperless-ngx.com/)
in eine [Qdrant](https://qdrant.tech/)-Vektordatenbank überführt und damit **semantische Suche** und
**RAG-Anwendungen** über dein Dokumentenarchiv ermöglicht. Statt eines dauerhaft laufenden Dienstes wird
der Indexer **ereignisgesteuert** (per Webhook / Post-consumption-Script) gestartet, verarbeitet nur neue
oder geänderte Dokumente und beendet sich anschließend wieder. Der komplette Zustand lebt in Qdrant – es
gibt **keine externen State-Dateien**.

## Architektur-Übersicht

```
                          (1) Dokument aufgenommen
   ┌───────────────┐        Webhook / Post-consume        ┌─────────────────────┐
   │  Paperless-ngx │ ───────────────────────────────────▶ │  Vector-Indexer     │
   │  (REST-API)    │ ◀─────────────────────────────────── │  (One-Shot Container)│
   └───────────────┘   (2) Dokumente + Volltext abrufen    └─────────┬───────────┘
                                                                      │
                                              (3) Chunk → Embedding    │
                                                                      ▼
                                                            ┌─────────────────────┐
                                                            │  Embedding-API      │
                                                            │  (OpenAI-kompatibel) │
                                                            │  Ollama / LocalAI    │
                                                            └─────────┬───────────┘
                                                                      │ (4) Vektor
                                                                      ▼
                                                            ┌─────────────────────┐
                                                            │  Qdrant             │
                                                            │  (Vektor-Datenbank)  │
                                                            └─────────────────────┘
```

1. Paperless-ngx nimmt ein Dokument auf und stößt den Indexer an.
2. Der Indexer ruft alle Dokumente samt Volltext paginiert über die REST-API ab.
3. Neue/geänderte Dokumente werden in überlappende Chunks zerlegt und einzeln embeddet.
4. Die Vektoren werden zusammen mit Metadaten als Points in Qdrant gespeichert.

## Features

- 🚀 **One-Shot-Betrieb** – kein Polling-Loop, kein Dauerdienst; läuft, wenn er gebraucht wird.
- 🔁 **Inkrementelle Indexierung** – Änderungserkennung per SHA-256-`content_hash`; unveränderte Dokumente werden übersprungen.
- ♻️ **Idempotent** – deterministische Point-IDs (`uuid5`), wiederholte Läufe erzeugen keine Duplikate.
- ✂️ **Wort-genaues Chunking** – Text wird an Wort-Grenzen mit konfigurierbarer Überlappung geteilt.
- 🔌 **OpenAI-kompatible Embeddings** – funktioniert mit Ollama, LocalAI, LM Studio & Co.
- 🗂️ **Reichhaltige Metadaten** – Titel, Korrespondent, Dokumenttyp, Tags und Datumsangaben landen im Qdrant-Payload.
- 🧠 **Zustandslos** – keine State-Dateien; der einzige Zustand ist der `content_hash` in Qdrant.
- 🐳 **Docker-ready** – minimales Image, per `docker compose run` gestartet.
- 💻 **CPU-only tauglich** – benötigt selbst keine GPU (Embeddings erledigt der externe Service).

## Voraussetzungen

- **Paperless-ngx** mit erreichbarer REST-API und einem API-Token (Einstellungen → API-Token).
- **Qdrant** (z. B. als Docker-Container `qdrant/qdrant`), erreichbar über HTTP.
- **Ein OpenAI-kompatibler Embedding-Endpunkt** mit Route `POST /v1/embeddings`, z. B.:
  - [Ollama](https://ollama.com/) (`/v1/embeddings`, z. B. Modell `nomic-embed-text`)
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

# --- Embedding-Service (OpenAI-kompatibel) ---
EMBEDDING_URL=http://embedding:8080/v1/embeddings
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
```

Damit `docker compose` die Werte lädt, referenziere die Datei in der `docker-compose.yaml`
(`env_file: .env`) oder übergib sie per `--env-file`.

### 2. Indexer einmalig ausführen

```bash
# Image bauen und One-Shot-Lauf starten
docker compose run --rm --env-file .env indexer
```

Der Container läuft genau einmal durch, verarbeitet alle neuen/geänderten Dokumente und beendet
sich anschließend (`restart: "no"`). Wiederhole den Aufruf jederzeit – bereits indexierte,
unveränderte Dokumente werden automatisch übersprungen.

## Umgebungsvariablen

| Variable            | Beschreibung                                                              | Default                                 |
|---------------------|---------------------------------------------------------------------------|-----------------------------------------|
| `PAPERLESS_URL`     | Basis-URL der Paperless-ngx-Instanz                                       | `http://paperless:8000`                 |
| `PAPERLESS_TOKEN`   | API-Token aus Paperless (**erforderlich**, sonst Abbruch)                 | *(leer)*                                |
| `EMBEDDING_URL`     | OpenAI-kompatibler Embeddings-Endpunkt (`POST /v1/embeddings`)            | `http://embedding:8080/v1/embeddings`   |
| `EMBEDDING_MODEL`   | Modellname, wird im Request mitgeschickt (falls gesetzt)                  | *(leer)*                                |
| `VECTOR_SIZE`       | Dimension der Embedding-Vektoren (muss zum Modell passen)                 | `1024`                                  |
| `QDRANT_URL`        | Basis-URL der Qdrant-Instanz                                              | `http://qdrant:6333`                    |
| `QDRANT_COLLECTION` | Name der Qdrant-Collection (wird bei Bedarf automatisch angelegt)         | `paperless`                             |
| `CHUNK_SIZE`        | Maximale Chunk-Größe in Zeichen                                           | `800`                                   |
| `CHUNK_OVERLAP`     | Überlappung zwischen aufeinanderfolgenden Chunks in Zeichen               | `150`                                   |
| `LOG_LEVEL`         | Log-Level (`INFO` oder `DEBUG`)                                           | `INFO`                                  |

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
   docker compose run --rm --env-file .env indexer
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
