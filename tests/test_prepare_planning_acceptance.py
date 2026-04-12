from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from runtime_loader import load_runtime_module


prepare_planning_acceptance = load_runtime_module("prepare_planning_acceptance")


class PreparePlanningAcceptanceTests(unittest.TestCase):
    def test_prepare_acceptance_creates_record_and_artifacts_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir)
            record_path = docs_dir / "archive" / "planning_acceptance_record_2026-04-10.md"
            with (
                patch.object(prepare_planning_acceptance, "DOCS_DIR", docs_dir),
                patch.object(prepare_planning_acceptance, "create_record", return_value=record_path),
            ):
                payload = prepare_planning_acceptance.prepare_acceptance(record_date="2026-04-10")

            self.assertTrue(payload["ok"])
            self.assertEqual(payload["record_path"], str(record_path))
            self.assertFalse(payload["reused_existing_record"])
            artifacts_dir = docs_dir / "artifacts" / "planning_acceptance_2026-04-10"
            self.assertTrue(artifacts_dir.is_dir())
            self.assertIn(str(artifacts_dir / "planning_acceptance.json"), payload["capture_targets"])

    def test_prepare_acceptance_reuses_existing_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir)
            record_path = docs_dir / "archive" / "planning_acceptance_record_2026-04-10.md"
            record_path.parent.mkdir(parents=True, exist_ok=True)
            record_path.write_text("existing\n", encoding="utf-8")
            with (
                patch.object(prepare_planning_acceptance, "DOCS_DIR", docs_dir),
                patch.object(prepare_planning_acceptance, "create_record", side_effect=FileExistsError("exists")),
            ):
                payload = prepare_planning_acceptance.prepare_acceptance(record_date="2026-04-10")

            self.assertTrue(payload["ok"])
            self.assertTrue(payload["reused_existing_record"])
            self.assertEqual(payload["record_path"], str(record_path))

    def test_main_can_emit_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir)
            record_path = docs_dir / "archive" / "planning_acceptance_record_2026-04-10.md"
            artifacts_dir = docs_dir / "artifacts" / "planning_acceptance_2026-04-10"
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            with (
                patch.object(prepare_planning_acceptance, "prepare_acceptance", return_value={
                    "ok": True,
                    "record_date": "2026-04-10",
                    "record_path": str(record_path),
                    "artifacts_dir": str(artifacts_dir),
                    "reused_existing_record": False,
                    "capture_targets": [],
                }),
                patch("sys.argv", ["prepare_planning_acceptance.py", "--date", "2026-04-10", "--json"]),
            ):
                buffer = StringIO()
                with redirect_stdout(buffer):
                    exit_code = prepare_planning_acceptance.main()

            payload = json.loads(buffer.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["record_date"], "2026-04-10")


if __name__ == "__main__":
    unittest.main()
