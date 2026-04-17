from __future__ import annotations
from dataclasses import dataclass

from shared.constants import WEIGHT_PRESETS


@dataclass
class CompositeResult:
    score: float
    confidence: float
    dimension_scores: dict[str, float]
    dimension_confidences: dict[str, float]
    effective_weights: dict[str, float]


def calculate_composite_score(
    dimension_scores: dict[str, float],
    dimension_confidences: dict[str, float],
    weights: dict[str, float] | None = None,
) -> CompositeResult:
    """
    Berechnet Confidence-gewichteten Composite Score.

    Formel:
        composite = Σ (weight_i × score_i × confidence_i) / Σ (weight_i × confidence_i)

    Bei niedriger Confidence wird der Score gedämpft.

    Args:
        dimension_scores: Score pro Dimension (0.0–1.0)
        dimension_confidences: Confidence pro Dimension (0.0–1.0)
        weights: Optionale Gewichte; Standard ist "default" Preset

    Returns:
        CompositeResult mit Gesamt-Score und Confidence
    """
    if weights is None:
        weights = WEIGHT_PRESETS["default"]

    weighted_sum = 0.0
    weight_sum = 0.0
    effective_weights: dict[str, float] = {}

    for dim, weight in weights.items():
        score = dimension_scores.get(dim, 0.0)
        confidence = dimension_confidences.get(dim, 0.5)

        effective_weight = weight * confidence
        weighted_sum += score * effective_weight
        weight_sum += effective_weight
        effective_weights[dim] = round(effective_weight, 4)

    if weight_sum == 0:
        return CompositeResult(
            score=0.0,
            confidence=0.0,
            dimension_scores=dimension_scores,
            dimension_confidences=dimension_confidences,
            effective_weights=effective_weights,
        )

    composite_score = weighted_sum / weight_sum

    overall_confidence = sum(
        weights[d] * dimension_confidences.get(d, 0.5)
        for d in weights
    ) / sum(weights.values())

    return CompositeResult(
        score=round(composite_score, 4),
        confidence=round(overall_confidence, 3),
        dimension_scores=dimension_scores,
        dimension_confidences=dimension_confidences,
        effective_weights=effective_weights,
    )
