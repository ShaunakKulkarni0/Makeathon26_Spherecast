# Spherecast Start Guide

## Voraussetzungen
- Du bist im Projektordner `Makeathon26_Spherecast`
- `.venv` ist vorhanden
- `OPENAI_API_KEY` ist in `.env` gesetzt

## Schnellstart (ein Befehl)
Im Projektordner:

```bash
python start_ui.py
```

Das startet:
- API auf `http://127.0.0.1:8001`
- Frontend auf `http://127.0.0.1:8000`

Beenden mit `Ctrl+C` (stoppt beide Prozesse).

## 1) Backend API starten
Im ersten Terminal:

```bash
cd /Users/valentinreinold/VSProjects/Makeathon26_Spherecast
.venv/bin/python -m uvicorn src.ui.api.main:app --host 127.0.0.1 --port 8001
```

Optionaler Health-Check (zweites Terminal):

```bash
curl http://127.0.0.1:8001/api/health
```

Erwartet: `{"status":"ok"}`

## 2) Frontend UI starten
Im zweiten Terminal:

```bash
cd /Users/valentinreinold/VSProjects/Makeathon26_Spherecast/src/ui/frontend
python -m http.server 8000
```

## 3) UI öffnen
Im Browser:

`http://localhost:8000`

## Hinweis zu den CSV-Daten
Die UI lädt Scoring-Daten bevorzugt aus:
- `data/scoring_capsuline_materials.csv`

Falls diese Runtime-Datei fehlt, wird auf das Test-Fallback zurückgegriffen:
- `tests/scoring/data/gesamt_materials.csv`
- `tests/scoring/data/gesamt_requirements.csv`
