from __future__ import annotations
import math
from dataclasses import dataclass

from shared.schemas import CrawledMaterial
from shared.constants import PROPERTY_RANGES

from .evidence import Evidence, EvidenceType, EvidenceTrail, collect_evidence, build_evidence_trail


@dataclass
class PropertyComparison:
    original_value: float
    kandidat_value: float
    original_normalized: float
    kandidat_normalized: float
    diff_percent: float
    original_evidence: Evidence
    kandidat_evidence: Evidence


@dataclass
class SpecSimilarityResult:
    score: float
    confidence: float
    evidence_trail: EvidenceTrail

    common_props: list[str]
    missing_in_kandidat: list[str]
    extra_in_kandidat: list[str]
    details: dict[str, PropertyComparison]


def _normalize(value: float, prop_name: str, vec_min: float, vec_max: float) -> float:
    """Min-Max Normalisierung. Nutzt PROPERTY_RANGES wenn verfügbar."""
    ranges = PROPERTY_RANGES.get(prop_name)
    if ranges:
        lo, hi = ranges["min"], ranges["max"]
    else:
        lo, hi = vec_min, vec_max

    if hi == lo:
        return 0.5
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x ** 2 for x in a))
    mag_b = math.sqrt(sum(x ** 2 for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def spec_similarity(
    original: CrawledMaterial,
    kandidat: CrawledMaterial,
) -> SpecSimilarityResult:
    """
    Berechnet Spec Similarity zwischen zwei Materialien.
    Sammelt Evidence für alle verglichenen Properties.

    Args:
        original: Das zu ersetzende Material
        kandidat: Der potenzielle Ersatz

    Returns:
        SpecSimilarityResult mit Score, Confidence und Evidence Trail
    """
    orig_keys = set(original.properties.keys())
    kand_keys = set(kandidat.properties.keys())

    common = sorted(orig_keys & kand_keys)
    missing_in_kandidat = sorted(orig_keys - kand_keys)
    extra_in_kandidat = sorted(kand_keys - orig_keys)

    if not common:
        trail = build_evidence_trail("spec_similarity", [], total_expected_fields=len(orig_keys))
        return SpecSimilarityResult(
            score=0.0,
            confidence=0.0,
            evidence_trail=trail,
            common_props=[],
            missing_in_kandidat=list(orig_keys),
            extra_in_kandidat=list(kand_keys),
            details={},
        )

    orig_vals = [original.properties[p].value for p in common]
    kand_vals = [kandidat.properties[p].value for p in common]

    vec_orig_norm: list[float] = []
    vec_kand_norm: list[float] = []
    details: dict[str, PropertyComparison] = {}
    evidences: list[Evidence] = []

    for i, prop in enumerate(common):
        ov = orig_vals[i]
        kv = kand_vals[i]
        lo = min(ov, kv)
        hi = max(ov, kv)

        on = _normalize(ov, prop, lo, hi)
        kn = _normalize(kv, prop, lo, hi)
        vec_orig_norm.append(on)
        vec_kand_norm.append(kn)

        diff = abs(ov - kv) / ov * 100 if ov != 0 else 0.0

        orig_source = original.source_url or EvidenceType.SUPPLIER_DATABASE.value
        kand_source = kandidat.source_url or EvidenceType.SUPPLIER_DATABASE.value

        orig_ev = collect_evidence(
            field=prop,
            value=ov,
            source_type=EvidenceType.SUPPLIER_DATABASE,
            source_url=original.source_url,
        )
        kand_ev = collect_evidence(
            field=prop,
            value=kv,
            source_type=EvidenceType.SUPPLIER_DATABASE,
            source_url=kandidat.source_url,
        )
        evidences.extend([orig_ev, kand_ev])

        details[prop] = PropertyComparison(
            original_value=ov,
            kandidat_value=kv,
            original_normalized=on,
            kandidat_normalized=kn,
            diff_percent=round(diff, 2),
            original_evidence=orig_ev,
            kandidat_evidence=kand_ev,
        )

    score = _cosine_similarity(vec_orig_norm, vec_kand_norm)

    # Confidence: reduzieren wenn viele Properties fehlen
    completeness = len(common) / len(orig_keys) if orig_keys else 1.0
    trail = build_evidence_trail(
        "spec_similarity",
        evidences,
        total_expected_fields=len(orig_keys) * 2,
    )
    confidence = trail.overall_confidence * completeness

    return SpecSimilarityResult(
        score=round(score, 4),
        confidence=round(confidence, 3),
        evidence_trail=trail,
        common_props=common,
        missing_in_kandidat=missing_in_kandidat,
        extra_in_kandidat=extra_in_kandidat,
        details=details,
    )
