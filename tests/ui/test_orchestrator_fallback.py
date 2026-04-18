from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src.ui.api.services import orchestrator


class TestOrchestratorFallback(unittest.TestCase):
    def test_prefers_runtime_scoring_csv_if_present(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            runtime = Path(tmp_dir) / "runtime.csv"
            default = Path(tmp_dir) / "default.csv"
            runtime.write_text("x", encoding="utf-8")

            with patch.object(orchestrator, "_RUNTIME_MATERIALS_CSV", runtime), patch.object(
                orchestrator, "_MATERIALS_CSV", default
            ):
                resolved = orchestrator._resolve_materials_csv_path()

            self.assertEqual(resolved, runtime)

    def test_uses_default_when_runtime_missing(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            runtime = Path(tmp_dir) / "runtime.csv"
            default = Path(tmp_dir) / "default.csv"
            extracted_missing = Path(tmp_dir) / "no_extracted.csv"
            default.write_text("x", encoding="utf-8")

            with (
                patch.object(orchestrator, "_RUNTIME_MATERIALS_CSV", runtime),
                patch.object(orchestrator, "_MATERIALS_CSV", default),
                patch.object(orchestrator, "_EXTRACTED_MATERIALS_CSV", extracted_missing),
            ):
                resolved = orchestrator._resolve_materials_csv_path()

            self.assertEqual(resolved, default)

    def test_refreshes_runtime_csv_when_extracted_has_more_rows(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            extracted = Path(tmp_dir) / "extracted.csv"
            runtime = Path(tmp_dir) / "runtime.csv"
            default = Path(tmp_dir) / "default.csv"
            default.write_text("id\nx\n", encoding="utf-8")

            extracted.write_text(
                (
                    "product_name,price,supplier,properties,certifications,lead_days,lead_type,years_in_business,source_url\n"
                    "A,10,S,{},[],5,stock,1,https://a\n"
                    "B,12,S,{},[],5,stock,1,https://b\n"
                ),
                encoding="utf-8",
            )
            runtime.write_text(
                "role,id,name,properties_json,certifications_json,price_value,price_unit,price_tiers_json,lead_days,lead_reliability,lead_type,supplier_rating_value,supplier_rating_reviews,defect_rate_value,defect_rate_sample,on_time_delivery_value,on_time_delivery_sample,years_in_business,audit_score_value,audit_age_months,audit_passed,moq,country_of_origin,incoterm,source_url\nORIGINAL,a,A,{},[],1,EUR/unit,,1,0.5,stock,,,,,,,,1,,,,1,UNKNOWN,EXW,https://a\n",
                encoding="utf-8",
            )

            with (
                patch.object(orchestrator, "_EXTRACTED_MATERIALS_CSV", extracted),
                patch.object(orchestrator, "_RUNTIME_MATERIALS_CSV", runtime),
                patch.object(orchestrator, "_MATERIALS_CSV", default),
            ):
                resolved = orchestrator._resolve_materials_csv_path()

            self.assertEqual(resolved, runtime)
            with runtime.open(newline="", encoding="utf-8") as f:
                rows = list(f.readlines())
            self.assertGreaterEqual(len(rows), 3)  # header + 2 rows


if __name__ == "__main__":
    unittest.main()
