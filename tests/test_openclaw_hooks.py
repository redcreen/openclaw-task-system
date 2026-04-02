from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from runtime_loader import load_runtime_module, task_state_module


openclaw_hooks = load_runtime_module("openclaw_hooks")


class OpenClawHooksTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="task-system-hooks-tests."))
        self.paths = task_state_module.TaskPaths.from_root(self.temp_dir)
        self.config_path = self.temp_dir / "task_system.json"
        self.config_path.write_text(
            json.dumps({"taskSystem": {"storageDir": str(self.paths.data_dir)}}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.previous_env = os.environ.get("OPENCLAW_TASK_SYSTEM_CONFIG")
        os.environ["OPENCLAW_TASK_SYSTEM_CONFIG"] = str(self.config_path)

    def tearDown(self) -> None:
        if self.previous_env is None:
            os.environ.pop("OPENCLAW_TASK_SYSTEM_CONFIG", None)
        else:
            os.environ["OPENCLAW_TASK_SYSTEM_CONFIG"] = self.previous_env
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_register_from_payload_creates_task(self) -> None:
        result = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:test",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:test",
                "user_id": "ou_test",
                "user_request": "帮我排查这个问题并修复，再验证结果",
                "estimated_steps": 4,
                "needs_verification": True,
            }
        )
        self.assertTrue(result["should_register_task"])
        self.assertIsNotNone(result["task_id"])

    def test_progress_from_payload_updates_task(self) -> None:
        registration = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:test",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:test",
                "user_request": "继续处理这个任务",
                "estimated_steps": 3,
            }
        )
        task_id = registration["task_id"]
        assert task_id is not None
        task = openclaw_hooks.progress_from_payload(
            {
                "task_id": task_id,
                "progress_note": "checked integration hook",
            }
        )
        self.assertEqual(task["meta"]["last_progress_note"], "checked integration hook")

    def test_completed_from_payload_archives_task(self) -> None:
        registration = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:test",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:test",
                "user_request": "继续处理这个任务",
                "estimated_steps": 3,
            }
        )
        task_id = registration["task_id"]
        assert task_id is not None
        task = openclaw_hooks.completed_from_payload(
            {
                "task_id": task_id,
                "result_summary": "hook finished",
            }
        )
        self.assertEqual(task["status"], task_state_module.STATUS_DONE)

    def test_resolve_and_progress_active_task_by_session(self) -> None:
        registration = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:test",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:test",
                "user_request": "继续处理这个任务",
                "estimated_steps": 3,
            }
        )
        task_id = registration["task_id"]
        assert task_id is not None
        resolved = openclaw_hooks.resolve_active_task_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:test",
            }
        )
        self.assertTrue(resolved["found"])
        self.assertEqual(resolved["task_id"], task_id)

        updated = openclaw_hooks.progress_active_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:test",
                "progress_note": "plugin synced outbound message",
            }
        )
        self.assertTrue(updated["updated"])

    def test_finalize_active_marks_done_on_success(self) -> None:
        registration = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:done",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:done",
                "user_request": "继续处理这个任务",
                "estimated_steps": 3,
            }
        )
        assert registration["task_id"] is not None
        finalized = openclaw_hooks.finalize_active_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:done",
                "success": True,
                "result_summary": "completed by agent_end",
            }
        )
        self.assertTrue(finalized["updated"])
        self.assertEqual(finalized["task"]["status"], task_state_module.STATUS_DONE)

    def test_finalize_active_marks_failed_on_error(self) -> None:
        registration = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:failed",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:failed",
                "user_request": "继续处理这个任务",
                "estimated_steps": 3,
            }
        )
        assert registration["task_id"] is not None
        finalized = openclaw_hooks.finalize_active_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:failed",
                "success": False,
                "error": "agent_end failure",
            }
        )
        self.assertTrue(finalized["updated"])
        self.assertEqual(finalized["task"]["status"], task_state_module.STATUS_FAILED)

    def test_finalize_active_skips_generic_success_without_progress(self) -> None:
        registration = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:generic-success",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:generic-success",
                "user_request": "继续处理这个较长任务并分阶段汇报",
                "estimated_steps": 3,
            }
        )
        assert registration["task_id"] is not None
        finalized = openclaw_hooks.finalize_active_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:generic-success",
                "success": True,
                "result_summary": "openai-codex-responses",
            }
        )
        self.assertFalse(finalized["updated"])
        self.assertEqual(finalized["reason"], "awaiting-visible-output")

        resolved = openclaw_hooks.resolve_active_task_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:generic-success",
            }
        )
        self.assertTrue(resolved["found"])

    def test_finalize_active_skips_short_success_summary_without_progress(self) -> None:
        registration = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:short-summary",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:short-summary",
                "user_request": "继续处理这个较长任务并分阶段汇报",
                "estimated_steps": 3,
            }
        )
        assert registration["task_id"] is not None
        finalized = openclaw_hooks.finalize_active_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:short-summary",
                "success": True,
                "result_summary": "assistant",
            }
        )
        self.assertFalse(finalized["updated"])
        self.assertEqual(finalized["reason"], "awaiting-visible-output")

    def test_finalize_active_marks_done_after_progress_even_with_generic_summary(self) -> None:
        registration = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:generic-after-progress",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:generic-after-progress",
                "user_request": "继续处理这个较长任务并分阶段汇报",
                "estimated_steps": 3,
            }
        )
        assert registration["task_id"] is not None
        updated = openclaw_hooks.progress_active_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:generic-after-progress",
                "progress_note": "已开始扫描主链路并整理验证步骤。",
            }
        )
        self.assertTrue(updated["updated"])
        finalized = openclaw_hooks.finalize_active_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:generic-after-progress",
                "success": True,
                "result_summary": "openai-codex-responses",
            }
        )
        self.assertTrue(finalized["updated"])
        self.assertEqual(finalized["task"]["status"], task_state_module.STATUS_DONE)

    def test_fulfill_due_continuation_matches_due_reply_and_archives_task(self) -> None:
        registration = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:continuation-due",
                "channel": "telegram",
                "account_id": "default",
                "chat_id": "tg:test",
                "user_request": "1秒后回复我ok1",
            }
        )
        task_id = registration["task_id"]
        assert task_id is not None

        task = task_state_module.TaskStore(paths=self.paths).load_task(task_id, allow_archive=False)
        task.meta["continuation_due_at"] = "2000-01-01T00:00:00+08:00"
        task_state_module.TaskStore(paths=self.paths).save_task(task)

        fulfilled = openclaw_hooks.fulfill_due_continuation_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:continuation-due",
                "content": '收到，1分钟后回复"ok1"。 ok1',
            }
        )
        self.assertTrue(fulfilled["updated"])
        self.assertEqual(fulfilled["matched_reply_text"], "ok1")
        self.assertEqual(fulfilled["task"]["status"], task_state_module.STATUS_DONE)

    def test_fulfill_due_continuation_ignores_not_due_task(self) -> None:
        registration = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:continuation-not-due",
                "channel": "telegram",
                "account_id": "default",
                "chat_id": "tg:test",
                "user_request": "1分钟后回复我ok1",
            }
        )
        assert registration["task_id"] is not None

        fulfilled = openclaw_hooks.fulfill_due_continuation_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:continuation-not-due",
                "content": '收到，1分钟后回复"ok1"。 ok1',
            }
        )
        self.assertFalse(fulfilled["updated"])
        self.assertEqual(fulfilled["reason"], "no-due-continuation-match")

    def test_mark_continuation_wake_tracks_attempts(self) -> None:
        registration = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:wake",
                "channel": "telegram",
                "account_id": "default",
                "chat_id": "tg:test",
                "user_request": "1分钟后回复我ok1",
            }
        )
        task_id = registration["task_id"]
        assert task_id is not None

        marked = openclaw_hooks.mark_continuation_wake_from_payload(
            {
                "task_id": task_id,
                "state": "attempting",
                "message": "已触发到点唤醒",
            }
        )
        self.assertTrue(marked["updated"])
        self.assertEqual(marked["attempt_count"], 1)
        self.assertEqual(marked["wake_state"], "attempting")

        dispatched = openclaw_hooks.mark_continuation_wake_from_payload(
            {
                "task_id": task_id,
                "state": "dispatched",
                "message": "已唤醒 agent",
            }
        )
        self.assertTrue(dispatched["updated"])
        self.assertEqual(dispatched["attempt_count"], 1)
        self.assertEqual(dispatched["wake_state"], "dispatched")

    def test_mark_continuation_wake_returns_task_not_found_for_archived_task(self) -> None:
        registration = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:wake-missing",
                "channel": "telegram",
                "account_id": "default",
                "chat_id": "tg:test",
                "user_request": "1分钟后回复我ok1",
            }
        )
        task_id = registration["task_id"]
        assert task_id is not None
        openclaw_hooks.completed_from_payload({"task_id": task_id, "result_summary": "done"})

        marked = openclaw_hooks.mark_continuation_wake_from_payload(
            {
                "task_id": task_id,
                "state": "dispatched",
                "message": "已唤醒 agent",
            }
        )
        self.assertFalse(marked["updated"])
        self.assertEqual(marked["reason"], "task-not-found")

    def test_claim_due_continuations_returns_scheduled_delayed_reply(self) -> None:
        registration = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:delayed",
                "channel": "telegram",
                "account_id": "telegram-main",
                "chat_id": "chat:delayed",
                "user_request": "1秒后回复我ok1",
                "requires_external_wait": True,
            }
        )
        assert registration["task_id"] is not None
        self.assertEqual(registration["task_status"], task_state_module.STATUS_PAUSED)

        task_path = self.paths.inflight_dir / f"{registration['task_id']}.json"
        payload = json.loads(task_path.read_text(encoding="utf-8"))
        payload["meta"]["continuation_due_at"] = "2020-01-01T00:00:00+00:00"
        task_state_module.atomic_write_json(task_path, payload)

        claimed = openclaw_hooks.claim_due_continuations_from_payload({})
        self.assertEqual(claimed["claimed_count"], 1)
        self.assertEqual(claimed["tasks"][0]["reply_text"], "ok1")

        refreshed = json.loads(task_path.read_text(encoding="utf-8"))
        self.assertEqual(refreshed["status"], task_state_module.STATUS_RUNNING)
        self.assertEqual(refreshed["meta"]["continuation_state"], "claimed")


if __name__ == "__main__":
    unittest.main()
