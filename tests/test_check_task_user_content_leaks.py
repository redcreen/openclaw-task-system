from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from runtime_loader import load_runtime_module


check_task_user_content_leaks = load_runtime_module("check_task_user_content_leaks")


class CheckTaskUserContentLeaksTests(unittest.TestCase):
    def test_run_audit_reports_clean_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            gateway_log = root / "openclaw-2026-04-10.log"
            session_file = root / "latest.jsonl"
            plugin_debug_log = root / "plugin-debug.log"
            gateway_log.write_text("deliver called (textPreview=在。)\n", encoding="utf-8")
            session_file.write_text('{"role":"assistant","content":"在。"}\n', encoding="utf-8")
            plugin_debug_log.write_text("before_message_write:user-content-sanitized\n", encoding="utf-8")

            payload = check_task_user_content_leaks.run_audit(
                record_date="2026-04-10",
                gateway_log=gateway_log,
                session_file=session_file,
                plugin_debug_log=plugin_debug_log,
                tail_lines=50,
            )

            self.assertTrue(payload["ok"])
            self.assertEqual(payload["counts"]["total"], 0)
            self.assertEqual(payload["counts"]["gateway_log"], 0)

    def test_run_audit_reports_hits_across_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            gateway_log = root / "openclaw-2026-04-10.log"
            session_file = root / "latest.jsonl"
            plugin_debug_log = root / "plugin-debug.log"
            gateway_log.write_text("deliver called (textPreview=<task_user_content>在。</task_user_content>)\n", encoding="utf-8")
            session_file.write_text('{"role":"assistant","content":"<task_user_content>在。</task_user_content>"}\n', encoding="utf-8")
            plugin_debug_log.write_text("message_sending raw=<task_user_content>在。</task_user_content>\n", encoding="utf-8")

            payload = check_task_user_content_leaks.run_audit(
                record_date="2026-04-10",
                gateway_log=gateway_log,
                session_file=session_file,
                plugin_debug_log=plugin_debug_log,
                tail_lines=50,
            )

            self.assertFalse(payload["ok"])
            self.assertEqual(payload["counts"]["gateway_log"], 1)
            self.assertEqual(payload["counts"]["session_hits"], 1)
            self.assertEqual(payload["counts"]["plugin_debug_log"], 1)
            self.assertEqual(payload["counts"]["total"], 3)
            self.assertEqual(len(payload["hits"]), 3)

    def test_run_audit_can_scan_all_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            agents_root = root / "agents"
            main_sessions = agents_root / "main" / "sessions"
            health_sessions = agents_root / "health" / "sessions"
            main_sessions.mkdir(parents=True)
            health_sessions.mkdir(parents=True)
            (main_sessions / "a.jsonl").write_text('{"content":"ok"}\n', encoding="utf-8")
            (health_sessions / "b.jsonl.reset.1").write_text('{"content":"<task_user_content>old</task_user_content>"}\n', encoding="utf-8")
            gateway_log = root / "openclaw-2026-04-10.log"
            plugin_debug_log = root / "plugin-debug.log"
            gateway_log.write_text("clean\n", encoding="utf-8")
            plugin_debug_log.write_text("clean\n", encoding="utf-8")

            with patch.object(check_task_user_content_leaks, "DEFAULT_AGENTS_ROOT", agents_root):
                payload = check_task_user_content_leaks.run_audit(
                    record_date="2026-04-10",
                    gateway_log=gateway_log,
                    plugin_debug_log=plugin_debug_log,
                    latest_only=False,
                )

            self.assertFalse(payload["ok"])
            self.assertEqual(payload["scan_mode"], "history")
            self.assertEqual(payload["counts"]["session_hits"], 1)
            self.assertTrue(any(hit["source"] == "historical_sessions" for hit in payload["hits"]))

    def test_run_audit_can_filter_hits_by_since_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            gateway_log = root / "openclaw-2026-04-10.log"
            session_file = root / "latest.jsonl"
            plugin_debug_log = root / "plugin-debug.log"
            gateway_log.write_text(
                "\n".join(
                    [
                        '{"_meta":{"date":"2026-04-10T01:00:00Z"},"1":"deliver called (textPreview=<task_user_content>old</task_user_content>)"}',
                        '{"_meta":{"date":"2026-04-10T02:00:00Z"},"1":"deliver called (textPreview=在。)"}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            session_file.write_text(
                "\n".join(
                    [
                        '{"timestamp":"2026-04-10T01:10:00Z","message":{"role":"assistant","content":[{"type":"text","text":"<task_user_content>old</task_user_content>"}]}}',
                        '{"timestamp":"2026-04-10T02:10:00Z","message":{"role":"assistant","content":[{"type":"text","text":"在。"}]}}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            plugin_debug_log.write_text(
                "\n".join(
                    [
                        '{"ts":"2026-04-10T01:20:00Z","event":"legacy","payload":{"raw":"<task_user_content>old</task_user_content>"}}',
                        '{"ts":"2026-04-10T02:20:00Z","event":"clean"}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            payload = check_task_user_content_leaks.run_audit(
                record_date="2026-04-10",
                gateway_log=gateway_log,
                session_file=session_file,
                plugin_debug_log=plugin_debug_log,
                tail_lines=50,
                since=datetime.fromisoformat("2026-04-10T02:00:00+00:00"),
            )

            self.assertTrue(payload["ok"])
            self.assertEqual(payload["counts"]["total"], 0)
            self.assertEqual(payload["since"], "2026-04-10T02:00:00+00:00")

    def test_main_can_emit_json_and_nonzero_when_leaks_found(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            gateway_log = root / "openclaw-2026-04-10.log"
            session_file = root / "latest.jsonl"
            plugin_debug_log = root / "plugin-debug.log"
            gateway_log.write_text("deliver called (textPreview=<task_user_content>在。</task_user_content>)\n", encoding="utf-8")
            session_file.write_text('{"role":"assistant","content":"在。"}\n', encoding="utf-8")
            plugin_debug_log.write_text("ok\n", encoding="utf-8")
            argv = [
                "check_task_user_content_leaks.py",
                "--date",
                "2026-04-10",
                "--gateway-log",
                str(gateway_log),
                "--session-file",
                str(session_file),
                "--plugin-debug-log",
                str(plugin_debug_log),
                "--json",
            ]
            with patch("sys.argv", argv):
                buffer = StringIO()
                with redirect_stdout(buffer):
                    exit_code = check_task_user_content_leaks.main()

            payload = json.loads(buffer.getvalue())
            self.assertEqual(exit_code, 1)
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["counts"]["gateway_log"], 1)

    def test_main_rejects_invalid_since(self) -> None:
        argv = [
            "check_task_user_content_leaks.py",
            "--since",
            "not-a-time",
        ]
        with patch("sys.argv", argv):
            with self.assertRaises(SystemExit):
                check_task_user_content_leaks.main()


if __name__ == "__main__":
    unittest.main()
