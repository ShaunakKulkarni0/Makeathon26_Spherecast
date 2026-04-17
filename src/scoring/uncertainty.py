from __future__ import annotations
from dataclasses import dataclass
from enum import Enum

from .evidence import EvidenceTrail, EvidenceType


class UncertaintyLevel(Enum):
    VERY_LOW = "very_low"                    # > 90% Confidence
    LOW = "low"                              # 75–90%
    MEDIUM = "medium"                        # 50–75%
    HIGH = "high"                            # 25–50%
    VERY_HIGH = "very_high"                  # < 25%
    INSUFFICIENT_DATA = "insufficient_data"  # Zu wenig Daten


def confidence_to_uncertainty(confidence: float) -> UncertaintyLevel:
    if confidence >= 0.90:
        return UncertaintyLevel.VERY_LOW
    elif confidence >= 0.75:
        return UncertaintyLevel.LOW
    elif confidence >= 0.50:
        return UncertaintyLevel.MEDIUM
    elif confidence >= 0.25:
        return UncertaintyLevel.HIGH
    else:
        return UncertaintyLevel.VERY_HIGH


@dataclass
class UncertaintyReport:
    overall_level: UncertaintyLevel
    overall_confidence: float

    dimension_confidence: dict[str, float]
    dimension_uncertainty: dict[str, UncertaintyLevel]

    uncertainty_reasons: list[str]
    data_gaps: list[str]
    verification_suggestions: list[str]

    should_warn_user: bool
    warning_message: str | None


def generate_uncertainty_report(
    scores: dict[str, float],
    evidence_trails: dict[str, EvidenceTrail],
    weights: dict[str, float] | None = None,
) -> UncertaintyReport:
    """
    Generiert einen Uncertainty-Report basierend auf den Evidence Trails.

    Args:
        scores: Die 5 Dimension-Scores (nur für Kontext, nicht direkt benötigt)
        evidence_trails: Evidence Trail pro Dimension
        weights: Gewichte für Overall-Confidence-Berechnung

    Returns:
        UncertaintyReport mit Gründen, Gaps und Warnings
    """
    if weights is None:
        weights = {
            "spec": 0.40, "compliance": 0.25, "price": 0.15,
            "lead_time": 0.10, "quality": 0.10,
        }

    dimension_confidence: dict[str, float] = {}
    uncertainty_reasons: list[str] = []
    data_gaps: list[str] = []
    verification_suggestions: list[str] = []

    for dim, trail in evidence_trails.items():
        dimension_confidence[dim] = trail.overall_confidence

        if trail.overall_confidence < 0.5:
            if trail.data_completeness < 0.5:
                uncertainty_reasons.append(
                    f"{dim}: Unvollständige Daten ({trail.data_completeness:.0%})"
                )
                data_gaps.append(f"{dim}: Fehlende Datenpunkte")

            if trail.data_freshness == "outdated":
                uncertainty_reasons.append(f"{dim}: Veraltete Daten")
                verification_suggestions.append(
                    f"{dim}: Aktuelle Daten vom Lieferanten anfordern"
                )

            inferred_count = sum(
                1 for e in trail.evidences if e.type == EvidenceType.INFERRED
            )
            if trail.evidences and inferred_count > len(trail.evidences) / 2:
                uncertainty_reasons.append(f"{dim}: Überwiegend abgeleitete Daten")
                verification_suggestions.append(
                    f"{dim}: Direkte Bestätigung einholen"
                )

    weight_total = sum(weights.values())
    overall_confidence = sum(
        dimension_confidence.get(dim, 0.5) * w
        for dim, w in weights.items()
    ) / weight_total

    overall_level = confidence_to_uncertainty(overall_confidence)

    should_warn = overall_confidence < 0.5
    warning_message = None
    if should_warn:
        suggestions_text = ", ".join(verification_suggestions[:3])
        warning_message = (
            f"Achtung: Diese Empfehlung basiert auf unvollständigen Daten "
            f"(Confidence: {overall_confidence:.0%}). "
            f"Vor einer Entscheidung sollten folgende Punkte verifiziert werden: "
            f"{suggestions_text}"
        )

    return UncertaintyReport(
        overall_level=overall_level,
        overall_confidence=round(overall_confidence, 3),
        dimension_confidence=dimension_confidence,
        dimension_uncertainty={
            d: confidence_to_uncertainty(c) for d, c in dimension_confidence.items()
        },
        uncertainty_reasons=uncertainty_reasons,
        data_gaps=data_gaps,
        verification_suggestions=verification_suggestions,
        should_warn_user=should_warn,
        warning_message=warning_message,
    )


def calculate_uncertainty_adjusted_score(
    raw_score: float,
    confidence: float,
    min_confidence_threshold: float = 0.3,
) -> tuple[float, bool]:
    """
    Passt Score basierend auf Confidence an.

    Returns:
        (adjusted_score, is_reliable)
    """
    if confidence < min_confidence_threshold:
        return (raw_score * 0.5, False)

    dampening = 1 - (1 - confidence) * 0.2
    return (raw_score * dampening, True)
