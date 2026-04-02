from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from runtime_loader import task_state_module


class TaskStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="task-system-tests."))
        self.paths = task_state_module.TaskPaths.from_root(self.temp_dir)
        self.store = task_state_module.TaskStore(paths=self.paths)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_register_task_creates_inflight_file(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:test",
            channel="feishu",
            chat_id="chat:test",
            task_label="register task",
        )
        self.assertEqual(task.status, task_state_module.STATUS_QUEUED)
        self.assertTrue(self.store.inflight_path(task.task_id).exists())

    def test_start_task_marks_running(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:test",
            channel="feishu",
            chat_id="chat:test",
            task_label="start task",
        )
        started = self.store.start_task(task.task_id)
        self.assertEqual(started.status, task_state_module.STATUS_RUNNING)
        self.assertIsNotNone(started.started_at)

    def test_touch_task_updates_user_visible_timestamp(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:test",
            channel="feishu",
            chat_id="chat:test",
            task_label="touch task",
        )
        before = self.store.load_task(task.task_id).last_user_visible_update_at
        updated = self.store.touch_task(task.task_id, user_visible=True, meta={"step": 2})
        self.assertGreaterEqual(updated.last_user_visible_update_at, before)
        self.assertEqual(updated.meta["step"], 2)

    def test_block_task_marks_blocked(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:test",
            channel="feishu",
            chat_id="chat:test",
            task_label="block task",
        )
        blocked = self.store.block_task(task.task_id, "waiting for approval")
        self.assertEqual(blocked.status, task_state_module.STATUS_BLOCKED)
        self.assertEqual(blocked.block_reason, "waiting for approval")

    def test_complete_task_archives_and_removes_inflight(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:test",
            channel="feishu",
            chat_id="chat:test",
            task_label="complete task",
        )
        completed = self.store.complete_task(task.task_id, meta={"result": "ok"})
        self.assertEqual(completed.status, task_state_module.STATUS_DONE)
        self.assertFalse(self.store.inflight_path(task.task_id).exists())
        self.assertTrue(self.store.archive_path(task.task_id).exists())
        archived = self.store.load_task(task.task_id)
        self.assertEqual(archived.meta["result"], "ok")

    def test_fail_task_archives_failure_reason(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:test",
            channel="feishu",
            chat_id="chat:test",
            task_label="fail task",
        )
        failed = self.store.fail_task(task.task_id, "provider timeout")
        self.assertEqual(failed.status, task_state_module.STATUS_FAILED)
        self.assertEqual(failed.failure_reason, "provider timeout")
        self.assertTrue(self.store.archive_path(task.task_id).exists())

    def test_resume_task_reopens_blocked_task(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:test",
            channel="feishu",
            chat_id="chat:test",
            task_label="resume task",
        )
        blocked = self.store.block_task(task.task_id, "waiting for approval")
        resumed = self.store.resume_task(blocked.task_id, progress_note="继续执行")
        self.assertEqual(resumed.status, task_state_module.STATUS_RUNNING)
        self.assertIsNone(resumed.block_reason)
        self.assertEqual(resumed.meta["last_progress_note"], "继续执行")


if __name__ == "__main__":
    unittest.main()
