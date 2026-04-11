from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from runtime_loader import load_runtime_module


run_planning_acceptance_bundle = load_runtime_module("run_planning_acceptance_bundle")


class RunPlanningAcceptanceBundleTests(unittest.TestCase):
    def test_run_bundle_summarizes_failures(self) -> None:
        with patch.object(
            run_planning_acceptance_bundle,
            "capture_artifacts",
            return_value={
                "ok": False,
                "record_path": "/tmp/record.md",
                "artifacts_dir": "/tmp/artifacts",
                "manifest_path": "/tmp/artifacts/capture_manifest.json",
                "results": [
                    {"label": "planning-acceptance", "ok": True, "output_path": "/tmp/a.json"},
                    {"label": "stable-acceptance", "ok": False, "output_path": "/tmp/b.json"},
                ],
            },
        ):
            payload = run_planning_acceptance_bundle.run_bundle(record_date="2026-04-10")

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["captured_count"], 2)
        self.assertEqual(payload["failed_count"], 1)
        self.assertEqual(payload["failed_labels"], ["stable-acceptance"])

    def test_run_bundle_writes_summary_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir)
            with patch.object(
                run_planning_acceptance_bundle,
                "capture_artifacts",
                return_value={
                    "ok": True,
                    "record_path": "/tmp/record.md",
                    "artifacts_dir": str(artifacts_dir),
                    "manifest_path": str(artifacts_dir / "capture_manifest.json"),
                    "results": [{"label": "planning-acceptance", "ok": True, "output_path": "/tmp/a.json"}],
                },
            ):
                payload = run_planning_acceptance_bundle.run_bundle(record_date="2026-04-10")

            summary_path = Path(str(payload["bundle_summary_path"]))
            self.assertTrue(summary_path.exists())
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertTrue(summary["ok"])
            self.assertEqual(summary["captured_count"], 1)

    def test_main_can_emit_json(self) -> None:
        with patch.object(
            run_planning_acceptance_bundle,
            "run_bundle",
            return_value={
                "ok": True,
                "record_date": "2026-04-10",
                "record_path": "/tmp/record.md",
                "artifacts_dir": "/tmp/artifacts",
                "capture_manifest_path": "/tmp/artifacts/capture_manifest.json",
                "captured_count": 1,
                "failed_count": 0,
                "failed_labels": [],
                "bundle_summary_path": "/tmp/artifacts/bundle_summary.json",
                "results": [],
            },
        ), patch("sys.argv", ["run_planning_acceptance_bundle.py", "--date", "2026-04-10", "--json"]):
            buffer = StringIO()
            with redirect_stdout(buffer):
                exit_code = run_planning_acceptance_bundle.main()

        payload = json.loads(buffer.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])


if __name__ == "__main__":
    unittest.main()
