from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Any


# ---------------------------------------------------------------------------
# Base Material Structures
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# User Input Schemas
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# BOM Consolidation Schemas
# ---------------------------------------------------------------------------

@dataclass
class BOMEntry:
    material_id: str
    material_name: str
    quantity_per_month: float
    current_supplier: str
    current_price: float


@dataclass
class ProcurementRecord:
    material_id: str
    supplier: str
    quantity: float
    price: float
    date: str


@dataclass
class ConsolidationGoals:
    max_suppliers_per_category: int = 2
    min_savings_percent: float = 5.0
    allow_spec_deviation_percent: float = 10.0


@dataclass
class BOMContext:
    company_boms: dict[str, list[BOMEntry]]
    historical_procurement: list[ProcurementRecord]
    consolidation_goals: ConsolidationGoals = field(default_factory=ConsolidationGoals)


# ---------------------------------------------------------------------------
# Scoring Result Schemas
# ---------------------------------------------------------------------------

@dataclass
class ScoredCandidate:
    kandidat: CrawledMaterial
    scores: dict[str, float]
    composite_score: float
    confidences: dict[str, float] = field(default_factory=dict)
    overall_confidence: float = 0.5
    evidence_trails: dict[str, Any] = field(default_factory=dict)   # dict[str, EvidenceTrail]
    uncertainty_report: Any = None                                   # UncertaintyReport
    rank: int | None = None
    explanation: Any = None                                          # Explanation
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class RejectedCandidate:
    candidate: CrawledMaterial
    reasons: list[str]
    evidence: list[Any] = field(default_factory=list)               # list[Evidence]


@dataclass
class ScoringMetadata:
    weights: dict[str, float]
    total_candidates: int
    passed_knockout: int
    average_confidence: float = 0.0


@dataclass
class ScoringResult:
    original: CrawledMaterial
    top_candidates: list[ScoredCandidate]
    rejected: list[RejectedCandidate]
    metadata: ScoringMetadata
    consolidation: Any = None                                        # ConsolidationResult | None
