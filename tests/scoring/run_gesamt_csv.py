from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
import sys
from typing import Any

project_root = Path(__file__).parent.parent.parent.resolve()
sys.path.insert(0, str(project_root))

from src.scoring.pipeline import find_substitutes
from tests.scoring.csv_loader import load_materials_csv, load_requirements_csv


def _print_input_contract() -> None:
    """Zeigt die Struktur der Eingabedaten fuer find_substitutes (ohne Werte)."""
    _print_block("0) Input-Struktur (ohne konkrete Werte)")
    print("find_substitutes(")
    print("  original: CrawledMaterial,")
    print("  candidates: list[CrawledMaterial],")
    print("  user_requirements: UserRequirements,")
    print("  weights: dict[str, float] | None = None,")
    print("  top_n: int = ...")
    print(")")
    print("")

    print("A) original (CrawledMaterial)")
    print("  - id: str")
    print("  - name: str")
    print("  - properties: dict[str, MaterialProperty]")
    print("      - MaterialProperty.value: float")
    print("      - MaterialProperty.unit: str")
    print("  - certifications: list[str]")
    print("  - price: PriceInfo")
    print("      - value: float")
    print("      - unit: str")
    print("      - tiers: list[dict] | None")
    print("  - lead_time: LeadTimeInfo")
    print("      - days: int")
    print("      - reliability: float")
    print("      - type: str")
    print("  - quality: QualityInfo")
    print("      - supplier_rating: dict | None")
    print("      - defect_rate: dict | None")
    print("      - on_time_delivery: dict | None")
    print("      - years_in_business: int | None")
    print("      - audit_score: dict | None")
    print("  - moq: int")
    print("  - country_of_origin: str")
    print("  - incoterm: str")
    print("  - source_url: str | None")
    print("")

    print("B) candidates (list[CrawledMaterial])")
    print("  - gleicher Feldaufbau wie original")
    print("  - mehrere Kandidatenobjekte in einer Liste")
    print("")

    print("C) user_requirements (UserRequirements)")
    print("  - max_quantity: int | None")
    print("  - destination_country: str")
    print("  - critical_certs: list[str] | None")
    print("  - max_lead_time_days: int | None")
    print("  - max_price_multiplier: float")


def _to_serializable(value: Any) -> Any:
    """Konvertiert Dataclasses/Enums rekursiv in druckbare Python-Strukturen."""
    if is_dataclass(value):
        return {k: _to_serializable(v) for k, v in asdict(value).items()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): _to_serializable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_serializable(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_to_serializable(v) for v in value)
    return value


def _print_block(title: str) -> None:
    print("")
    print("=" * 90)
    print(title)
    print("=" * 90)


def _print_dict(prefix: str, data: dict[str, Any], indent: int = 0) -> None:
    pad = " " * indent
    for key, value in data.items():
        if isinstance(value, dict):
            print(f"{pad}{prefix}{key}:")
            _print_dict("", value, indent + 2)
        elif isinstance(value, list):
            print(f"{pad}{prefix}{key}:")
            if not value:
                print(f"{pad}  - keine")
                continue
            for idx, item in enumerate(value, start=1):
                if isinstance(item, dict):
                    print(f"{pad}  - [{idx}]")
                    _print_dict("", item, indent + 6)
                else:
                    print(f"{pad}  - {item}")
        else:
            print(f"{pad}{prefix}{key}: {value}")


def _print_explanation(explanation: Any) -> None:
    if not explanation:
        print("  explanation: nicht vorhanden")
        return

    exp = _to_serializable(explanation)
    print("  explanation:")
    _print_dict("  ", exp, indent=2)


def _print_uncertainty(uncertainty_report: Any) -> None:
    if not uncertainty_report:
        print("  uncertainty_report: nicht vorhanden")
        return

    report = _to_serializable(uncertainty_report)
    print("  uncertainty_report:")
    _print_dict("  ", report, indent=2)


def _print_evidence_trails(evidence_trails: dict[str, Any]) -> None:
    print("  evidence_trails:")
    if not evidence_trails:
        print("    - keine")
        return

    for dim, trail in evidence_trails.items():
        print(f"    {dim}:")
        trail_data = _to_serializable(trail)
        _print_dict("    ", trail_data, indent=6)


def _print_details(details: dict[str, Any]) -> None:
    print("  details (dimension-specific result objects):")
    if not details:
        print("    - keine")
        return

    for dim, detail_obj in details.items():
        print(f"    {dim}:")
        detail = _to_serializable(detail_obj)
        if isinstance(detail, dict):
            _print_dict("    ", detail, indent=6)
        else:
            print(f"      {detail}")


def main() -> int:
    _print_input_contract()

    data_dir = Path(__file__).parent / "data"
    materials_csv = data_dir / "gesamt_materials.csv"
    requirements_csv = data_dir / "gesamt_requirements.csv"

    original, candidates = load_materials_csv(materials_csv)
    requirements = load_requirements_csv(requirements_csv)

    _print_block("0.1) Input-Mengen aus CSV")
    print(f"original: 1 Objekt (CrawledMaterial)")
    print(f"candidates: {len(candidates)} Objekte (list[CrawledMaterial])")
    print("user_requirements: 1 Objekt (UserRequirements)")

    try:
        result = find_substitutes(
            original=original,
            candidates=candidates,
            user_requirements=requirements,
            top_n=3,
        )
    except Exception as exc:
        print("Scoring run failed before result generation.")
        print(f"Reason: {exc}")
        print("Hint: Ensure OPENAI_API_KEY is set and outbound network to OpenAI is available.")
        return 1

    _print_block("CSV -> find_substitutes(...) Vollausgabe")
    print("Erklaerung:")
    print("- Diese Ausgabe zeigt die komplette Struktur von ScoringResult.")
    print("- So siehst du alle moeglichen Felder fuer Top-Kandidaten und Rejected-Kandidaten.")

    _print_block("1) Original Material")
    _print_dict("", _to_serializable(result.original))

    _print_block("2) Metadata")
    _print_dict("", _to_serializable(result.metadata))

    _print_block("3) Top Candidates")
    if not result.top_candidates:
        print("- keine")
    else:
        for c in result.top_candidates:
            print("")
            print("-" * 90)
            print(
                f"rank={c.rank} | kandidat.id={c.kandidat.id} | kandidat.name={c.kandidat.name} | "
                f"composite={c.composite_score:.4f} | overall_confidence={c.overall_confidence:.3f}"
            )
            print("-" * 90)

            print("  kandidat (voll):")
            _print_dict("  ", _to_serializable(c.kandidat), indent=2)

            print("  scores:")
            _print_dict("  ", _to_serializable(c.scores), indent=2)

            print("  confidences:")
            _print_dict("  ", _to_serializable(c.confidences), indent=2)

            _print_explanation(c.explanation)
            _print_uncertainty(c.uncertainty_report)
            _print_evidence_trails(c.evidence_trails)
            _print_details(c.details)

    _print_block("4) Rejected Candidates")
    if not result.rejected:
        print("- keine")
    else:
        for idx, r in enumerate(result.rejected, start=1):
            print("")
            print(f"[{idx}] id={r.candidate.id} | name={r.candidate.name}")
            print("  candidate (voll):")
            _print_dict("  ", _to_serializable(r.candidate), indent=2)
            print("  reasons:")
            if not r.reasons:
                print("    - keine")
            else:
                for reason in r.reasons:
                    print(f"    - {reason}")
            print("  evidence:")
            if not r.evidence:
                print("    - keine")
            else:
                for ev_idx, evidence in enumerate(r.evidence, start=1):
                    print(f"    - [{ev_idx}]")
                    ev = _to_serializable(evidence)
                    if isinstance(ev, dict):
                        _print_dict("    ", ev, indent=8)
                    else:
                        print(f"      {ev}")

    _print_block("5) Consolidation (optional)")
    if result.consolidation is None:
        print("None (kein bom_context uebergeben)")
    else:
        _print_dict("", _to_serializable(result.consolidation))

    _print_block("6) Raw Dataclass Repr (Debug)")
    print("ScoringResult repr:")
    print(result)

    _print_block("7) Kurzfazit")
    print(f"Total candidates input: {len(candidates)}")
    print(f"Top candidates output: {len(result.top_candidates)}")
    print(f"Rejected output: {len(result.rejected)}")
    print(f"Average confidence: {result.metadata.average_confidence}")

    print("")
    print("Hinweis:")
    print("- Die wichtigsten Rueckgabefelder von find_substitutes sind damit komplett sichtbar.")
    print("- Wenn dir diese Ausgabe zu lang ist, kann ich eine 'compact' und eine 'full' Variante einbauen.")

    print("")
    print("Legacy summary:")
    print(f"Original: {result.original.id} ({result.original.name})")
    print(f"Total candidates: {result.metadata.total_candidates}")
    print(f"Passed knockout:  {result.metadata.passed_knockout}")
    print(f"Top candidates:   {len(result.top_candidates)}")
    print(f"Rejected:         {len(result.rejected)}")

    print("Rejected reasons (quick list):")
    for r in result.rejected:
        print(f"- id={r.candidate.id}")
        for reason in r.reasons:
            print(f"  reason: {reason}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
