# CLAUDE.md — Shared Module

## Überblick

Dieses Modul enthält alle gemeinsamen Definitionen, Schemas und Konstanten. Es ist der **Vertrag** zwischen allen Modulen. Änderungen hier müssen mit dem gesamten Team abgestimmt werden.

## Dateien

| Datei | Inhalt |
|-------|--------|
| schemas.py | Alle Datenstrukturen (CrawledMaterial, ScoringResult, etc.) |
| constants.py | Gemeinsame Konstanten (Gewichte, Schwellwerte, etc.) |

## schemas.py — Datenstrukturen

### CrawledMaterial (Crawling → Scoring)

```python
@dataclass
class MaterialProperty:
    value: float
    unit: str

@dataclass
class PriceInfo:
    value: float
    unit: str
    tiers: list[dict] | None = None

@dataclass
class LeadTimeInfo:
    days: int
    reliability: float
    type: str  # "stock", "express", "standard", "unknown"

@dataclass
class QualityInfo:
    supplier_rating: dict | None = None
    defect_rate: dict | None = None
    on_time_delivery: dict | None = None
    years_in_business: int | None = None
    audit_score: dict | None = None

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
    source_url: str | None = None
```

### ScoringResult (Scoring → UI)

```python
@dataclass
class ScoredCandidate:
    kandidat: CrawledMaterial
    composite_score: float
    scores: dict[str, float]   # spec, compliance, price, lead_time, quality
    rank: int | None = None
    explanation: Explanation | None = None

@dataclass
class RejectedCandidate:
    candidate: CrawledMaterial
    reasons: list[str]

@dataclass
class ScoringResult:
    original: CrawledMaterial
    top_candidates: list[ScoredCandidate]
    rejected: list[RejectedCandidate]
    metadata: dict
```

### User Input Schemas

```python
@dataclass
class MaterialQuery:
    name: str
    category: str
    properties: dict[str, MaterialProperty] | None = None
    certifications: list[str] | None = None

@dataclass
class SearchCriteria:
    category: str
    application: str | None = None
    max_results: int = 50

@dataclass
class UserRequirements:
    max_quantity: int | None = None
    destination_country: str = "DE"
    critical_certs: list[str] | None = None
    max_lead_time_days: int | None = None
    max_price_multiplier: float = 2.0

@dataclass
class UserPreferences:
    priority_properties: list[str] | None = None
    weight_preset: str = "default"
```

## constants.py — Gemeinsame Konstanten

```python
DEFAULT_WEIGHTS = {
    "spec": 0.40,
    "compliance": 0.25,
    "price": 0.15,
    "lead_time": 0.10,
    "quality": 0.10,
}

MAX_KNOCKOUT_CANDIDATES = 15
DEFAULT_TOP_N = 5
DEFAULT_DESTINATION_COUNTRY = "DE"
DEFAULT_MAX_PRICE_MULTIPLIER = 2.0
```

## Wichtig

- Änderungen an schemas.py **immer zuerst im Team besprechen**
- Alle Module importieren ihre Types aus diesem Modul
- Keine Logik hier — nur Datenstrukturen und Konstanten
