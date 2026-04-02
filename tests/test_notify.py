from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from runtime_loader import load_runtime_module, task_state_module


notify = load_runtime_module("notify")


class NotifyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="task-system-notify-tests."))
        self.paths = task_state_module.TaskPaths.from_root(self.temp_dir)
        self.store = task_state_module.TaskStore(paths=self.paths)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_mark_notified_updates_task_fields(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:test",
            channel="feishu",
            chat_id="chat:test",
            task_label="notify task",
        )
        task = self.store.start_task(task.task_id)
        updated = notify.mark_notified(task.task_id, paths=self.paths)
        self.assertEqual(updated.monitor_state, "notified")
        self.assertEqual(updated.notify_count, 1)
        self.assertIsNotNone(updated.last_monitor_notify_at)

    def test_build_payload_contains_runtime_fields(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:test",
            channel="feishu",
            chat_id="chat:test",
            task_label="notify payload task",
        )
        payload = notify.build_payload(task)
        self.assertEqual(payload["schema"], "openclaw.task-system.notify.v1")
        self.assertEqual(payload["task_id"], task.task_id)
        self.assertEqual(payload["agent_id"], "main")
        self.assertEqual(payload["channel"], "feishu")

    def test_mark_notified_can_resolve_paths_from_config_file(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:test",
            channel="feishu",
            chat_id="chat:test",
            task_label="notify config task",
        )
        task = self.store.start_task(task.task_id)
        config_dir = self.temp_dir / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "task_system.json"
        config_path.write_text(
            json.dumps({"taskSystem": {"storageDir": str(self.paths.data_dir)}}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        updated = notify.mark_notified(task.task_id, config_path=config_path)
        self.assertEqual(updated.monitor_state, "notified")
        self.assertEqual(updated.notify_count, 1)
