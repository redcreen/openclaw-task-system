from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from runtime_loader import load_runtime_module


scrub_task_user_content_history = load_runtime_module("scrub_task_user_content_history")


class ScrubTaskUserContentHistoryTests(unittest.TestCase):
    def test_scrub_text_replaces_full_blocks_and_strips_unmatched_markers(self) -> None:
        raw = (
            '{"content":"<task_user_content>在。</task_user_content>"}\n'
            '{"content":"broken <task_user_content> marker"}\n'
        )
        scrubbed, changed = scrub_task_user_content_history.scrub_text(raw)
        self.assertTrue(changed)
        self.assertNotIn("<task_user_content>", scrubbed)
        self.assertNotIn("</task_user_content>", scrubbed)
        self.assertIn('{"content":"在。"}', scrubbed)
        self.assertIn('{"content":"broken  marker"}', scrubbed)

    def test_run_scrub_reports_changes_without_writing_in_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            agents_root = Path(temp_dir) / "agents"
            session_dir = agents_root / "main" / "sessions"
            session_dir.mkdir(parents=True)
            session_file = session_dir / "a.jsonl"
            session_file.write_text('{"content":"<task_user_content>在。</task_user_content>"}\n', encoding="utf-8")

            payload = scrub_task_user_content_history.run_scrub(agents_root=agents_root, apply=False)

            self.assertEqual(payload["scanned_files"], 1)
            self.assertEqual(payload["changed_files"], 1)
            self.assertIn("<task_user_content>", session_file.read_text(encoding="utf-8"))

    def test_run_scrub_writes_changes_when_apply_is_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            agents_root = Path(temp_dir) / "agents"
            session_dir = agents_root / "main" / "sessions"
            session_dir.mkdir(parents=True)
            session_file = session_dir / "a.jsonl.reset.1"
            session_file.write_text('{"content":"<task_user_content>在。</task_user_content>"}\n', encoding="utf-8")

            payload = scrub_task_user_content_history.run_scrub(agents_root=agents_root, apply=True)

            self.assertEqual(payload["changed_files"], 1)
            self.assertEqual(session_file.read_text(encoding="utf-8"), '{"content":"在。"}\n')

    def test_main_can_emit_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            agents_root = Path(temp_dir) / "agents"
            session_dir = agents_root / "main" / "sessions"
            session_dir.mkdir(parents=True)
            (session_dir / "a.jsonl").write_text('{"content":"<task_user_content>在。</task_user_content>"}\n', encoding="utf-8")

            argv = [
                "scrub_task_user_content_history.py",
                "--agents-root",
                str(agents_root),
                "--json",
            ]
            with patch("sys.argv", argv):
                buffer = StringIO()
                with redirect_stdout(buffer):
                    exit_code = scrub_task_user_content_history.main()

            payload = json.loads(buffer.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["changed_files"], 1)
            self.assertFalse(payload["apply"])


if __name__ == "__main__":
    unittest.main()
