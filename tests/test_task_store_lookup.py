from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from runtime_loader import task_state_module


class TaskStoreLookupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="task-system-store-lookup-tests."))
        self.paths = task_state_module.TaskPaths.from_root(self.temp_dir)
        self.store = task_state_module.TaskStore(paths=self.paths)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_find_latest_active_task_returns_newest_match(self) -> None:
        first = self.store.register_task(
            agent_id="main",
            session_key="session:test",
            channel="feishu",
            chat_id="chat:test",
            task_label="first",
        )
        self.store.start_task(first.task_id)
        second = self.store.register_task(
            agent_id="main",
            session_key="session:test",
            channel="feishu",
            chat_id="chat:test",
            task_label="second",
        )
        second = self.store.start_task(second.task_id)

        latest = self.store.find_latest_active_task(agent_id="main", session_key="session:test")
        self.assertIsNotNone(latest)
        assert latest is not None
        self.assertEqual(latest.task_id, second.task_id)

    def test_find_latest_active_task_ignores_terminal_tasks(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:test",
            channel="feishu",
            chat_id="chat:test",
            task_label="done task",
        )
        self.store.start_task(task.task_id)
        self.store.complete_task(task.task_id)
        latest = self.store.find_latest_active_task(agent_id="main", session_key="session:test")
        self.assertIsNone(latest)


if __name__ == "__main__":
    unittest.main()
