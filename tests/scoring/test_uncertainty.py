from __future__ import annotations

import unittest

from src.scoring.evidence import build_evidence_trail
from src.scoring.uncertainty import (
    UncertaintyLevel,
    calculate_uncertainty_adjusted_score,
    generate_uncertainty_report,
)


class TestUncertainty(unittest.TestCase):
    def test_uncertainty_report_warns_with_missing_data(self) -> None:
        evidence_trails = {
            "spec": build_evidence_trail("spec", [], total_expected_fields=2),
            "compliance": build_evidence_trail("compliance", [], total_expected_fields=2),
            "price": build_evidence_trail("price", [], total_expected_fields=2),
            "lead_time": build_evidence_trail("lead_time", [], total_expected_fields=2),
            "quality": build_evidence_trail("quality", [], total_expected_fields=2),
        }
        scores = {k: 0.7 for k in evidence_trails.keys()}

        report = generate_uncertainty_report(scores, evidence_trails)

        self.assertTrue(report.should_warn_user)
        self.assertEqual(report.overall_level, UncertaintyLevel.VERY_HIGH)
        self.assertLess(report.overall_confidence, 0.5)
        self.assertGreaterEqual(len(report.data_gaps), 1)

    def test_uncertainty_adjusted_score_dampens_low_confidence(self) -> None:
        adjusted, reliable = calculate_uncertainty_adjusted_score(0.8, 0.2)
        self.assertFalse(reliable)
        self.assertAlmostEqual(adjusted, 0.4, places=4)

        adjusted_ok, reliable_ok = calculate_uncertainty_adjusted_score(0.8, 0.9)
        self.assertTrue(reliable_ok)
        self.assertGreater(adjusted_ok, 0.7)


if __name__ == "__main__":
    unittest.main()
