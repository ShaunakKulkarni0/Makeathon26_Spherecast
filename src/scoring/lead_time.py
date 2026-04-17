from __future__ import annotations
from dataclasses import dataclass

from shared.schemas import CrawledMaterial
from shared.constants import INCOTERM_ADJUSTMENTS

from .evidence import Evidence, EvidenceType, EvidenceTrail, collect_evidence, build_evidence_trail


@dataclass
class LeadTimeResult:
    score: float
    confidence: float
    evidence_trail: EvidenceTrail

    base_score: float
    days_original: int
    days_kandidat: int
    days_difference: int
    direction: str
    percent_change: float
    reliability_original: float
    reliability_kandidat: float
    risk_level: str
    tolerance_applied: bool

    lead_time_evidence: Evidence
    reliability_evidence: Evidence | None
    stock_evidence: Evidence | None


def _determine_risk_level(
    days_difference: int,
    percent_change: float,
    reliability: float,
    confidence: float,
) -> str:
    if confidence < 0.5:
        return "high"
    if days_difference <= 0:
        return "low"
    if days_difference <= 3 and reliability >= 0.9:
        return "low"
    if days_difference <= 7 and reliability >= 0.8:
        return "medium"
    if percent_change > 100 or reliability < 0.7:
        return "critical"
    return "high"


def lead_time_score(
    original: CrawledMaterial,
    kandidat: CrawledMaterial,
    tolerance_days: int = 2,
) -> LeadTimeResult:
    """
    Berechnet Lead Time Score mit Evidence Trail.

    Berücksichtigt Incoterm-Zeitaufschläge, Lagerbestand und Zuverlässigkeit.

    Args:
        original: Das Original-Material
        kandidat: Der potenzielle Ersatz
        tolerance_days: Toleranzbereich in Tagen (innerhalb = kein Abzug)

    Returns:
        LeadTimeResult mit Score, Confidence und Evidence
    """
    evidences: list[Evidence] = []

    days_orig = original.lead_time.days
    days_kand = kandidat.lead_time.days

    reliability_orig = original.lead_time.reliability
    reliability_kand = kandidat.lead_time.reliability

    # Evidence für Lead Time Quellen
    lt_source = EvidenceType.SUPPLIER_DATABASE
    lt_ev = collect_evidence(
        field="lead_time",
        value=days_kand,
        source_type=lt_source,
        source_url=kandidat.source_url,
        metadata={"notes": f"Lieferzeit {kandidat.lead_time.type}"},
    )
    evidences.append(lt_ev)

    # Reliability Evidence
    rel_ev: Evidence | None = None
    if reliability_kand < 1.0:
        rel_ev = collect_evidence(
            field="reliability",
            value=reliability_kand,
            source_type=EvidenceType.HISTORICAL_PROCUREMENT,
            metadata={"notes": "Pünktlichkeitsrate aus historischen Daten"},
        )
        evidences.append(rel_ev)

    # Stock Check — wenn auf Lager, schnellere Lieferung
    stock_ev: Evidence | None = None
    if kandidat.lead_time.type == "stock":
        days_kand = min(days_kand, 3)
        stock_ev = collect_evidence(
            field="stock",
            value=True,
            source_type=EvidenceType.SUPPLIER_DATABASE,
            source_url=kandidat.source_url,
            metadata={"notes": "Material auf Lager verfügbar"},
        )
        evidences.append(stock_ev)

    # Incoterm Zeitaufschlag
    incoterm_info = INCOTERM_ADJUSTMENTS.get(kandidat.incoterm, INCOTERM_ADJUSTMENTS["DDP"])
    days_kand += incoterm_info["time_adder"]

    if incoterm_info["time_adder"] > 0:
        inco_ev = collect_evidence(
            field="incoterm_time_adder",
            value=incoterm_info["time_adder"],
            source_type=EvidenceType.CALCULATED,
            metadata={"notes": f"Incoterm {kandidat.incoterm}: +{incoterm_info['time_adder']} Tage"},
        )
        evidences.append(inco_ev)

    # Score Berechnung
    tolerance_applied = False
    days_diff = days_kand - days_orig

    if abs(days_diff) <= tolerance_days:
        base_score = 1.0
        tolerance_applied = True
    elif days_diff <= 0:
        base_score = 1.0
    else:
        max_acceptable = days_orig * 2 if days_orig > 0 else 30
        base_score = max(0.0, 1.0 - (days_diff / max_acceptable))

    # Reliability-Adjustment
    score = base_score * reliability_kand

    percent_change = (
        ((days_kand - days_orig) / days_orig * 100) if days_orig > 0 else 0.0
    )
    direction = "faster" if days_diff < 0 else "equal" if days_diff == 0 else "slower"

    trail = build_evidence_trail("lead_time", evidences, total_expected_fields=3)
    confidence = trail.overall_confidence

    risk = _determine_risk_level(days_diff, percent_change, reliability_kand, confidence)

    return LeadTimeResult(
        score=round(score, 4),
        confidence=round(confidence, 3),
        evidence_trail=trail,
        base_score=round(base_score, 4),
        days_original=days_orig,
        days_kandidat=days_kand,
        days_difference=days_diff,
        direction=direction,
        percent_change=round(percent_change, 2),
        reliability_original=reliability_orig,
        reliability_kandidat=reliability_kand,
        risk_level=risk,
        tolerance_applied=tolerance_applied,
        lead_time_evidence=lt_ev,
        reliability_evidence=rel_ev,
        stock_evidence=stock_ev,
    )
