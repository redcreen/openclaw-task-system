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
                return_value={"ok": True, "record_path": "/tmp/record.md", "artifacts_dir": "/tmp/artifacts"},
            ),
        ):
            payload = planning_acceptance_suite.run_suite(record_date="2026-04-10")

        self.assertTrue(payload["ok"])
        self.assertTrue(payload["tests_ok"])
        self.assertTrue(payload["bundle"]["ok"])
        self.assertEqual(payload["tests_output"], "OK\n")

    def test_main_can_emit_json(self) -> None:
        with patch.object(
            planning_acceptance_suite,
            "run_suite",
            return_value={
                "ok": True,
                "record_date": "2026-04-10",
                "tests_ok": True,
                "tests_returncode": 0,
                "tests_output": "OK\n",
                "tests_stdout": "OK\n",
                "tests_stderr": "",
                "bundle": {"ok": True, "record_path": "/tmp/record.md", "artifacts_dir": "/tmp/artifacts"},
            },
        ), patch("sys.argv", ["planning_acceptance_suite.py", "--date", "2026-04-10", "--json"]):
            buffer = StringIO()
            with redirect_stdout(buffer):
                exit_code = planning_acceptance_suite.main()

        payload = json.loads(buffer.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])


if __name__ == "__main__":
    unittest.main()
