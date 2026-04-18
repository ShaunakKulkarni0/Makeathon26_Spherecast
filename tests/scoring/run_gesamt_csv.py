from __future__ import annotations

from pathlib import Path
import sys

project_root = Path(__file__).parent.parent.parent.resolve()
sys.path.insert(0, str(project_root))

from src.scoring.pipeline import find_substitutes
from tests.scoring.csv_loader import load_materials_csv, load_requirements_csv


def main() -> int:
    data_dir = Path(__file__).parent / "data"
    materials_csv = data_dir / "gesamt_materials.csv"
    requirements_csv = data_dir / "gesamt_requirements.csv"

    original, candidates = load_materials_csv(materials_csv)
    requirements = load_requirements_csv(requirements_csv)

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

    print("=== CSV -> ScoringResult Demo ===")
    print(f"Original: {result.original.id} ({result.original.name})")
    print(f"Total candidates: {result.metadata.total_candidates}")
    print(f"Passed knockout:  {result.metadata.passed_knockout}")
    print("")

    print("Top candidates:")
    if not result.top_candidates:
        print("- keine")
    else:
        for c in result.top_candidates:
            print(
                f"- rank={c.rank} id={c.kandidat.id} "
                f"composite={c.composite_score:.4f} "
                f"confidence={c.overall_confidence:.3f}"
            )
            print(
                f"  scores: spec={c.scores.get('spec', 0):.3f} "
                f"compliance={c.scores.get('compliance', 0):.3f} "
                f"price={c.scores.get('price', 0):.3f} "
                f"lead_time={c.scores.get('lead_time', 0):.3f} "
                f"quality={c.scores.get('quality', 0):.3f}"
            )
            if c.explanation:
                print(f"  recommendation: {c.explanation.recommendation}")

    print("")
    print("Rejected candidates:")
    if not result.rejected:
        print("- keine")
    else:
        for r in result.rejected:
            print(f"- id={r.candidate.id}")
            for reason in r.reasons:
                print(f"  reason: {reason}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
