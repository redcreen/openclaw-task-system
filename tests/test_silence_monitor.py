from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from runtime_loader import load_runtime_module, task_state_module


task_config = load_runtime_module("task_config")
silence_monitor = load_runtime_module("silence_monitor")


class SilenceMonitorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="task-system-watchdog-tests."))
        self.paths = task_state_module.TaskPaths.from_root(self.temp_dir)
        self.store = task_state_module.TaskStore(paths=self.paths)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def make_running_task(self) -> task_state_module.TaskState:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:test",
            channel="feishu",
            chat_id="chat:test",
            task_label="watchdog test task",
        )
        return self.store.start_task(task.task_id)

    def test_running_task_within_timeout_does_not_trigger(self) -> None:
        task = self.make_running_task()
        findings = silence_monitor.scan_tasks([task], timeout_seconds=30, resend_interval_seconds=30)
        self.assertEqual(findings, [])

    def test_overdue_running_task_triggers_notification(self) -> None:
        task = self.make_running_task()
        stored = self.store.load_task(task.task_id)
        stored.last_user_visible_update_at = "2020-01-01T00:00:00+00:00"
        stored.updated_at = stored.last_user_visible_update_at
        self.store.save_task(stored)

        findings = silence_monitor.scan_tasks([self.store.load_task(task.task_id)], timeout_seconds=30, resend_interval_seconds=30)
        self.assertEqual(len(findings), 1)
        self.assertTrue(findings[0].should_notify)
        self.assertEqual(findings[0].reason, "first-overdue")
        self.assertIn("已收到你的任务", silence_monitor.fallback_message(findings[0]))

    def test_recently_notified_task_does_not_repeat_within_resend_window(self) -> None:
        task = self.make_running_task()
        stored = self.store.load_task(task.task_id)
        stored.last_user_visible_update_at = "2020-01-01T00:00:00+00:00"
        stored.last_monitor_notify_at = silence_monitor.now().isoformat()
        self.store.save_task(stored)

        findings = silence_monitor.scan_tasks([self.store.load_task(task.task_id)], timeout_seconds=30, resend_interval_seconds=30)
        self.assertEqual(len(findings), 1)
        self.assertFalse(findings[0].should_notify)
        self.assertEqual(findings[0].reason, "recently-notified")

    def test_non_running_task_is_ignored(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:test",
            channel="feishu",
            chat_id="chat:test",
            task_label="blocked task",
        )
        blocked = self.store.block_task(task.task_id, "waiting for approval")
        findings = silence_monitor.scan_tasks([blocked], timeout_seconds=30, resend_interval_seconds=30)
        self.assertEqual(findings, [])

    def test_process_overdue_tasks_writes_outbox_and_marks_task(self) -> None:
        task = self.make_running_task()
        stored = self.store.load_task(task.task_id)
        stored.last_user_visible_update_at = "2020-01-01T00:00:00+00:00"
        self.store.save_task(stored)

        results = silence_monitor.process_overdue_tasks(
            paths=self.paths,
            timeout_seconds=30,
            resend_interval_seconds=30,
        )

        self.assertEqual(len(results), 1)
        refreshed = self.store.load_task(task.task_id)
        self.assertEqual(refreshed.monitor_state, "notified")
        self.assertEqual(refreshed.notify_count, 1)
        outbox_path = self.paths.data_dir / "outbox" / f"{task.task_id}.json"
        self.assertTrue(outbox_path.exists())

    def test_process_overdue_tasks_respects_disabled_monitor_config(self) -> None:
        task = self.make_running_task()
        stored = self.store.load_task(task.task_id)
        stored.last_user_visible_update_at = "2020-01-01T00:00:00+00:00"
        self.store.save_task(stored)

        config = task_config.TaskSystemConfig(
            enabled=True,
            storage_dir=self.paths.data_dir,
            agents={
                "main": task_config.AgentTaskConfig(
                    enabled=True,
                    silence_monitor=task_config.SilenceMonitorConfig(enabled=False),
                )
            },
        )
        results = silence_monitor.process_overdue_tasks(paths=self.paths, config=config)
        self.assertEqual(results, [])
        outbox_path = self.paths.data_dir / "outbox" / f"{task.task_id}.json"
        self.assertFalse(outbox_path.exists())

    def test_process_overdue_tasks_escalates_no_visible_progress_task_to_blocked(self) -> None:
        task = self.make_running_task()
        stored = self.store.load_task(task.task_id)
        stored.last_user_visible_update_at = "2020-01-01T00:00:00+00:00"
        stored.meta["finalize_skipped_reason"] = "success-without-visible-progress"
        self.store.save_task(stored)

        results = silence_monitor.process_overdue_tasks(
            paths=self.paths,
            timeout_seconds=30,
            resend_interval_seconds=30,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["escalation"], "blocked-no-visible-progress")
        refreshed = self.store.load_task(task.task_id)
        self.assertEqual(refreshed.status, task_state_module.STATUS_BLOCKED)
        self.assertEqual(refreshed.monitor_state, "blocked")
        self.assertEqual(refreshed.meta["watchdog_escalation"], "blocked-no-visible-progress")

        outbox_path = self.paths.data_dir / "outbox" / f"{task.task_id}.json"
        payload = outbox_path.read_text(encoding="utf-8")
        self.assertIn("标记为阻塞", payload)


if __name__ == "__main__":
    unittest.main()
