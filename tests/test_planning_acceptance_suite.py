from __future__ import annotations

import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from subprocess import CompletedProcess
from unittest.mock import patch

from runtime_loader import load_runtime_module


planning_acceptance_suite = load_runtime_module("planning_acceptance_suite")


class PlanningAcceptanceSuiteTests(unittest.TestCase):
    def test_run_suite_combines_tests_and_bundle(self) -> None:
        with (
            patch.object(
                planning_acceptance_suite.subprocess,
                "run",
                return_value=CompletedProcess(args=["cmd"], returncode=0, stdout="OK\n", stderr=""),
            ),
            patch.object(
                planning_acceptance_suite,
                "run_bundle",
                return_value={
                    "ok": True,
                    "dry_run": True,
                    "workspace_root": "/tmp/workspace",
                    "record_path": "/tmp/record.md",
                    "artifacts_dir": "/tmp/artifacts",
                    "promotion_policy": {
                        "status": "ready-for-archive",
                        "promotion_ready": True,
                        "promotion_command": "python3 scripts/runtime/run_planning_acceptance_bundle.py --json --date 2026-04-10",
                    },
                },
            ) as mocked_bundle,
        ):
            payload = planning_acceptance_suite.run_suite(record_date="2026-04-10", dry_run=True)

        self.assertTrue(payload["ok"])
        self.assertTrue(payload["dry_run"])
        self.assertTrue(payload["tests_ok"])
        self.assertTrue(payload["bundle"]["ok"])
        self.assertEqual(payload["tests_output"], "OK\n")
        self.assertEqual(payload["promotion_policy"]["status"], "ready-for-archive")
        mocked_bundle.assert_called_once_with(record_date="2026-04-10", force=False, dry_run=True, labels=None)

    def test_main_can_emit_json(self) -> None:
        with patch.object(
            planning_acceptance_suite,
            "run_suite",
            return_value={
                "ok": True,
                "record_date": "2026-04-10",
                "dry_run": False,
                "tests_ok": True,
                "tests_returncode": 0,
                "tests_output": "OK\n",
                "tests_stdout": "OK\n",
                "tests_stderr": "",
                "promotion_policy": {
                    "status": "ready-for-archive",
                    "promotion_command": "python3 scripts/runtime/run_planning_acceptance_bundle.py --json --date 2026-04-10",
                },
                "bundle": {
                    "ok": True,
                    "dry_run": False,
                    "workspace_root": "/tmp/workspace",
                    "record_path": "/tmp/record.md",
                    "artifacts_dir": "/tmp/artifacts",
                    "promotion_policy": {
                        "status": "ready-for-archive",
                        "promotion_command": "python3 scripts/runtime/run_planning_acceptance_bundle.py --json --date 2026-04-10",
                    },
                },
            },
        ), patch("sys.argv", ["planning_acceptance_suite.py", "--date", "2026-04-10", "--json"]):
            buffer = StringIO()
            with redirect_stdout(buffer):
                exit_code = planning_acceptance_suite.main()

        payload = json.loads(buffer.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])

    def test_render_markdown_includes_promotion_policy(self) -> None:
        rendered = planning_acceptance_suite.render_markdown(
            {
                "ok": True,
                "dry_run": True,
                "tests_ok": True,
                "tests_returncode": 0,
                "promotion_policy": {
                    "status": "ready-for-archive",
                    "promotion_command": "python3 scripts/runtime/run_planning_acceptance_bundle.py --json --date 2026-04-10",
                },
                "bundle": {
                    "ok": True,
                    "workspace_root": "/tmp/workspace",
                    "record_path": "/tmp/record.md",
                    "artifacts_dir": "/tmp/artifacts",
                },
            }
        )

        self.assertIn("promotion_status: ready-for-archive", rendered)
        self.assertIn("promotion_command: python3 scripts/runtime/run_planning_acceptance_bundle.py --json --date 2026-04-10", rendered)


if __name__ == "__main__":
    unittest.main()
