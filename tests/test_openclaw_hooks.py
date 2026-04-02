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
        self.assertEqual(
            finalized["task"]["last_user_visible_update_at"],
            finalized["task"]["updated_at"],
        )


if __name__ == "__main__":
    unittest.main()
