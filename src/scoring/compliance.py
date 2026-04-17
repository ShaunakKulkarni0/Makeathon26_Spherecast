from __future__ import annotations
from dataclasses import dataclass

from shared.schemas import CrawledMaterial
from shared.constants import CERTIFICATION_VERIFICATION

from .evidence import Evidence, EvidenceType, EvidenceTrail, collect_evidence, build_evidence_trail


@dataclass
class ComplianceResult:
    score: float
    confidence: float
    evidence_trail: EvidenceTrail

    matched: list[str]
    missing: list[str]
    extra: list[str]
    coverage: str

    certification_evidence: dict[str, Evidence]
    verified_certs: list[str]
    claimed_only_certs: list[str]


def compliance_score(
    original: CrawledMaterial,
    kandidat: CrawledMaterial,
) -> ComplianceResult:
    """
    Berechnet Compliance Match mit Evidence Trail.

    Critical Certifications wurden bereits im K.O.-Filter geprüft.
    Hier geht es um den Grad der Übereinstimmung aller Zertifikate.

    Args:
        original: Das zu ersetzende Material (definiert die Required-Certs)
        kandidat: Der potenzielle Ersatz

    Returns:
        ComplianceResult mit Score, Confidence und Evidence pro Zertifikat
    """
    required = set(original.certifications)
    available = set(kandidat.certifications)

    matched = sorted(required & available)
    missing = sorted(required - available)
    extra = sorted(available - required)

    score = len(matched) / len(required) if required else 1.0

    evidences: list[Evidence] = []
    certification_evidence: dict[str, Evidence] = {}
    verified_certs: list[str] = []
    claimed_only_certs: list[str] = []

    all_relevant = sorted(required | available)
    for cert in all_relevant:
        cert_info = CERTIFICATION_VERIFICATION.get(cert)

        if cert_info and not cert_info.get("self_declaration", True):
            # Kann offiziell verifiziert werden
            source = cert_info["verification_sources"][0]
            ev = collect_evidence(
                field="certification",
                value=cert if cert in available else None,
                source_type=EvidenceType.CERTIFICATION_DB,
                source_url=source,
                metadata={"notes": f"{cert} aus offizieller Datenbank"},
            )
            if cert in available:
                verified_certs.append(cert)
        else:
            # Nur vom Supplier behauptet
            ev = collect_evidence(
                field="certification",
                value=cert if cert in available else None,
                source_type=EvidenceType.SUPPLIER_WEBSITE,
                source_url=kandidat.source_url,
                metadata={"notes": f"{cert}: Selbstdeklaration des Lieferanten"},
            )
            if cert in available:
                claimed_only_certs.append(cert)

        evidences.append(ev)
        certification_evidence[cert] = ev

    if score >= 1.0:
        coverage = "full"
    elif score >= 0.75:
        coverage = "high"
    elif score >= 0.5:
        coverage = "medium"
    else:
        coverage = "low"

    trail = build_evidence_trail(
        "compliance",
        evidences,
        total_expected_fields=len(all_relevant),
    )

    # Confidence reduzieren wenn viele Certs nur behauptet (nicht verifiziert)
    if all_relevant:
        verified_ratio = len(verified_certs) / len(all_relevant)
        confidence = trail.overall_confidence * (0.7 + 0.3 * verified_ratio)
    else:
        confidence = trail.overall_confidence

    return ComplianceResult(
        score=round(score, 4),
        confidence=round(confidence, 3),
        evidence_trail=trail,
        matched=matched,
        missing=missing,
        extra=extra,
        coverage=coverage,
        certification_evidence=certification_evidence,
        verified_certs=verified_certs,
        claimed_only_certs=claimed_only_certs,
    )
