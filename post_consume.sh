#!/bin/sh
# Post-Consume-Script fuer Paperless-ngx (PAPERLESS_POST_CONSUME_SCRIPT).
#
# Meldet das eben aufgenommene Dokument per HTTP an die Indexer-API
# (POST /index/<id>). Paperless braucht dafuer keinen Docker-Zugriff.
#
# Erwartet in der Umgebung des Paperless-Containers:
#   INDEXER_URL      z. B. http://192.168.0.4:8088
#   INDEXER_API_KEY  derselbe Wert wie INDEX_API_KEY der Indexer-API
# DOCUMENT_ID setzt Paperless selbst.
#
# Schlaegt der Aufruf fehl, endet das Script trotzdem mit 0: Die Aufnahme des
# Dokuments soll nicht am Indexer scheitern, der naechste Volllauf holt nach.

if [ -z "${DOCUMENT_ID:-}" ] || [ -z "${INDEXER_URL:-}" ] || [ -z "${INDEXER_API_KEY:-}" ]; then
    echo "post_consume: DOCUMENT_ID, INDEXER_URL oder INDEXER_API_KEY fehlt - uebersprungen" >&2
    exit 0
fi

if ! curl -fsS -m 30 -X POST \
        -H "X-API-Key: ${INDEXER_API_KEY}" \
        "${INDEXER_URL%/}/index/${DOCUMENT_ID}"; then
    echo "post_consume: Indexer nicht erreichbar, Dokument ${DOCUMENT_ID} folgt beim naechsten Volllauf" >&2
fi
exit 0
