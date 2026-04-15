from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_observe_task_creates_received_task(self) -> None:
        task = self.store.observe_task(
            agent_id="main",
            session_key="session:observe",
            channel="feishu",
            chat_id="chat:observe",
            task_label="observe task",
        )
        self.assertEqual(task.status, task_state_module.STATUS_RECEIVED)
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
        self.assertEqual(archived.last_user_visible_update_at, archived.updated_at)

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
        self.assertEqual(failed.last_user_visible_update_at, failed.updated_at)

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

    def test_cancel_task_archives_cancel_reason(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:test",
            channel="feishu",
            chat_id="chat:test",
            task_label="cancel task",
        )
        cancelled = self.store.cancel_task(task.task_id, "stopped by user")
        self.assertEqual(cancelled.status, task_state_module.STATUS_CANCELLED)
        self.assertEqual(cancelled.failure_reason, "stopped by user")
        self.assertEqual(cancelled.meta["cancel_reason"], "stopped by user")
        self.assertTrue(self.store.archive_path(task.task_id).exists())

    def test_reuses_inflight_cache_across_repeated_find_operations(self) -> None:
        running = self.store.register_task(
            agent_id="main",
            session_key="session:cache:running",
            channel="feishu",
            chat_id="chat:cache:running",
            task_label="running task",
        )
        self.store.start_task(running.task_id)
        queued = self.store.register_task(
            agent_id="main",
            session_key="session:cache:queued",
            channel="feishu",
            chat_id="chat:cache:queued",
            task_label="queued task",
        )
        observed = self.store.observe_task(
            agent_id="main",
            session_key="session:cache:observed",
            channel="feishu",
            chat_id="chat:cache:observed",
            task_label="observed task",
        )
        original = task_state_module.TaskStore.load_task
        load_calls: list[tuple[str, bool]] = []

        def counting_load(store: object, task_id: str, *, allow_archive: bool = True):
            load_calls.append((task_id, allow_archive))
            return original(store, task_id, allow_archive=allow_archive)

        with patch.object(task_state_module.TaskStore, "load_task", autospec=True, side_effect=counting_load):
            self.store.find_running_tasks(agent_id="main")
            self.store.find_queued_tasks(agent_id="main")
            self.store.find_latest_observed_task(agent_id="main", session_key=observed.session_key)

        self.assertEqual(len(load_calls), 3)
        self.assertEqual({task_id for task_id, _allow_archive in load_calls}, {running.task_id, queued.task_id, observed.task_id})

    def test_write_paths_invalidate_inflight_cache(self) -> None:
        first = self.store.register_task(
            agent_id="main",
            session_key="session:cache:first",
            channel="feishu",
            chat_id="chat:cache:first",
            task_label="first task",
        )
        initial = self.store.find_inflight_tasks(agent_id="main")
        self.assertEqual(len(initial), 1)

        second = self.store.register_task(
            agent_id="main",
            session_key="session:cache:second",
            channel="feishu",
            chat_id="chat:cache:second",
            task_label="second task",
        )

        refreshed = self.store.find_inflight_tasks(agent_id="main")
        self.assertEqual({task.task_id for task in refreshed}, {first.task_id, second.task_id})

    def test_cross_store_writes_invalidate_cached_inflight_snapshot(self) -> None:
        first = self.store.register_task(
            agent_id="main",
            session_key="session:cache:cross:first",
            channel="feishu",
            chat_id="chat:cache:cross:first",
            task_label="first cross-store task",
        )
        sibling_store = task_state_module.TaskStore(paths=self.paths)
        initial = self.store.find_inflight_tasks(agent_id="main")
        self.assertEqual([task.task_id for task in initial], [first.task_id])

        second = sibling_store.register_task(
            agent_id="main",
            session_key="session:cache:cross:second",
            channel="feishu",
            chat_id="chat:cache:cross:second",
            task_label="second cross-store task",
        )

        refreshed = self.store.find_inflight_tasks(agent_id="main")
        self.assertEqual({task.task_id for task in refreshed}, {first.task_id, second.task_id})

    def test_cross_store_reads_reuse_shared_inflight_snapshot(self) -> None:
        first = self.store.register_task(
            agent_id="main",
            session_key="session:cache:shared:first",
            channel="feishu",
            chat_id="chat:cache:shared:first",
            task_label="first shared task",
        )
        second = self.store.register_task(
            agent_id="main",
            session_key="session:cache:shared:second",
            channel="feishu",
            chat_id="chat:cache:shared:second",
            task_label="second shared task",
        )
        self.store.find_inflight_tasks(agent_id="main")
        sibling_store = task_state_module.TaskStore(paths=self.paths)
        original = task_state_module.TaskStore.load_task
        load_calls: list[str] = []

        def counting_load(store: object, task_id: str, *, allow_archive: bool = True):
            load_calls.append(task_id)
            return original(store, task_id, allow_archive=allow_archive)

        with patch.object(task_state_module.TaskStore, "load_task", autospec=True, side_effect=counting_load):
            tasks = sibling_store.find_inflight_tasks(agent_id="main")

        self.assertEqual({task.task_id for task in tasks}, {first.task_id, second.task_id})
        self.assertEqual(load_calls, [])


if __name__ == "__main__":
    unittest.main()
