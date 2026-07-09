# Paperless-Vector-Indexer

Ein schlanker **One-Shot-Indexer**, der Dokumente aus [Paperless-ngx](https://docs.paperless-ngx.com/)
in eine [Qdrant](https://qdrant.tech/)-Vektordatenbank indexiert – für semantische Suche / RAG.

Der Indexer läuft **einmalig** (kein Polling-Loop): Er wird per Webhook bzw.
Post-consumption-Script von Paperless gestartet, verarbeitet alle neuen oder
geänderten Dokumente und beendet sich danach wieder.

## Funktionsweise

1. Alle Dokumente werden über die Paperless-REST-API paginiert abgerufen.
2. Für jedes Dokument wird der `content_hash` (SHA-256 des Volltextes) mit dem
   bereits in Qdrant gespeicherten Hash verglichen:
   - **Unverändert** → übersprungen.
   - **Geändert** → alte Chunks werden gelöscht und das Dokument neu indexiert.
   - **Neu** → wird indexiert.
3. Der Volltext wird an Wort-Grenzen in überlappende Chunks zerlegt.
4. Pro Chunk wird ein Embedding über einen OpenAI-kompatiblen Endpunkt
   (`POST /v1/embeddings`) erzeugt und als Point in Qdrant gespeichert.

Es werden **keine externen State-Dateien** verwendet – der Zustand lebt
ausschließlich in Qdrant (über den `content_hash` im Payload).

### Qdrant-Payload pro Point

| Feld            | Typ  | Beschreibung                          |
|-----------------|------|---------------------------------------|
| `paperless_id`  | int  | Dokument-ID in Paperless              |
| `chunk_index`   | int  | Laufender Index des Chunks            |
| `content`       | str  | Text des Chunks                       |
| `content_hash`  | str  | SHA-256 des gesamten Dokumenttextes   |
| `title`         | str  | Dokumenttitel                         |
| `correspondent` | int  | Korrespondent-ID                      |
| `document_type` | int  | Dokumenttyp-ID                        |
| `tags`          | list | Tag-IDs                               |
| `created_date`  | str  | Erstellungsdatum                      |
| `modified_date` | str  | Änderungsdatum                        |

Die Point-ID wird deterministisch via `uuid5(namespace, "{paperless_id}_{chunk_index}")`
erzeugt, sodass wiederholte Läufe idempotent sind.

## Setup (docker-compose)

1. `docker-compose.yaml` anpassen (mindestens `PAPERLESS_TOKEN`, URLs und
   `EMBEDDING_MODEL`).
2. Image bauen und einmalig ausführen:

   ```bash
   docker compose run --rm indexer
   ```

   oder mit Build:

   ```bash
   docker compose build
   docker compose up indexer
   ```

Da der Service mit `restart: "no"` konfiguriert ist, läuft er genau einmal
durch und beendet sich anschließend.

## Umgebungsvariablen

| Variable            | Default                             | Beschreibung                                                        |
|---------------------|-------------------------------------|---------------------------------------------------------------------|
| `PAPERLESS_URL`     | `http://paperless:8000`             | Basis-URL der Paperless-ngx-Instanz                                 |
| `PAPERLESS_TOKEN`   | *(leer – erforderlich)*             | API-Token aus Paperless (Einstellungen → API-Token)                 |
| `EMBEDDING_URL`     | `http://embedding:8080/v1/embeddings` | OpenAI-kompatibler Embeddings-Endpunkt                            |
| `EMBEDDING_MODEL`   | *(leer)*                            | Modellname, wird im Request mitgeschickt (falls gesetzt)            |
| `VECTOR_SIZE`       | `1024`                              | Dimension der Embedding-Vektoren (muss zum Modell passen)           |
| `QDRANT_URL`        | `http://qdrant:6333`                | Basis-URL der Qdrant-Instanz                                        |
| `QDRANT_COLLECTION` | `paperless`                         | Name der Qdrant-Collection (wird bei Bedarf automatisch angelegt)   |
| `CHUNK_SIZE`        | `800`                               | Maximale Chunk-Größe in Zeichen                                     |
| `CHUNK_OVERLAP`     | `150`                               | Überlappung zwischen aufeinanderfolgenden Chunks in Zeichen         |
| `LOG_LEVEL`         | `INFO`                              | Log-Level (`INFO` oder `DEBUG`)                                     |

Wenn `PAPERLESS_TOKEN` nicht gesetzt ist, bricht der Indexer sofort mit einer
Fehlermeldung ab.

## Paperless Webhook-Konfiguration

Da der Indexer als One-Shot-Prozess läuft, kann er direkt aus Paperless heraus
gestartet werden.

### Variante A – Post-consumption-Script

Paperless kann nach jedem konsumierten Dokument ein Script ausführen
(`PAPERLESS_POST_CONSUME_SCRIPT`). Hinterlege dort ein kleines Wrapper-Script,
das den Indexer-Container startet:

```bash
#!/usr/bin/env bash
# /usr/src/paperless/scripts/post_consume_indexer.sh
docker compose -f /pfad/zu/paperless-vector-indexer/docker-compose.yaml run --rm indexer
```

In der Paperless-Konfiguration (`docker-compose.env` oder `paperless.conf`):

```
PAPERLESS_POST_CONSUME_SCRIPT=/usr/src/paperless/scripts/post_consume_indexer.sh
```

> Damit das Script den Docker-Host erreichen kann, muss der Docker-Socket im
> Paperless-Container verfügbar sein (`/var/run/docker.sock`).

### Variante B – Workflow-Webhook (Paperless-ngx ≥ 2.x)

Alternativ über **Einstellungen → Workflows → Aktion „Webhook"**: Lege einen
Workflow-Trigger (z. B. „Dokument hinzugefügt") an und rufe einen kleinen
HTTP-Endpunkt auf, der seinerseits `docker compose run --rm indexer` ausführt
(z. B. ein winziger Webhook-Empfänger). Der Indexer selbst benötigt keinen
laufenden Server, da er ohnehin alle Dokumente prüft und nur die Deltas
verarbeitet.

## Betrieb ohne GPU (NVIDIA P400 / CPU-only)

Der Indexer benötigt **keinen GPU-Zugriff**. Die rechenintensiven Embeddings
werden von einem **externen** Embedding-Service (`EMBEDDING_URL`) erzeugt – der
Indexer selbst führt nur HTTP-Requests, Chunking und Qdrant-Upserts aus.

Der Container läuft daher problemlos CPU-only. Eine vorhandene NVIDIA P400 muss
nicht an diesen Container durchgereicht werden; sie kann bei Bedarf
ausschließlich vom separaten Embedding-Service genutzt werden.
