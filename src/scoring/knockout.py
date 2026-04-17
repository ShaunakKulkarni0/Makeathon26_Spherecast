from __future__ import annotations
from dataclasses import dataclass, field

from shared.schemas import CrawledMaterial, RejectedCandidate, UserRequirements
from shared.constants import COUNTRY_BLACKLIST, MAX_KNOCKOUT_CANDIDATES

from .evidence import Evidence, EvidenceType, collect_evidence


@dataclass
class KnockoutResult:
    passed: list[CrawledMaterial]
    rejected: list[RejectedCandidate]


def apply_knockout_filters(
    candidates: list[CrawledMaterial],
    user_requirements: UserRequirements,
    original: CrawledMaterial | None = None,
) -> KnockoutResult:
    """
    Filtert Kandidaten nach harten K.O.-Kriterien.
    Dokumentiert Evidence für jede Entscheidung.

    Args:
        candidates: Alle potenziellen Ersatzmaterialien
        user_requirements: Harte Ausschlusskriterien vom User
        original: Das Original-Material (für Preis-Vergleich)

    Returns:
        KnockoutResult mit passed- und rejected-Liste
    """
    passed: list[CrawledMaterial] = []
    rejected: list[RejectedCandidate] = []

    destination = user_requirements.destination_country
    blacklist = COUNTRY_BLACKLIST.get(destination, [])
    critical_certs = set(user_requirements.critical_certs or [])

    original_price = original.price.value if original else None
    max_price = (
        original_price * user_requirements.max_price_multiplier
        if original_price is not None
        else None
    )

    for candidate in candidates:
        reasons: list[str] = []
        evidences: list[Evidence] = []

        # --- MOQ Check ---
        if (
            user_requirements.max_quantity is not None
            and candidate.moq > user_requirements.max_quantity
        ):
            reasons.append(
                f"MOQ {candidate.moq} > Max-Menge {user_requirements.max_quantity}"
            )
            evidences.append(
                collect_evidence(
                    field="moq",
                    value=candidate.moq,
                    source_type=EvidenceType.SUPPLIER_DATABASE,
                    metadata={"notes": f"MOQ überschreitet User-Maximum von {user_requirements.max_quantity}"},
                )
            )

        # --- Blacklist Check ---
        if candidate.country_of_origin in blacklist:
            reasons.append(
                f"Herkunftsland {candidate.country_of_origin} auf Blacklist für {destination}"
            )
            evidences.append(
                collect_evidence(
                    field="country_of_origin",
                    value=candidate.country_of_origin,
                    source_type=EvidenceType.EXTERNAL_API,
                    metadata={"notes": "Sanktionsliste / Blacklist-Prüfung"},
                )
            )

        # --- Critical Certifications Check ---
        candidate_certs = set(candidate.certifications)
        missing_certs = critical_certs - candidate_certs
        if missing_certs:
            reasons.append(f"Kritische Zertifikate fehlen: {', '.join(sorted(missing_certs))}")
            for cert in missing_certs:
                evidences.append(
                    collect_evidence(
                        field="certification",
                        value=None,
                        source_type=EvidenceType.CERTIFICATION_DB,
                        metadata={"notes": f"Keine {cert}-Registrierung gefunden für {candidate.name}"},
                    )
                )

        # --- Max Lead Time Check ---
        if (
            user_requirements.max_lead_time_days is not None
            and candidate.lead_time.days > user_requirements.max_lead_time_days
        ):
            reasons.append(
                f"Lieferzeit {candidate.lead_time.days} Tage > Maximum {user_requirements.max_lead_time_days} Tage"
            )
            evidences.append(
                collect_evidence(
                    field="lead_time",
                    value=candidate.lead_time.days,
                    source_type=EvidenceType.SUPPLIER_DATABASE,
                    metadata={"notes": "Lieferzeit überschreitet User-Maximum"},
                )
            )

        # --- Max Price Check ---
        if max_price is not None and candidate.price.value > max_price:
            reasons.append(
                f"Preis {candidate.price.value} {candidate.price.unit} > Maximum {max_price:.2f}"
            )
            evidences.append(
                collect_evidence(
                    field="price",
                    value=candidate.price.value,
                    source_type=EvidenceType.SUPPLIER_DATABASE,
                    metadata={"notes": f"Preis überschreitet {user_requirements.max_price_multiplier}x Original"},
                )
            )

        if reasons:
            rejected.append(RejectedCandidate(
                candidate=candidate,
                reasons=reasons,
                evidence=evidences,
            ))
        else:
            passed.append(candidate)

    # Limit auf MAX_KNOCKOUT_CANDIDATES
    passed = passed[:MAX_KNOCKOUT_CANDIDATES]

    return KnockoutResult(passed=passed, rejected=rejected)
