from __future__ import annotations

import unittest

from shared.schemas import UserRequirements
from src.scoring.knockout import apply_knockout_filters
from tests.scoring.factories import make_material


class TestKnockout(unittest.TestCase):
    def test_knockout_filters_reject_and_pass(self) -> None:
        original = make_material("orig", price_value=2.0, certifications=["RoHS", "ISO9001"])

        candidate_ok = make_material(
            "ok",
            moq=100,
            certifications=["RoHS", "ISO9001", "REACH"],
            lead_days=12,
            price_value=2.1,
            country_of_origin="DE",
        )
        candidate_bad = make_material(
            "bad",
            moq=600,
            certifications=["RoHS"],
            lead_days=45,
            price_value=4.0,
            country_of_origin="IR",
        )

        req = UserRequirements(
            max_quantity=200,
            destination_country="DE",
            critical_certs=["ISO9001"],
            max_lead_time_days=30,
            max_price_multiplier=1.2,
        )

        result = apply_knockout_filters([candidate_ok, candidate_bad], req, original)

        self.assertEqual(len(result.passed), 1)
        self.assertEqual(result.passed[0].id, "ok")

        self.assertEqual(len(result.rejected), 1)
        rejected = result.rejected[0]
        self.assertEqual(rejected.candidate.id, "bad")
        self.assertGreaterEqual(len(rejected.reasons), 4)
        self.assertGreaterEqual(len(rejected.evidence), 4)


if __name__ == "__main__":
    unittest.main()
