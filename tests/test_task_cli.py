from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from runtime_loader import load_runtime_module, task_state_module


task_cli = load_runtime_module("task_cli")


class TaskCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="task-system-task-cli-tests."))
        self.paths = task_state_module.TaskPaths.from_root(self.temp_dir)
        self.store = task_state_module.TaskStore(paths=self.paths)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _config_path(self) -> Path:
        config_path = self.temp_dir / "task_system.json"
        config_path.write_text(
            json.dumps({"taskSystem": {"storageDir": str(self.paths.data_dir)}}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return config_path

    def test_get_task_cli_tasks_lists_main_tasks(self) -> None:
        main_task = self.store.register_task(
            agent_id="main",
            session_key="session:main",
            channel="feishu",
            chat_id="chat:main",
            task_label="main task",
        )
        self.store.register_task(
            agent_id="code",
            session_key="session:code",
            channel="feishu",
            chat_id="chat:code",
            task_label="code task",
        )

        summary = task_cli.get_task_cli_tasks(paths=self.paths)

        self.assertEqual(summary["schema"], "openclaw.task-system.task-cli.v1")
        self.assertEqual(summary["view"], "tasks")
        self.assertEqual(summary["task_count"], 1)
        self.assertEqual(summary["tasks"][0]["task_id"], main_task.task_id)

    def test_get_task_cli_task_returns_status_summary(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:detail",
            channel="feishu",
            chat_id="chat:detail",
            task_label="detail task",
        )

        payload = task_cli.get_task_cli_task(task.task_id, paths=self.paths)

        self.assertEqual(payload["view"], "task")
        self.assertEqual(payload["task"]["task_id"], task.task_id)
        self.assertEqual(payload["task"]["task_label"], "detail task")

    def test_get_task_cli_session_returns_filtered_session_summary(self) -> None:
        session_task = self.store.register_task(
            agent_id="main",
            session_key="session:focus",
            channel="feishu",
            chat_id="chat:focus",
            task_label="focus task",
        )
        other_task = self.store.register_task(
            agent_id="main",
            session_key="session:other",
            channel="feishu",
            chat_id="chat:other",
            task_label="other task",
        )
        self.store.start_task(other_task.task_id)

        summary = task_cli.get_task_cli_session("session:focus", paths=self.paths)

        self.assertEqual(summary["view"], "session")
        self.assertEqual(summary["session_key"], "session:focus")
        self.assertEqual(summary["task_count"], 1)
        self.assertEqual(summary["tasks"][0]["task_id"], session_task.task_id)
        self.assertEqual(summary["queues"]["queue_count"], 1)
        self.assertEqual(summary["lanes"]["agent_count"], 1)
        self.assertIn("python3 scripts/runtime/main_ops.py continuity --session-key 'session:focus'", summary["suggested_next_commands"])

    def test_render_task_cli_session_includes_queue_and_tasks(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:render",
            channel="telegram",
            chat_id="chat:render",
            task_label="render task",
        )

        rendered = task_cli.render_task_cli_session("session:render", paths=self.paths)

        self.assertIn("# Task CLI", rendered)
        self.assertIn("- view: session", rendered)
        self.assertIn("- session_key: session:render", rendered)
        self.assertIn(task.task_id, rendered)

    def test_main_tasks_can_emit_json(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:main",
            channel="feishu",
            chat_id="chat:main",
            task_label="main task",
        )
        argv = [
            "task_cli.py",
            "--config",
            str(self._config_path()),
            "tasks",
            "--json",
        ]

        with patch("sys.argv", argv):
            buffer = StringIO()
            with redirect_stdout(buffer):
                exit_code = task_cli.main()

        payload = json.loads(buffer.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["task_count"], 1)
        self.assertEqual(payload["tasks"][0]["task_id"], task.task_id)

    def test_main_session_renders_markdown(self) -> None:
        self.store.register_task(
            agent_id="main",
            session_key="session:cli",
            channel="feishu",
            chat_id="chat:cli",
            task_label="cli task",
        )
        argv = [
            "task_cli.py",
            "--config",
            str(self._config_path()),
            "session",
            "session:cli",
        ]

        with patch("sys.argv", argv):
            buffer = StringIO()
            with redirect_stdout(buffer):
                exit_code = task_cli.main()

        rendered = buffer.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("# Task CLI", rendered)
        self.assertIn("- session_key: session:cli", rendered)


if __name__ == "__main__":
    unittest.main()
