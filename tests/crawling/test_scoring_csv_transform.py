from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path
from tempfile import NamedTemporaryFile

from src.crawling.data_transformer.scoring_csv_transform import (
    transform_extracted_to_scoring_csv,
)
from tests.scoring.csv_loader import load_materials_csv


class TestScoringCsvTransform(unittest.TestCase):
    def _write_input_csv(self, content: str) -> Path:
        temp = NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8")
        try:
            temp.write(content)
            temp.flush()
        finally:
            temp.close()
        return Path(temp.name)

    def test_transform_to_scoring_contract(self) -> None:
        input_path = self._write_input_csv(
            "product_name,price,supplier,properties,certifications,lead_days,lead_type,years_in_business,source_url\n"
            "Clear Gel Caps,1293.95,Capsuline,\"{\"\"moisture\"\": \"\"13% to 16%\"\", \"\"dimensions\"\": {\"\"length\"\": \"\"20.10 mm\"\"}}\",\"[\"\"COA\"\",\"\"Halal\"\"]\",NONE,NONE,NONE,https://eu.capsuline.com/products/clear-gel-caps\n"
            "Empty Gel Caps,NONE,Capsuline,NONE,NONE,12,out of stock,7,https://eu.capsuline.com/products/empty-gel-caps\n"
        )
        output_path = input_path.with_name(f"{input_path.stem}_scoring.csv")

        try:
            total_rows, numeric_properties = transform_extracted_to_scoring_csv(
                input_path=input_path,
                output_path=output_path,
            )

            self.assertEqual(total_rows, 2)
            self.assertGreaterEqual(numeric_properties, 2)

            with output_path.open(newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))

            self.assertEqual(rows[0]["role"], "ORIGINAL")
            self.assertEqual(rows[1]["role"], "CANDIDATE")
            self.assertEqual(rows[0]["id"], "clear-gel-caps")
            self.assertEqual(rows[1]["id"], "empty-gel-caps")
            self.assertEqual(rows[0]["price_unit"], "EUR/unit")
            self.assertEqual(rows[1]["price_value"], "0")
            self.assertEqual(rows[0]["lead_days"], "30")
            self.assertEqual(rows[1]["lead_type"], "unknown")
            self.assertEqual(rows[0]["moq"], "1")
            self.assertEqual(rows[0]["country_of_origin"], "UNKNOWN")
            self.assertEqual(rows[0]["incoterm"], "EXW")

            props = json.loads(rows[0]["properties_json"])
            self.assertIn("moisture", props)
            self.assertIn("dimensions.length", props)

            certs = json.loads(rows[0]["certifications_json"])
            self.assertEqual(certs, ["COA", "Halal"])

            original, candidates = load_materials_csv(output_path)
            self.assertEqual(original.id, "clear-gel-caps")
            self.assertEqual(len(candidates), 1)
        finally:
            input_path.unlink(missing_ok=True)
            output_path.unlink(missing_ok=True)

    def test_original_id_override(self) -> None:
        input_path = self._write_input_csv(
            "product_name,price,supplier,properties,certifications,lead_days,lead_type,years_in_business,source_url\n"
            "A,1,S,NONE,NONE,NONE,NONE,NONE,https://example.com/products/a\n"
            "B,1,S,NONE,NONE,NONE,NONE,NONE,https://example.com/products/b\n"
        )
        output_path = input_path.with_name(f"{input_path.stem}_scoring.csv")

        try:
            transform_extracted_to_scoring_csv(
                input_path=input_path,
                output_path=output_path,
                original_id="b",
            )
            with output_path.open(newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))

            self.assertEqual(rows[0]["role"], "CANDIDATE")
            self.assertEqual(rows[1]["role"], "ORIGINAL")
        finally:
            input_path.unlink(missing_ok=True)
            output_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
