from __future__ import annotations
from dataclasses import dataclass

from shared.schemas import CrawledMaterial

from .evidence import Evidence, EvidenceType, EvidenceTrail, collect_evidence, build_evidence_trail


# Signal-Gewichte und Confidence-Faktoren laut Spezifikation
SIGNAL_CONFIG = {
    "supplier_rating":   {"weight": 0.25, "min_reviews": 100},
    "defect_rate":       {"weight": 0.25, "min_sample": 1000},
    "on_time_delivery":  {"weight": 0.20, "min_sample": 50},
    "audit_score":       {"weight": 0.15, "max_age_months": 24},
    "years_in_business": {"weight": 0.10},
    "sample_test":       {"weight": 0.05},
}


@dataclass
class SignalResult:
    score: float | None
    weight_used: float
    confidence: float
    notes: str
    evidence: Evidence


@dataclass
class QualitySignalsResult:
    score: float
    confidence: float
    evidence_trail: EvidenceTrail

    signals: dict[str, SignalResult]
    overall_confidence: float
    missing_signals: list[str]
    risk_factors: list[str]


def quality_signals_score(
    original: CrawledMaterial,
    kandidat: CrawledMaterial,
) -> QualitySignalsResult:
    """
    Berechnet Quality Signals Score mit Evidence Trail.

    Bewertet Lieferanten-Qualität anhand mehrerer Signale.
    Dynamische Gewichtsverteilung: Signale ohne Daten werden übersprungen
    und ihr Gewicht auf vorhandene Signale verteilt.

    Args:
        original: Nicht direkt genutzt, aber für zukünftige Vergleiche vorhanden
        kandidat: Der potenzielle Ersatz

    Returns:
        QualitySignalsResult mit Score, Confidence und Signal-Details
    """
    quality = kandidat.quality
    evidences: list[Evidence] = []
    signals: dict[str, SignalResult] = {}
    missing_signals: list[str] = []
    risk_factors: list[str] = []

    raw_scores: dict[str, tuple[float, float, float]] = {}  # signal → (score, confidence, weight)

    # --- Supplier Rating ---
    if quality.supplier_rating and quality.supplier_rating.get("value") is not None:
        rating = quality.supplier_rating["value"]
        review_count = quality.supplier_rating.get("review_count", 0)
        score = min(rating / 5.0, 1.0)
        confidence = 0.85 if review_count >= 100 else 0.6 if review_count >= 20 else 0.4
        ev = collect_evidence(
            field="supplier_rating",
            value=rating,
            source_type=EvidenceType.SUPPLIER_WEBSITE,
            source_url=kandidat.source_url,
            metadata={"sample_size": review_count, "notes": f"{review_count} Bewertungen"},
        )
        evidences.append(ev)
        signals["supplier_rating"] = SignalResult(score, SIGNAL_CONFIG["supplier_rating"]["weight"], confidence, f"Rating {rating}/5 ({review_count} Reviews)", ev)
        raw_scores["supplier_rating"] = (score, confidence, SIGNAL_CONFIG["supplier_rating"]["weight"])
    else:
        missing_signals.append("supplier_rating")

    # --- Defect Rate ---
    if quality.defect_rate and quality.defect_rate.get("value") is not None:
        defect = quality.defect_rate["value"]
        sample = quality.defect_rate.get("sample_size", 0)
        score = max(0.0, 1.0 - (defect / 5.0))
        confidence = 0.9 if sample >= 1000 else 0.7 if sample >= 100 else 0.5
        if defect > 2.0:
            risk_factors.append(f"Hohe Ausschussrate: {defect}%")
        ev = collect_evidence(
            field="defect_rate",
            value=defect,
            source_type=EvidenceType.HISTORICAL_PROCUREMENT,
            metadata={"sample_size": sample, "notes": f"Defektrate {defect}% bei n={sample}"},
        )
        evidences.append(ev)
        signals["defect_rate"] = SignalResult(score, SIGNAL_CONFIG["defect_rate"]["weight"], confidence, f"Defektrate {defect}% (n={sample})", ev)
        raw_scores["defect_rate"] = (score, confidence, SIGNAL_CONFIG["defect_rate"]["weight"])
    else:
        missing_signals.append("defect_rate")

    # --- On-Time Delivery ---
    if quality.on_time_delivery and quality.on_time_delivery.get("value") is not None:
        otd = quality.on_time_delivery["value"]
        sample = quality.on_time_delivery.get("sample_size", 0)
        score = otd / 100.0
        confidence = 0.85 if sample >= 50 else 0.6
        if otd < 80:
            risk_factors.append(f"Niedrige Pünktlichkeit: {otd}%")
        ev = collect_evidence(
            field="on_time_delivery",
            value=otd,
            source_type=EvidenceType.HISTORICAL_PROCUREMENT,
            metadata={"sample_size": sample, "notes": f"Pünktlichkeit {otd}%"},
        )
        evidences.append(ev)
        signals["on_time_delivery"] = SignalResult(score, SIGNAL_CONFIG["on_time_delivery"]["weight"], confidence, f"Pünktlich: {otd}%", ev)
        raw_scores["on_time_delivery"] = (score, confidence, SIGNAL_CONFIG["on_time_delivery"]["weight"])
    else:
        missing_signals.append("on_time_delivery")

    # --- Audit Score ---
    if quality.audit_score and quality.audit_score.get("value") is not None:
        audit = quality.audit_score["value"]
        age_months = quality.audit_score.get("age_months", 0)
        score = audit / 100.0
        confidence = 0.95 if age_months <= 12 else 0.75 if age_months <= 24 else 0.4
        if age_months > 24:
            risk_factors.append(f"Audit veraltet ({age_months} Monate)")
        ev = collect_evidence(
            field="audit_score",
            value=audit,
            source_type=EvidenceType.CERTIFICATION_DB,
            metadata={"age_days": age_months * 30, "notes": f"Audit-Score {audit}/100 ({age_months}M alt)"},
        )
        evidences.append(ev)
        signals["audit_score"] = SignalResult(score, SIGNAL_CONFIG["audit_score"]["weight"], confidence, f"Audit {audit}/100 ({age_months}M)", ev)
        raw_scores["audit_score"] = (score, confidence, SIGNAL_CONFIG["audit_score"]["weight"])
    else:
        missing_signals.append("audit_score")

    # --- Years in Business ---
    if quality.years_in_business is not None:
        years = quality.years_in_business
        score = min(years / 10.0, 1.0)
        ev = collect_evidence(
            field="years_in_business",
            value=years,
            source_type=EvidenceType.SUPPLIER_DATABASE,
            source_url=kandidat.source_url,
        )
        evidences.append(ev)
        signals["years_in_business"] = SignalResult(score, SIGNAL_CONFIG["years_in_business"]["weight"], 1.0, f"{years} Jahre im Geschäft", ev)
        raw_scores["years_in_business"] = (score, 1.0, SIGNAL_CONFIG["years_in_business"]["weight"])
    else:
        missing_signals.append("years_in_business")

    # --- Sample Test (aus audit_score nutzen als Proxy) ---
    sample_passed = (
        quality.audit_score is not None and quality.audit_score.get("passed") is True
    ) if quality.audit_score else None

    if sample_passed is not None:
        score = 1.0 if sample_passed else 0.0
        ev = collect_evidence(
            field="sample_test",
            value=sample_passed,
            source_type=EvidenceType.HISTORICAL_PROCUREMENT,
        )
        evidences.append(ev)
        signals["sample_test"] = SignalResult(score, SIGNAL_CONFIG["sample_test"]["weight"], 1.0, "Sample-Test bestanden" if sample_passed else "Sample-Test nicht bestanden", ev)
        raw_scores["sample_test"] = (score, 1.0, SIGNAL_CONFIG["sample_test"]["weight"])
    else:
        missing_signals.append("sample_test")

    # --- Composite Score (dynamische Gewichte) ---
    if not raw_scores:
        trail = build_evidence_trail("quality_signals", [], 6)
        return QualitySignalsResult(
            score=0.0,
            confidence=0.0,
            evidence_trail=trail,
            signals=signals,
            overall_confidence=0.0,
            missing_signals=list(SIGNAL_CONFIG.keys()),
            risk_factors=["Keine Qualitätsdaten verfügbar"],
        )

    total_weight = sum(w for _, _, w in raw_scores.values())
    weighted_score = sum(s * w for s, _, w in raw_scores.values()) / total_weight
    weighted_confidence = sum(c * w for _, c, w in raw_scores.values()) / total_weight

    trail = build_evidence_trail("quality_signals", evidences, total_expected_fields=6)

    return QualitySignalsResult(
        score=round(weighted_score, 4),
        confidence=round(weighted_confidence, 3),
        evidence_trail=trail,
        signals=signals,
        overall_confidence=round(weighted_confidence, 3),
        missing_signals=missing_signals,
        risk_factors=risk_factors,
    )
