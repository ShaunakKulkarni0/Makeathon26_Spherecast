from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class EvidenceType(Enum):
    SUPPLIER_DATABASE = "supplier_database"
    SUPPLIER_WEBSITE = "supplier_website"
    CERTIFICATION_DB = "certification_db"
    DATASHEET = "datasheet"
    HISTORICAL_PROCUREMENT = "historical"
    EXTERNAL_API = "external_api"
    CALCULATED = "calculated"
    USER_INPUT = "user_input"
    INFERRED = "inferred"


BASE_CONFIDENCE: dict[EvidenceType, float] = {
    EvidenceType.CERTIFICATION_DB:       0.95,
    EvidenceType.DATASHEET:              0.90,
    EvidenceType.SUPPLIER_DATABASE:      0.85,
    EvidenceType.HISTORICAL_PROCUREMENT: 0.80,
    EvidenceType.EXTERNAL_API:           0.75,
    EvidenceType.CALCULATED:             0.70,
    EvidenceType.SUPPLIER_WEBSITE:       0.70,
    EvidenceType.USER_INPUT:             0.60,
    EvidenceType.INFERRED:               0.40,
}


@dataclass
class Evidence:
    type: EvidenceType
    source: str
    field: str
    value: Any
    timestamp: datetime
    confidence: float
    url: str | None = None
    notes: str | None = None


@dataclass
class EvidenceTrail:
    dimension: str
    evidences: list[Evidence]
    overall_confidence: float
    data_completeness: float   # 0.0–1.0
    data_freshness: str        # "current", "recent", "outdated"


def collect_evidence(
    field: str,
    value: Any,
    source_type: EvidenceType,
    source_url: str | None = None,
    metadata: dict | None = None,
) -> Evidence:
    """
    Erstellt einen Evidence-Eintrag für einen Datenpunkt.

    Args:
        field: Name des Datenfelds (z.B. "price", "zugfestigkeit")
        value: Der Wert
        source_type: Woher die Information stammt
        source_url: Optional direkter Link zur Quelle
        metadata: Optionale Zusatzinfos (age_days, sample_size, notes)

    Returns:
        Evidence-Objekt mit berechneter Confidence
    """
    confidence = BASE_CONFIDENCE.get(source_type, 0.5)

    if metadata:
        if "age_days" in metadata:
            age_factor = max(0.5, 1 - (metadata["age_days"] / 365))
            confidence *= age_factor
        if "sample_size" in metadata:
            if metadata["sample_size"] < 10:
                confidence *= 0.6
            elif metadata["sample_size"] < 100:
                confidence *= 0.8

    return Evidence(
        type=source_type,
        source=source_url or source_type.value,
        field=field,
        value=value,
        timestamp=datetime.now(),
        confidence=round(confidence, 3),
        url=source_url,
        notes=metadata.get("notes") if metadata else None,
    )


def build_evidence_trail(
    dimension: str,
    evidences: list[Evidence],
    total_expected_fields: int = 0,
) -> EvidenceTrail:
    """
    Aggregiert eine Liste von Evidence-Objekten zu einem EvidenceTrail.

    Args:
        dimension: Name der Scoring-Dimension
        evidences: Alle gesammelten Evidence-Einträge
        total_expected_fields: Wie viele Felder es insgesamt geben sollte (für Completeness)

    Returns:
        EvidenceTrail mit aggregierter Confidence
    """
    if not evidences:
        return EvidenceTrail(
            dimension=dimension,
            evidences=[],
            overall_confidence=0.0,
            data_completeness=0.0,
            data_freshness="outdated",
        )

    overall_confidence = sum(e.confidence for e in evidences) / len(evidences)

    completeness = (
        len(evidences) / total_expected_fields if total_expected_fields > 0 else 1.0
    )
    completeness = min(completeness, 1.0)

    now = datetime.now()
    max_age = max((now - e.timestamp).days for e in evidences)
    if max_age <= 1:
        freshness = "current"
    elif max_age <= 30:
        freshness = "recent"
    else:
        freshness = "outdated"

    return EvidenceTrail(
        dimension=dimension,
        evidences=evidences,
        overall_confidence=round(overall_confidence, 3),
        data_completeness=round(completeness, 3),
        data_freshness=freshness,
    )
