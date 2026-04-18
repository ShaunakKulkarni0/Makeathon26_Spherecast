# CLAUDE.md — Scoring Modul

## Hinweis

Die vollständige Modul-Dokumentation liegt in `CLAUDE2.md`.
Diese Datei enthält die aktuelle, verbindliche Zusammenfassung der zentralen Änderung für Dimension 1.

## Dimension 1: Spec Similarity (40%)

Datei: `spec_similarity.py`

### Methode

Semantic Similarity via OpenAI Embeddings (`text-embedding-3-small`).

### Optimierung für Supplements/Lebensmittel

Spec Similarity ist auf semantische Austauschbarkeit optimiert:
- Synonyme (z. B. Glucose = Dextrose = Traubenzucker)
- Funktionsähnlichkeit (z. B. Süßungsmittel, Carrier)
- Kategorie-/Anwendungsnähe

### Algorithmus

1. `material_to_text(material)` erzeugt eine semantische Beschreibung aus Name, Synonymen, Funktion, Kategorie, Properties und Kurzbeschreibung.
2. Embeddings werden mit OpenAI (`text-embedding-3-small`) erzeugt.
3. Embedding-Cache wird über Text-Hash (`sha256`) genutzt, um doppelte API-Calls zu vermeiden.
4. Cosine Similarity wird auf Embedding-Vektoren berechnet.
5. Confidence wird aus Textqualität (Informationsdichte/Länge) plus Evidence Confidence berechnet.

### Environment

- API-Key wird via `python-dotenv` geladen.
- Erwartete Variable: `OPENAI_API_KEY`
- Fehlender Key führt zu fail-fast Fehler (kein stiller Fallback).
