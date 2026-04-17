# CLAUDE.md

## Projektübersicht
Substitution-Scoring-System für den TUM.ai Makeathon mit Spherecast.
Bewertet Ersatzmaterialien in 5 Dimensionen.

## Architektur
- Stufe 0: K.O.-Filter (filters/knockout.py)
- Stufe 1: 5D Scoring (scoring/*.py)
- Stufe 2: Composite Score (composite/scorer.py)

## Die 5 Dimensionen
1. Spec Similarity (40%) - Cosine Similarity auf normalisierten Property-Vektoren
2. Compliance (25%) - Set-Intersection für Zertifikate
3. Price Delta (15%) - Prozentuale Abweichung
4. Lead Time (10%) - Verhältnis-Score mit Tolerance
5. Quality Signals (10%) - Gewichteter Durchschnitt multipler Signale

## Code-Konventionen
- Python 3.11+
- Type Hints überall
- Docstrings im Google-Style
- Tests mit pytest

## Wichtige Entscheidungen
- K.O.-Filter vor Scoring (nicht während)
- Compliance: Critical Certs = K.O., restliche Certs = Score
- Alle Scores normalisiert auf [0, 1]
- Gewichte konfigurierbar

## Input-Format (von Agnes)
```python
{
    "name": str,
    "properties": {"prop_name": {"value": float, "unit": str}},
    "certifications": [str],
    "price": {"value": float, "unit": str},
    "lead_time": {"days": int, "reliability": float},
    "quality": {...},
    "moq": int,
    "country_of_origin": str,
    "incoterm": str  # EXW, FOB, DDP
}
