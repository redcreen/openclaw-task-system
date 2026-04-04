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

    def test_received_task_can_trigger_notification(self) -> None:
        task = self.store.observe_task(
            agent_id="main",
            session_key="session:received",
            channel="feishu",
            chat_id="chat:received",
            task_label="received task",
        )
        stored = self.store.load_task(task.task_id)
        stored.last_user_visible_update_at = "2020-01-01T00:00:00+00:00"
        stored.updated_at = stored.last_user_visible_update_at
        self.store.save_task(stored)

        findings = silence_monitor.scan_tasks([self.store.load_task(task.task_id)], timeout_seconds=30, resend_interval_seconds=30)
        self.assertEqual(len(findings), 1)
        self.assertTrue(findings[0].should_notify)
        self.assertEqual(findings[0].status, task_state_module.STATUS_RECEIVED)
        self.assertIn("等待 agent 真正开始处理", silence_monitor.fallback_message(findings[0]))

    def test_queued_task_can_trigger_notification(self) -> None:
        first = self.store.register_task(
            agent_id="main",
            session_key="session:first",
            channel="feishu",
            chat_id="chat:first",
            task_label="first task",
        )
        self.store.start_task(first.task_id)
        second = self.store.observe_task(
            agent_id="main",
            session_key="session:queued",
            channel="feishu",
            chat_id="chat:queued",
            task_label="queued task",
        )
        queued = self.store.claim_execution_slot(second.task_id)
        queued.last_user_visible_update_at = "2020-01-01T00:00:00+00:00"
        queued.updated_at = queued.last_user_visible_update_at
        self.store.save_task(queued)

        findings = silence_monitor.scan_tasks([self.store.load_task(second.task_id)], timeout_seconds=30, resend_interval_seconds=30)
        self.assertEqual(len(findings), 1)
        self.assertTrue(findings[0].should_notify)
        self.assertEqual(findings[0].status, task_state_module.STATUS_QUEUED)
        self.assertIn("排队等待处理", silence_monitor.fallback_message(findings[0]))

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

    def test_fallback_message_includes_continuation_wake_status(self) -> None:
        finding = silence_monitor.SilenceFinding(
            task_id="task_1",
            agent_id="main",
            session_key="session:test",
            channel="telegram",
            chat_id="8705812936",
            status=task_state_module.STATUS_RUNNING,
            silence_seconds=45,
            last_user_visible_update_at=task_state_module.now_iso(),
            should_notify=True,
            reason="first-overdue",
            continuation_wake_state="dispatched",
            continuation_wake_attempt_count=1,
            continuation_last_wake_at=task_state_module.now_iso(),
            continuation_wake_message="已唤醒 agent，等待最终回复送达",
        )
        message = silence_monitor.fallback_message(finding)
        self.assertIn("已尝试唤醒 agent 1 次", message)
        self.assertIn("已唤醒 agent", message)


if __name__ == "__main__":
    unittest.main()
