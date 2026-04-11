from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from runtime_loader import load_runtime_module


capture_planning_acceptance_artifacts = load_runtime_module("capture_planning_acceptance_artifacts")


class CapturePlanningAcceptanceArtifactsTests(unittest.TestCase):
    def test_capture_artifacts_writes_selected_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            artifacts_dir = Path(temp_dir) / "artifacts"
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            prepared = {
                "ok": True,
                "record_date": "2026-04-10",
                "record_path": str(Path(temp_dir) / "planning_acceptance_record_2026-04-10.md"),
                "artifacts_dir": str(artifacts_dir),
            }
            with (
                patch.object(capture_planning_acceptance_artifacts, "prepare_acceptance", return_value=prepared),
                patch.object(
                    capture_planning_acceptance_artifacts.subprocess,
                    "run",
                    return_value=CompletedProcess(args=["cmd"], returncode=0, stdout='{"ok":true}\n', stderr=""),
                ),
            ):
                payload = capture_planning_acceptance_artifacts.capture_artifacts(
                    record_date="2026-04-10",
                    labels=["planning-acceptance"],
                )

            self.assertTrue(payload["ok"])
            self.assertEqual(len(payload["results"]), 1)
            output_path = Path(str(payload["results"][0]["output_path"]))
            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.read_text(encoding="utf-8"), '{"ok":true}\n')
            manifest_path = Path(str(payload["manifest_path"]))
            self.assertTrue(manifest_path.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertTrue(manifest["ok"])
            self.assertEqual(manifest["results"][0]["label"], "planning-acceptance")

    def test_main_can_emit_json(self) -> None:
        with patch.object(
            capture_planning_acceptance_artifacts,
            "capture_artifacts",
            return_value={
                "ok": True,
                "record_date": "2026-04-10",
                "record_path": "/tmp/record.md",
                "artifacts_dir": "/tmp/artifacts",
                "manifest_path": "/tmp/artifacts/capture_manifest.json",
                "results": [],
            },
        ), patch(
            "sys.argv",
            ["capture_planning_acceptance_artifacts.py", "--date", "2026-04-10", "--json"],
        ):
            buffer = StringIO()
            with redirect_stdout(buffer):
                exit_code = capture_planning_acceptance_artifacts.main()

        payload = json.loads(buffer.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])


if __name__ == "__main__":
    unittest.main()
