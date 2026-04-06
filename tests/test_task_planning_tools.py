from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from runtime_loader import load_runtime_module, task_state_module


openclaw_hooks = load_runtime_module("openclaw_hooks")


class TaskPlanningToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="task-system-planning-tools-tests."))
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

    def _register_running_source_task(self) -> dict[str, object]:
        return openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:planning-tools",
                "channel": "feishu",
                "account_id": "feishu-main",
                "chat_id": "chat:planning-tools",
                "user_id": "ou_test",
                "user_request": "帮我查一下天气，然后稍后回来继续告诉我结果",
                "estimated_steps": 4,
            },
            config_path=self.config_path,
        )

    def test_create_followup_plan_persists_truth_source_state(self) -> None:
        registration = self._register_running_source_task()
        source_task_id = str(registration["task_id"])

        created = openclaw_hooks.create_followup_plan_from_payload(
            {
                "source_task_id": source_task_id,
                "followup_kind": "delayed-reply",
                "followup_due_at": "2026-04-06T11:30:00+08:00",
                "followup_message": "5 分钟后继续告诉你天气结果",
                "followup_summary": "5 分钟后同步天气结果",
                "main_user_content_mode": "none",
                "dependency": "after-source-task-finalized",
                "original_time_expression": "5分钟后",
                "reply_to_id": "om_source_message",
                "thread_id": "thread_source_message",
            },
            config_path=self.config_path,
        )

        self.assertTrue(created["accepted"])
        self.assertEqual(created["runtime_contract"]["followup_due_at"], "2026-04-06T11:30:00+08:00")
        store = task_state_module.TaskStore(paths=self.paths)
        source = store.load_task(source_task_id, allow_archive=False)
        plan = source.meta.get("tool_followup_plan")
        self.assertIsInstance(plan, dict)
        self.assertEqual(plan["plan_id"], created["plan_id"])
        self.assertEqual(plan["status"], "planned")
        self.assertEqual(plan["followup_message"], "5 分钟后继续告诉你天气结果")
        self.assertEqual(plan["followup_summary"], "5 分钟后同步天气结果")
        self.assertEqual(plan["main_user_content_mode"], "none")
        self.assertEqual(plan["reply_to_id"], "om_source_message")
        self.assertEqual(plan["thread_id"], "thread_source_message")

    def test_create_followup_plan_accepts_legacy_due_at_and_reply_text_aliases(self) -> None:
        registration = self._register_running_source_task()
        source_task_id = str(registration["task_id"])

        created = openclaw_hooks.create_followup_plan_from_payload(
            {
                "source_task_id": source_task_id,
                "kind": "delayed-reply",
                "due_at": "2026-04-06T11:30:00+08:00",
                "reply_text": "5 分钟后继续告诉你天气结果",
            },
            config_path=self.config_path,
        )

        self.assertTrue(created["accepted"])
        self.assertEqual(created["runtime_contract"]["followup_due_at"], "2026-04-06T11:30:00+08:00")

    def test_create_followup_plan_accepts_reply_target_aliases(self) -> None:
        registration = self._register_running_source_task()
        source_task_id = str(registration["task_id"])

        created = openclaw_hooks.create_followup_plan_from_payload(
            {
                "source_task_id": source_task_id,
                "followup_due_at": "2026-04-06T11:30:00+08:00",
                "followup_message": "5 分钟后继续告诉你天气结果",
                "replyToId": "om_alias_source_message",
                "threadId": "thread_alias_source_message",
            },
            config_path=self.config_path,
        )

        self.assertTrue(created["accepted"])
        store = task_state_module.TaskStore(paths=self.paths)
        source = store.load_task(source_task_id, allow_archive=False)
        plan = source.meta.get("tool_followup_plan")
        self.assertEqual(plan["reply_to_id"], "om_alias_source_message")
        self.assertEqual(plan["thread_id"], "thread_alias_source_message")

    def test_create_followup_plan_falls_back_to_source_task_reply_target(self) -> None:
        registration = self._register_running_source_task()
        source_task_id = str(registration["task_id"])
        store = task_state_module.TaskStore(paths=self.paths)
        source_task = store.load_task(source_task_id, allow_archive=False)
        source_task.meta["source_reply_to_id"] = "om_saved_source_message"
        source_task.meta["source_thread_id"] = "thread_saved_source_message"
        store.save_task(source_task)

        created = openclaw_hooks.create_followup_plan_from_payload(
            {
                "source_task_id": source_task_id,
                "followup_due_at": "2026-04-06T11:30:00+08:00",
                "followup_message": "5 分钟后继续告诉你天气结果",
            },
            config_path=self.config_path,
        )

        self.assertTrue(created["accepted"])
        source = store.load_task(source_task_id, allow_archive=False)
        plan = source.meta.get("tool_followup_plan")
        self.assertEqual(plan["reply_to_id"], "om_saved_source_message")
        self.assertEqual(plan["thread_id"], "thread_saved_source_message")

    def test_schedule_followup_from_plan_materializes_paused_task(self) -> None:
        registration = self._register_running_source_task()
        source_task_id = str(registration["task_id"])
        created = openclaw_hooks.create_followup_plan_from_payload(
            {
                "source_task_id": source_task_id,
                "followup_kind": "delayed-reply",
                "followup_due_at": "2026-04-06T11:30:00+08:00",
                "followup_message": "5 分钟后继续告诉你天气结果",
                "reply_to_id": "om_source_message",
                "thread_id": "thread_source_message",
            },
            config_path=self.config_path,
        )

        scheduled = openclaw_hooks.schedule_followup_from_plan_from_payload(
            {"plan_id": created["plan_id"]},
            config_path=self.config_path,
        )

        self.assertTrue(scheduled["scheduled"])
        self.assertEqual(scheduled["status"], task_state_module.STATUS_PAUSED)
        store = task_state_module.TaskStore(paths=self.paths)
        source = store.load_task(source_task_id, allow_archive=False)
        plan = source.meta.get("tool_followup_plan")
        self.assertEqual(plan["status"], "scheduled")
        self.assertEqual(plan["followup_task_id"], scheduled["task_id"])
        followup = store.load_task(scheduled["task_id"], allow_archive=False)
        self.assertEqual(followup.status, task_state_module.STATUS_PAUSED)
        self.assertEqual(followup.meta["continuation_kind"], "delayed-reply")
        self.assertEqual(followup.meta["continuation_payload"]["reply_text"], "5 分钟后继续告诉你天气结果")
        self.assertEqual(followup.meta["continuation_payload"]["reply_to_id"], "om_source_message")
        self.assertEqual(followup.meta["continuation_payload"]["thread_id"], "thread_source_message")

    def test_finalize_active_marks_promise_without_task_anomaly(self) -> None:
        registration = self._register_running_source_task()
        source_task_id = str(registration["task_id"])

        openclaw_hooks.attach_promise_guard_from_payload(
            {
                "source_task_id": source_task_id,
                "promise_type": "delayed-followup",
                "expected_by_finalize": True,
            },
            config_path=self.config_path,
        )

        finalized = openclaw_hooks.finalize_active_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:planning-tools",
                "task_id": source_task_id,
                "success": True,
                "has_visible_output": True,
                "result_summary": "即时部分已经完成。",
            },
            config_path=self.config_path,
        )

        self.assertTrue(finalized["updated"])
        meta = finalized["task"]["meta"]
        self.assertEqual(meta["planning_anomaly"], "promise-without-task")
        self.assertEqual(meta["planning_promise_guard"]["status"], "anomaly")

    def test_finalize_planned_followup_returns_due_at_metadata_for_runtime_status(self) -> None:
        registration = self._register_running_source_task()
        source_task_id = str(registration["task_id"])
        created = openclaw_hooks.create_followup_plan_from_payload(
            {
                "source_task_id": source_task_id,
                "followup_kind": "delayed-reply",
                "followup_due_at": "2026-04-06T11:30:00+08:00",
                "followup_message": "5 分钟后继续告诉你天气结果",
                "original_time_expression": "5分钟后",
            },
            config_path=self.config_path,
        )
        scheduled = openclaw_hooks.schedule_followup_from_plan_from_payload(
            {"plan_id": created["plan_id"]},
            config_path=self.config_path,
        )

        finalized = openclaw_hooks.finalize_planned_followup_from_payload(
            {
                "source_task_id": source_task_id,
                "plan_id": created["plan_id"],
                "followup_task_id": scheduled["task_id"],
            },
            config_path=self.config_path,
        )

        self.assertTrue(finalized["promise_fulfilled"])
        self.assertEqual(finalized["followup_due_at"], "2026-04-06T11:30:00+08:00")
        self.assertEqual(finalized["original_time_expression"], "5分钟后")

    def test_sync_followup_reply_target_updates_materialized_followup(self) -> None:
        registration = self._register_running_source_task()
        source_task_id = str(registration["task_id"])
        created = openclaw_hooks.create_followup_plan_from_payload(
            {
                "source_task_id": source_task_id,
                "followup_kind": "delayed-reply",
                "followup_due_at": "2026-04-06T11:30:00+08:00",
                "followup_message": "5 分钟后继续告诉你天气结果",
                "reply_to_id": "om_source_message",
                "thread_id": "thread_source_message",
            },
            config_path=self.config_path,
        )
        scheduled = openclaw_hooks.schedule_followup_from_plan_from_payload(
            {"plan_id": created["plan_id"]},
            config_path=self.config_path,
        )

        synced = openclaw_hooks.sync_followup_reply_target_from_payload(
            {
                "followup_task_id": scheduled["task_id"],
                "reply_to_id": "om_schedule_wd_message",
                "thread_id": "thread_source_message",
            },
            config_path=self.config_path,
        )

        self.assertTrue(synced["updated"])
        store = task_state_module.TaskStore(paths=self.paths)
        followup = store.load_task(scheduled["task_id"], allow_archive=False)
        self.assertEqual(followup.meta["continuation_payload"]["reply_to_id"], "om_schedule_wd_message")

    def test_overdue_followup_is_still_claimed_and_delivered(self) -> None:
        registration = self._register_running_source_task()
        source_task_id = str(registration["task_id"])
        created = openclaw_hooks.create_followup_plan_from_payload(
            {
                "source_task_id": source_task_id,
                "followup_kind": "delayed-reply",
                "followup_due_at": "2000-01-01T00:00:00+00:00",
                "followup_message": "已经过点也要继续发",
            },
            config_path=self.config_path,
        )
        scheduled = openclaw_hooks.schedule_followup_from_plan_from_payload(
            {"plan_id": created["plan_id"]},
            config_path=self.config_path,
        )

        self.assertTrue(scheduled["scheduled"])
        self.assertTrue(scheduled["overdue_on_materialize"])

        finalized_plan = openclaw_hooks.finalize_planned_followup_from_payload(
            {
                "source_task_id": source_task_id,
                "plan_id": created["plan_id"],
                "followup_task_id": scheduled["task_id"],
            },
            config_path=self.config_path,
        )
        self.assertTrue(finalized_plan["promise_fulfilled"])

        openclaw_hooks.finalize_active_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:planning-tools",
                "task_id": source_task_id,
                "success": True,
                "has_visible_output": True,
                "result_summary": "即时部分已经完成。",
            },
            config_path=self.config_path,
        )

        claimed = openclaw_hooks.claim_due_continuations_from_payload({}, config_path=self.config_path)
        self.assertEqual(claimed["claimed_count"], 1)
        self.assertEqual(claimed["tasks"][0]["task_id"], scheduled["task_id"])
        self.assertEqual(claimed["tasks"][0]["reply_text"], "已经过点也要继续发")


if __name__ == "__main__":
    unittest.main()
