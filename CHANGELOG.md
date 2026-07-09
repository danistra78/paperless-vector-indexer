# Changelog

## [Unreleased]

### Hinzugefügt
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
