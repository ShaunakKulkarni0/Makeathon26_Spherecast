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
            default.write_text("x", encoding="utf-8")

            with patch.object(orchestrator, "_RUNTIME_MATERIALS_CSV", runtime), patch.object(
                orchestrator, "_MATERIALS_CSV", default
            ):
                resolved = orchestrator._resolve_materials_csv_path()

            self.assertEqual(resolved, default)


if __name__ == "__main__":
    unittest.main()
