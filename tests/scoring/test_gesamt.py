from __future__ import annotations

import unittest
from pathlib import Path

from src.scoring.pipeline import find_substitutes
from tests.scoring.csv_loader import load_materials_csv, load_requirements_csv


class TestGesamt(unittest.TestCase):
    def test_csv_to_scoring_end_to_end(self) -> None:
        data_dir = Path(__file__).parent / "data"
        materials_csv = data_dir / "gesamt_materials.csv"
        requirements_csv = data_dir / "gesamt_requirements.csv"

        original, candidates = load_materials_csv(materials_csv)
        requirements = load_requirements_csv(requirements_csv)

        result = find_substitutes(
            original=original,
            candidates=candidates,
            user_requirements=requirements,
            top_n=3,
        )

        self.assertEqual(result.original.id, "orig-001")
        self.assertGreaterEqual(result.metadata.total_candidates, 20)
        self.assertGreater(result.metadata.passed_knockout, 0)
        self.assertGreater(len(result.rejected), 0)
        self.assertGreater(len(result.top_candidates), 0)
        self.assertLessEqual(len(result.top_candidates), 3)

        # Ranked candidates contain explainability and uncertainty payload.
        for idx, cand in enumerate(result.top_candidates, start=1):
            self.assertEqual(cand.rank, idx)
            self.assertIsNotNone(cand.explanation)
            self.assertIsNotNone(cand.uncertainty_report)
            self.assertEqual(
                set(cand.scores.keys()),
                {"spec", "compliance", "price", "lead_time", "quality"},
            )
            self.assertGreaterEqual(cand.composite_score, 0.0)
            self.assertLessEqual(cand.composite_score, 1.0)

        # Rejected candidates should carry reasons and evidence.
        for rejected in result.rejected:
            self.assertGreaterEqual(len(rejected.reasons), 1)
            self.assertGreaterEqual(len(rejected.evidence), 1)


if __name__ == "__main__":
    unittest.main()
