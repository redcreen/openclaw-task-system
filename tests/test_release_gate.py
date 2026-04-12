from __future__ import annotations

import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from subprocess import CompletedProcess
from unittest.mock import patch

from runtime_loader import load_runtime_module


release_gate = load_runtime_module("release_gate")


class ReleaseGateTests(unittest.TestCase):
    def test_run_release_gate_succeeds(self) -> None:
        side_effect = [
            CompletedProcess(args=["cmd"], returncode=0, stdout="[testsuite] 自动化 testsuite 已全部通过\n", stderr=""),
            CompletedProcess(
                args=["cmd"],
                returncode=0,
                stdout=json.dumps({"ok": True, "steps": [{"ok": True}]}, ensure_ascii=False),
                stderr="",
            ),
            CompletedProcess(
                args=["cmd"],
                returncode=0,
                stdout=json.dumps({"ok": True, "steps": [{"ok": True}, {"ok": True}]}, ensure_ascii=False),
                stderr="",
            ),
            CompletedProcess(
                args=["cmd"],
                returncode=0,
                stdout=json.dumps(
                    {"ok": True, "missing_in_mirror": [], "extra_in_mirror": [], "changed_files": []},
                    ensure_ascii=False,
                ),
                stderr="",
            ),
            CompletedProcess(
                args=["cmd"],
                returncode=0,
                stdout=json.dumps({"ok": True, "missing_in_installed": [], "extra_in_installed": []}, ensure_ascii=False),
                stderr="",
            ),
        ]
        with patch.object(release_gate.subprocess, "run", side_effect=side_effect):
            payload = release_gate.run_release_gate()

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["step_count"], 5)
        self.assertEqual(payload["failed_step_count"], 0)
        self.assertEqual([step["step"] for step in payload["steps"]], [command.step for command in release_gate.build_release_gate_commands()])
        self.assertEqual(payload["steps"][0]["summary"], "[testsuite] 自动化 testsuite 已全部通过")
        self.assertEqual(payload["steps"][2]["summary"], "reported_ok=True steps=2 failed=0")

    def test_run_release_gate_keeps_collecting_after_failure(self) -> None:
        side_effect = [
            CompletedProcess(args=["cmd"], returncode=0, stdout="[testsuite] ok\n", stderr=""),
            CompletedProcess(
                args=["cmd"],
                returncode=0,
                stdout=json.dumps({"ok": True, "steps": [{"ok": True}]}, ensure_ascii=False),
                stderr="",
            ),
            CompletedProcess(
                args=["cmd"],
                returncode=1,
                stdout=json.dumps({"ok": False, "steps": [{"ok": False}]}, ensure_ascii=False),
                stderr="stable failed\n",
            ),
            CompletedProcess(
                args=["cmd"],
                returncode=0,
                stdout=json.dumps(
                    {"ok": True, "missing_in_mirror": [], "extra_in_mirror": [], "changed_files": []},
                    ensure_ascii=False,
                ),
                stderr="",
            ),
            CompletedProcess(
                args=["cmd"],
                returncode=0,
                stdout=json.dumps({"ok": True, "missing_in_installed": [], "extra_in_installed": []}, ensure_ascii=False),
                stderr="",
            ),
        ]
        with patch.object(release_gate.subprocess, "run", side_effect=side_effect):
            payload = release_gate.run_release_gate()

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["failed_step_count"], 1)
        self.assertFalse(payload["steps"][2]["ok"])
        self.assertEqual(payload["steps"][2]["summary"], "reported_ok=False steps=1 failed=1")
        self.assertTrue(payload["steps"][3]["ok"])
        self.assertTrue(payload["steps"][4]["ok"])

    def test_main_can_emit_json(self) -> None:
        with patch.object(
            release_gate,
            "run_release_gate",
            return_value={
                "schema": "openclaw.task-system.release-gate.v1",
                "version": 1,
                "project_root": "/tmp/project",
                "ok": True,
                "step_count": 1,
                "failed_step_count": 0,
                "steps": [
                    {
                        "step": "testsuite",
                        "ok": True,
                        "returncode": 0,
                        "command": ["bash", "scripts/run_tests.sh"],
                        "summary": "ok",
                        "metrics": {},
                    }
                ],
            },
        ), patch("sys.argv", ["release_gate.py", "--json"]):
            buffer = StringIO()
            with redirect_stdout(buffer):
                exit_code = release_gate.main()

        payload = json.loads(buffer.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])

    def test_render_markdown_includes_step_summary(self) -> None:
        rendered = release_gate.render_markdown(
            {
                "ok": False,
                "step_count": 2,
                "failed_step_count": 1,
                "steps": [
                    {"step": "testsuite", "ok": True, "summary": "ok"},
                    {"step": "stable-acceptance", "ok": False, "summary": "reported_ok=False steps=4 failed=1"},
                ],
            }
        )

        self.assertIn("# Release Gate", rendered)
        self.assertIn("- testsuite: ok", rendered)
        self.assertIn("- stable-acceptance: failed", rendered)
        self.assertIn("summary: reported_ok=False steps=4 failed=1", rendered)


if __name__ == "__main__":
    unittest.main()
