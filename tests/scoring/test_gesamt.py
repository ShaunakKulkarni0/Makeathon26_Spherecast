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
        self.assertEqual(result.metadata.total_candidates, 3)
        self.assertEqual(result.metadata.passed_knockout, 2)
        self.assertEqual(len(result.top_candidates), 2)
        self.assertEqual(len(result.rejected), 1)

        self.assertEqual(result.top_candidates[0].rank, 1)
        self.assertIsNotNone(result.top_candidates[0].explanation)
        self.assertEqual(result.rejected[0].candidate.id, "cand-003")
        self.assertGreaterEqual(len(result.rejected[0].reasons), 1)


if __name__ == "__main__":
    unittest.main()
