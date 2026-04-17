# CLAUDE.md

## Projekt: Spherecast Substitute Finder

TUM.ai Makeathon 2026 — Material-Substitution mit Agnes AI (Spherecast)

Ein System zur automatisierten Bewertung und Empfehlung von Ersatzmaterialien basierend auf einem 5-dimensionalen Scoring-Modell.

## Team-Struktur

| Modul | Verantwortung | Ordner |
|-------|---------------|--------|
| Crawling | Daten von Agnes holen, normalisieren | src/crawling/ |
| Scoring | 5D Bewertungssystem, K.O.-Filter, Ranking | src/scoring/ |
| UI | API-Endpunkte, Frontend, Demo | src/ui/ |

Jedes Modul hat eine eigene CLAUDE.md mit detaillierter Dokumentation:
- src/crawling/CLAUDE.md
- src/scoring/CLAUDE.md
- src/ui/CLAUDE.md

## Architektur-Überblick

```
USER INPUT                      CRAWLING                    SCORING                     UI
(Original-Material,       →     (Agnes API,           →     (K.O.-Filter,         →     (API Server,
 Suchkriterien,                  Normalizer)                 5D Scoring,                 Frontend,
 Anforderungen)                                              Ranking)                    Demo)

                                OUTPUT:                      OUTPUT:                     OUTPUT:
                                list[CrawledMaterial]        ScoringResult               Visualisierung
```

## Projektstruktur

```
spherecast-substitute-finder/
├── CLAUDE.md                        # Diese Datei (Haupt-Dokumentation)
├── README.md
├── requirements.txt
├── pyproject.toml
│
├── shared/                          # GEMEINSAME DEFINITIONEN
│   ├── CLAUDE.md                    # Dokumentation der Schnittstellen
│   ├── __init__.py
│   ├── schemas.py                   # Datenstrukturen (DER VERTRAG!)
│   └── constants.py                 # Gemeinsame Konstanten
│
├── src/
│   ├── __init__.py
│   │
│   ├── crawling/                    # MODUL 1: CRAWLING
│   │   ├── CLAUDE.md                # Detaillierte Modul-Dokumentation
│   │   ├── __init__.py
│   │   ├── agnes_connector.py       # Agnes API Anbindung
│   │   └── data_normalizer.py       # Response zu CrawledMaterial
│   │
│   ├── scoring/                     # MODUL 2: SCORING
│   │   ├── CLAUDE.md                # Detaillierte Modul-Dokumentation
│   │   ├── __init__.py
│   │   ├── knockout.py              # Stufe 0: K.O.-Filter
│   │   ├── spec_similarity.py       # Dimension 1 (40%)
│   │   ├── compliance.py            # Dimension 2 (25%)
│   │   ├── price_delta.py           # Dimension 3 (15%)
│   │   ├── lead_time.py             # Dimension 4 (10%)
│   │   ├── quality_signals.py       # Dimension 5 (10%)
│   │   ├── composite.py             # Composite Score Berechnung
│   │   └── pipeline.py              # Orchestrierung
│   │
│   └── ui/                          # MODUL 3: UI
│       ├── CLAUDE.md                # Detaillierte Modul-Dokumentation
│       ├── __init__.py
│       ├── api.py                   # FastAPI Endpunkte
│       └── components/              # Frontend-Komponenten
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                  # Pytest Fixtures
│   ├── mock_data.py                 # Mock-Daten für alle Module
│   ├── crawling/
│   ├── scoring/
│   └── ui/
│
└── examples/
    ├── demo.py                      # Makeathon Demo
    └── sample_materials.json        # Beispiel-Materialien
```

## Die Schnittstellen

Die Schnittstellen zwischen den Modulen sind in shared/schemas.py definiert. Das ist der Vertrag zwischen allen Modulen. Änderungen hier müssen mit dem Team abgestimmt werden.

### Schnittstelle 1: Crawling zu Scoring

```python
@dataclass
class CrawledMaterial:
    id: str
    name: str
    properties: dict[str, MaterialProperty]
    certifications: list[str]
    price: PriceInfo
    lead_time: LeadTimeInfo
    quality: QualityInfo
    moq: int
    country_of_origin: str
    incoterm: str
    source_url: Optional[str] = None
```

### Schnittstelle 2: Scoring zu UI

```python
@dataclass
class ScoringResult:
    original: CrawledMaterial
    top_candidates: list[ScoredCandidate]
    rejected: list[dict]
    metadata: dict
```

Vollständige Schema-Definitionen: Siehe shared/CLAUDE.md und shared/schemas.py

## Scoring-System: 5 Dimensionen

Das Herzstück des Projekts. Jede Dimension hat einen spezifischen Datentyp und eine passende Berechnungsmethode.

| Dim | Name | Gewicht | Datentyp | Methode |
|-----|------|---------|----------|---------|
| 1 | Spec Similarity | 40% | Numerische Properties | Cosine Similarity auf normalisierten Vektoren |
| 2 | Compliance | 25% | Kategorische Listen | Set-Intersection |
| 3 | Price Delta | 15% | Einzelner Zahlenwert | Prozentuale Abweichung mit Capping |
| 4 | Lead Time | 10% | Zeitwert | Verhältnis-Score mit Tolerance |
| 5 | Quality Signals | 10% | Multiple Signale | Gewichteter Durchschnitt mit Confidence |

### Scoring-Pipeline

```
Stufe 0: K.O.-Filter     → Harte Ausschlüsse (MOQ, Blacklist, Critical Certs)
Stufe 1: 5D Scoring      → Alle 5 Dimensionen berechnen
Stufe 2: Composite Score → Gewichtete Summe, Ranking, Explanation
```

Details: Siehe src/scoring/CLAUDE.md

## Crawling-Parameter

Diese Daten werden von Agnes gecrawlt und müssen in CrawledMaterial normalisiert werden.

### Konstante Parameter (Agnes crawlt automatisch)

| Parameter | Beschreibung | Fließt in |
|-----------|--------------|-----------|
| Price und Price Tiers | Preis inkl. Mengenrabatte | Price Delta |
| Lead Time | Lieferzeit in Tagen | Lead Time |
| Incoterms | EXW, FOB, DDP | Price Delta, Lead Time |
| MOQ | Minimum Order Quantity | K.O.-Filter |
| Compliance | Zertifikate | Compliance, K.O.-Filter |
| Stock | Lagerbestand | Lead Time |
| Country of Origin | Herkunftsland | Compliance (Tariffs), K.O.-Filter |

### Dynamische Parameter (User Input)

| Parameter | Beschreibung | Fließt in |
|-----------|--------------|-----------|
| Ontology-Assistant | Anwendungsspezifische Properties | Spec Similarity |
| User Preferences | Material-Properties und Ranges | Spec Similarity |

Details: Siehe src/crawling/CLAUDE.md

## Code-Konventionen

### Python

- Version: 3.11+
- Type Hints: Überall, dataclasses aus shared/schemas.py verwenden
- Docstrings: Google-Style
- Formatting: Black (line-length=100)
- Linting: Ruff

### Beispiel

```python
from shared.schemas import CrawledMaterial, ScoringResult

def score_candidates(
    original: CrawledMaterial,
    candidates: list[CrawledMaterial],
    weights: dict[str, float] | None = None
) -> ScoringResult:
    """
    Bewertet Kandidaten gegen das Original-Material.
    
    Args:
        original: Das zu ersetzende Material
        candidates: Liste der potenziellen Ersatzmaterialien
        weights: Optionale Gewichte für die 5 Dimensionen
        
    Returns:
        ScoringResult mit Top-Kandidaten und Explanations
    """
    ...
```

### Testing

- Framework: pytest
- Struktur: Tests spiegeln src/ Struktur
- Naming: test_<function_name>_<scenario>
- Mock-Daten: In tests/mock_data.py

## Entwicklungs-Workflow

### Git-Workflow

```
main                 ← Stable, immer lauffähig
├── feature/crawling ← Person 1
├── feature/scoring  ← Person 2
└── feature/ui       ← Person 3
```

### Regeln

1. Schema-Änderungen: Immer erst in shared/schemas.py, dann Team informieren
2. Eigener Branch: Jeder arbeitet auf seinem Feature-Branch
3. Merge zu main: Nur nach Review und wenn Tests grün sind
4. Mock-Daten: Nutzen um parallel zu arbeiten

### Kommunikation bei Schnittstellenänderungen

1. Änderung in shared/schemas.py vorschlagen
2. Im Team besprechen
3. Alle bestätigen
4. Änderung committen
5. Alle pullen und ihre Module anpassen

## Befehle

### Setup

```bash
git clone <repo-url>
cd spherecast-substitute-finder

python -m venv venv
source venv/bin/activate  # Linux/Mac
# oder: venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

### Development

```bash
pytest                           # Alle Tests
pytest tests/scoring/ -v         # Nur Scoring-Tests
pytest -k "test_spec"            # Tests mit "spec" im Namen

black src/ tests/                # Formatting
ruff check src/ tests/           # Linting
mypy src/                        # Type Checking
```

### Demo starten

```bash
python examples/demo.py
```

## Modul-Dokumentation

Für detaillierte Informationen zu jedem Modul, siehe die jeweilige CLAUDE.md:

| Modul | Dokumentation | Inhalt |
|-------|---------------|--------|
| Shared | shared/CLAUDE.md | Schema-Definitionen, Datenstrukturen |
| Crawling | src/crawling/CLAUDE.md | Agnes API, Normalisierung, Output-Format |
| Scoring | src/scoring/CLAUDE.md | K.O.-Filter, 5D Scoring, Pipeline |
| UI | src/ui/CLAUDE.md | API-Endpunkte, Frontend, Demo-Features |

## Wichtige Design-Entscheidungen

| Entscheidung | Begründung |
|--------------|------------|
| K.O.-Filter VOR Scoring | Performance: Nicht unnötig scoren |
| Alle Scores auf 0 bis 1 | Einheitlich, leicht zu gewichten |
| Gewichte konfigurierbar | Demo-Feature für Makeathon |
| Schemas in shared/ | Single Source of Truth für Schnittstellen |
| Mock-Daten für alle | Ermöglicht parallele Entwicklung |

## Nächste Schritte

1. shared/schemas.py finalisieren (gemeinsam)
2. Projektstruktur anlegen
3. Modul-CLAUDE.md Files erstellen
4. Mock-Daten erstellen
5. Parallel entwickeln
6. Integration
7. Demo vorbereiten