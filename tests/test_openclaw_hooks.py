from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
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
        self.assertIn("register_decision", result)
        self.assertIsInstance(result["register_decision"], dict)
        self.assertEqual(result["register_decision"]["task_id"], result["task_id"])

    def test_register_from_payload_includes_structured_register_decision(self) -> None:
        result = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:structured-decision",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:structured-decision",
                "user_id": "ou_test",
                "user_request": "帮我继续排队处理这个任务",
                "observe_only": True,
            }
        )
        decision = result["register_decision"]
        self.assertEqual(decision["should_register_task"], result["should_register_task"])
        self.assertEqual(decision["task_id"], result["task_id"])
        self.assertEqual(decision["classification_reason"], result["classification_reason"])
        self.assertEqual(decision["task_status"], result["task_status"])
        self.assertEqual(decision["queue_position"], result["queue_position"])

    def test_openclaw_hooks_cli_accepts_stdin_payload(self) -> None:
        script = Path(__file__).resolve().parents[1] / "scripts" / "runtime" / "openclaw_hooks.py"
        payload = {
            "agent_id": "main",
            "session_key": "session:stdin",
            "channel": "feishu",
            "account_id": "feishu1-main",
            "chat_id": "chat:stdin",
            "user_id": "ou_test",
            "user_request": "帮我检查一下 stdin hook 路径",
            "observe_only": True,
        }

        result = subprocess.run(
            [sys.executable, str(script), "register", "-", str(self.config_path)],
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            capture_output=True,
            check=True,
        )

        parsed = json.loads(result.stdout)
        self.assertTrue(parsed["should_register_task"])
        self.assertEqual(parsed["classification_reason"], "observed-task")

    def test_load_payload_for_claim_due_continuations_tolerates_keyboard_interrupt(self) -> None:
        original = openclaw_hooks.load_payload_from_stdin

        def raising_loader() -> dict[str, object]:
            raise KeyboardInterrupt

        openclaw_hooks.load_payload_from_stdin = raising_loader
        try:
            parsed = openclaw_hooks.load_payload_for_command("claim-due-continuations", "-")
        finally:
            openclaw_hooks.load_payload_from_stdin = original

        self.assertEqual(parsed, {})

    def test_load_payload_for_other_commands_preserves_keyboard_interrupt(self) -> None:
        original = openclaw_hooks.load_payload_from_stdin

        def raising_loader() -> dict[str, object]:
            raise KeyboardInterrupt

        openclaw_hooks.load_payload_from_stdin = raising_loader
        try:
            with self.assertRaises(KeyboardInterrupt):
                openclaw_hooks.load_payload_for_command("register", "-")
        finally:
            openclaw_hooks.load_payload_from_stdin = original

    def test_watchdog_auto_recover_orchestrates_scan_and_auto_resume(self) -> None:
        original_scan = openclaw_hooks.process_overdue_tasks
        original_auto_resume = openclaw_hooks.auto_resume_watchdog_blocked_main_tasks_if_safe

        def fake_scan(*, paths=None, config=None, config_path=None):
            return [
                {
                    "task_id": "task_watchdog",
                    "session_key": "session:main:recover",
                    "should_notify": True,
                    "escalation": "blocked-no-visible-progress",
                }
            ]

        def fake_auto_resume(*, config_path=None, paths=None, session_key=None, limit=None, note=None, dry_run=False):
            return {
                "status": "applied",
                "session_filter": session_key or "all",
                "closure_complete": False,
                "closure_state": "needs-followup",
                "closure_state_reason": "resumed-sessions-still-have-active-tasks",
                "closure_hint": "Follow up session session:main:recover next.",
                "closure_hint_command": "python3 ... continuity --session-key 'session:main:recover'",
                "focus_session_key": "session:main:recover",
                "primary_action_kind": "followup-session",
                "primary_action_command": "python3 ... continuity --session-key 'session:main:recover'",
                "runbook_status": "needs-followup",
                "requires_action": True,
                "top_risk_session": {
                    "session_key": "session:main:recover",
                    "user_facing_status_counts": {"已阻塞": 1},
                },
                "primary_action": {"kind": "followup-session", "command": "python3 ... continuity --session-key 'session:main:recover'"},
                "runbook": {"status": "needs-followup", "primary_action": {"kind": "followup-session"}, "steps": [], "commands": []},
                "suggested_next_commands": ["python3 ... continuity --session-key 'session:main:recover'"],
                "next_followup_summary": {"session_filter": "session:main:recover"},
            }

        openclaw_hooks.process_overdue_tasks = fake_scan
        openclaw_hooks.auto_resume_watchdog_blocked_main_tasks_if_safe = fake_auto_resume
        try:
            result = openclaw_hooks.watchdog_auto_recover_from_payload(
                {"session_key": "session:main:recover", "limit": 1, "note": "继续推进"},
                config_path=self.config_path,
            )
        finally:
            openclaw_hooks.process_overdue_tasks = original_scan
            openclaw_hooks.auto_resume_watchdog_blocked_main_tasks_if_safe = original_auto_resume

        self.assertEqual(result["status"], "applied")
        self.assertEqual(result["watchdog_findings_count"], 1)
        self.assertEqual(result["watchdog_notified_count"], 1)
        self.assertEqual(result["watchdog_blocked_count"], 1)
        self.assertEqual(result["focus_session_key"], "session:main:recover")
        self.assertEqual(result["control_plane_message"]["event_name"], "watchdog-auto-recover")
        self.assertEqual(result["control_plane_message"]["priority"], "p1-task-management")
        self.assertEqual(result["control_plane_message"]["metadata"]["primary_action_kind"], "followup-session")
        self.assertEqual(result["control_plane_message"]["metadata"]["top_risk_session_key"], "session:main:recover")
        self.assertEqual(
            result["control_plane_message"]["metadata"]["top_risk_session_user_status_counts"],
            {"已阻塞": 1},
        )
        self.assertIn("当前重点 session：session:main:recover（已阻塞:1）", result["control_plane_message"]["text"])

    def test_watchdog_auto_recover_startup_recovery_promotes_stale_running_main_task(self) -> None:
        store = task_state_module.TaskStore(paths=self.paths)
        task = store.register_task(
            agent_id="main",
            session_key="session:main:startup-recover",
            channel="feishu",
            account_id="feishu1-main",
            chat_id="chat:startup-recover",
            user_id="ou_test",
            task_label="startup stale running task",
        )
        running = store.start_task(task.task_id)
        running.last_user_visible_update_at = "2020-01-01T00:00:00+00:00"
        running.last_monitor_notify_at = "2026-04-04T10:00:00+08:00"
        store.save_task(running)

        result = openclaw_hooks.watchdog_auto_recover_from_payload(
            {"startup_recovery": True},
            config_path=self.config_path,
        )

        refreshed = store.load_task(task.task_id, allow_archive=False)
        self.assertEqual(result["startup_recovery"], True)
        self.assertEqual(result["startup_promoted_count"], 1)
        self.assertEqual(result["startup_promoted"][0]["task_id"], task.task_id)
        self.assertEqual(result["startup_promoted"][0]["channel"], "feishu")
        self.assertEqual(result["startup_promoted"][0]["account_id"], "feishu1-main")
        self.assertEqual(result["startup_promoted"][0]["chat_id"], "chat:startup-recover")
        self.assertEqual(result["status"], "applied")
        self.assertEqual(refreshed.status, task_state_module.STATUS_RUNNING)

    def test_watchdog_auto_recover_startup_recovery_repromotes_running_task_with_existing_escalation(self) -> None:
        store = task_state_module.TaskStore(paths=self.paths)
        task = store.register_task(
            agent_id="main",
            session_key="session:main:startup-rerun",
            channel="feishu",
            account_id="feishu1-main",
            chat_id="chat:startup-rerun",
            user_id="ou_test",
            task_label="startup rerun task",
        )
        running = store.start_task(task.task_id)
        running.last_user_visible_update_at = "2020-01-01T00:00:00+00:00"
        running.last_monitor_notify_at = "2026-04-04T10:00:00+08:00"
        running.meta["watchdog_escalation"] = "startup-recovery-stalled-running"
        running.meta["watchdog_escalation_at"] = "2026-04-04T10:00:05+08:00"
        store.save_task(running)

        result = openclaw_hooks.watchdog_auto_recover_from_payload(
            {"startup_recovery": True},
            config_path=self.config_path,
        )

        refreshed = store.load_task(task.task_id, allow_archive=False)
        self.assertEqual(result["startup_recovery"], True)
        self.assertEqual(result["startup_promoted_count"], 1)
        self.assertEqual(result["startup_promoted"][0]["task_id"], task.task_id)
        self.assertEqual(result["status"], "applied")
        self.assertEqual(refreshed.status, task_state_module.STATUS_RUNNING)

    def test_register_from_payload_includes_estimated_wait_seconds(self) -> None:
        store = task_state_module.TaskStore(paths=self.paths)
        done = store.register_task(
            agent_id="main",
            session_key="session:history",
            channel="feishu",
            account_id="feishu1-main",
            chat_id="chat:history",
            task_label="history task",
        )
        started = store.start_task(done.task_id)
        archived = store.complete_task(started.task_id, archive=True)
        archive_path = self.paths.archive_dir / f"{archived.task_id}.json"
        payload = json.loads(archive_path.read_text(encoding="utf-8"))
        payload["created_at"] = "2026-04-04T10:00:00+08:00"
        payload["started_at"] = "2026-04-04T10:00:10+08:00"
        payload["updated_at"] = "2026-04-04T10:00:40+08:00"
        task_state_module.atomic_write_json(archive_path, payload)

        result = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:test-estimate",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:test-estimate",
                "user_id": "ou_test",
                "user_request": "帮我排查这个问题并修复，再验证结果",
                "estimated_steps": 4,
                "needs_verification": True,
            }
        )
        self.assertEqual(result["estimated_wait_seconds"], 30)

    def test_should_send_short_followup_for_queued_task_includes_queue_reason(self) -> None:
        store = task_state_module.TaskStore(paths=self.paths)
        running = store.register_task(
            agent_id="main",
            session_key="session:running",
            channel="feishu",
            account_id="feishu1-main",
            chat_id="chat:running",
            task_label="running task",
        )
        store.start_task(running.task_id)
        queued = store.register_task(
            agent_id="main",
            session_key="session:queued",
            channel="feishu",
            account_id="feishu1-main",
            chat_id="chat:queued",
            task_label="queued task",
        )

        result = openclaw_hooks.should_send_short_followup_from_payload({"task_id": queued.task_id})

        self.assertTrue(result["should_send"])
        self.assertEqual(result["reason"], "task-active:queued")
        self.assertIn("仍在排队处理中", result["followup_message"])
        self.assertIn("前面还有 1 个号", result["followup_message"])
        self.assertIn("control_plane_message", result)
        self.assertEqual(result["control_plane_message"]["event_name"], "short-task-followup")
        self.assertEqual(result["control_plane_message"]["priority"], "p2-progress-followup")
        self.assertEqual(result["control_plane_message"]["task_id"], queued.task_id)
        self.assertEqual(result["control_plane_message"]["text"], result["followup_message"])
        self.assertEqual(result["user_facing_status_code"], "queued")
        self.assertEqual(result["user_facing_status"], "排队中")
        self.assertEqual(result["control_plane_message"]["user_facing_status_code"], "queued")
        self.assertEqual(result["control_plane_message"]["user_facing_status"], "排队中")
        self.assertEqual(result["control_plane_message"]["metadata"]["user_facing_status_code"], "queued")
        self.assertEqual(result["control_plane_message"]["metadata"]["user_facing_status"], "排队中")

    def test_should_send_short_followup_for_queue_head_uses_pending_start_user_status(self) -> None:
        store = task_state_module.TaskStore(paths=self.paths)
        queued = store.register_task(
            agent_id="main",
            session_key="session:queued-head",
            channel="feishu",
            account_id="feishu1-main",
            chat_id="chat:queued-head",
            task_label="queued head task",
        )

        result = openclaw_hooks.should_send_short_followup_from_payload(
            {"task_id": queued.task_id},
            config_path=self.config_path,
        )

        self.assertTrue(result["should_send"])
        self.assertEqual(result["reason"], "task-active:queued")
        self.assertEqual(result["user_facing_status_code"], "pending-start")
        self.assertEqual(result["user_facing_status"], "待开始")
        self.assertIn("当前状态：待开始", result["followup_message"])
        self.assertEqual(result["control_plane_message"]["user_facing_status_code"], "pending-start")
        self.assertEqual(result["control_plane_message"]["user_facing_status"], "待开始")
        self.assertEqual(result["control_plane_message"]["metadata"]["user_facing_status_code"], "pending-start")
        self.assertEqual(result["control_plane_message"]["metadata"]["user_facing_status"], "待开始")

    def test_should_send_short_followup_for_running_task_prefers_last_progress(self) -> None:
        store = task_state_module.TaskStore(paths=self.paths)
        task = store.register_task(
            agent_id="main",
            session_key="session:running-progress",
            channel="feishu",
            account_id="feishu1-main",
            chat_id="chat:running-progress",
            task_label="running progress task",
        )
        store.start_task(task.task_id)
        store.touch_task(
            task.task_id,
            user_visible=False,
            meta={"last_progress_note": "正在检查 webhook 配置"},
        )

        result = openclaw_hooks.should_send_short_followup_from_payload({"task_id": task.task_id})

        self.assertTrue(result["should_send"])
        self.assertEqual(result["reason"], "task-active:running")
        self.assertIn("最近进展", result["followup_message"])
        self.assertIn("正在检查 webhook 配置", result["followup_message"])
        self.assertEqual(result["control_plane_message"]["task_status"], "running")
        self.assertEqual(result["control_plane_message"]["text"], result["followup_message"])
        self.assertEqual(result["user_facing_status_code"], "running")
        self.assertEqual(result["user_facing_status"], "处理中")
        self.assertEqual(result["control_plane_message"]["user_facing_status_code"], "running")
        self.assertEqual(result["control_plane_message"]["user_facing_status"], "处理中")

    def test_taskmonitor_control_can_toggle_session(self) -> None:
        off = openclaw_hooks.taskmonitor_control_from_payload(
            {
                "session_key": "session:taskmonitor",
                "action": "off",
            }
        )
        self.assertTrue(off["ok"])
        self.assertFalse(off["enabled"])

        status = openclaw_hooks.taskmonitor_status_from_payload(
            {
                "session_key": "session:taskmonitor",
            }
        )
        self.assertTrue(status["ok"])
        self.assertFalse(status["enabled"])

        on = openclaw_hooks.taskmonitor_control_from_payload(
            {
                "session_key": "session:taskmonitor",
                "action": "on",
            }
        )
        self.assertTrue(on["ok"])
        self.assertTrue(on["enabled"])

    def test_activate_latest_promotes_observed_task(self) -> None:
        registered = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:activate",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:activate",
                "user_id": "ou_test",
                "user_request": "看一下",
                "observe_only": True,
            }
        )
        self.assertEqual(registered["task_status"], task_state_module.STATUS_RECEIVED)
        activated = openclaw_hooks.activate_latest_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:activate",
            }
        )
        self.assertTrue(activated["updated"])
        self.assertEqual(activated["reason"], "promoted-observed-task")
        self.assertEqual(activated["task"]["status"], task_state_module.STATUS_RUNNING)

    def test_activate_latest_prefers_requested_observed_task_over_older_active_task(self) -> None:
        first = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:activate-requested",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:activate-requested",
                "user_id": "ou_test",
                "user_request": "第一个任务",
                "estimated_steps": 3,
            }
        )
        second = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:activate-requested",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:activate-requested",
                "user_id": "ou_test",
                "user_request": "在么",
                "observe_only": True,
            }
        )
        self.assertEqual(second["task_status"], task_state_module.STATUS_RECEIVED)

        activated = openclaw_hooks.activate_latest_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:activate-requested",
                "task_id": second["task_id"],
            }
        )
        self.assertTrue(activated["updated"])
        self.assertEqual(activated["reason"], "promoted-requested-task")
        self.assertEqual(activated["task"]["task_id"], second["task_id"])
        self.assertEqual(activated["task"]["status"], task_state_module.STATUS_QUEUED)

        resolved = openclaw_hooks.resolve_active_task_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:activate-requested",
                "task_id": second["task_id"],
            }
        )
        self.assertTrue(resolved["found"])
        self.assertEqual(resolved["task_id"], second["task_id"])

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
        self.assertEqual(task["control_plane_message"]["event_name"], "task-completed")
        self.assertEqual(task["control_plane_message"]["priority"], "p1-task-management")
        self.assertEqual(task["control_plane_message"]["task_id"], task_id)
        self.assertIn("hook finished", task["control_plane_message"]["text"])

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
        self.assertEqual(finalized["control_plane_message"]["event_name"], "task-completed")
        self.assertIn("completed by agent_end", finalized["control_plane_message"]["text"])

    def test_should_send_short_followup_only_for_active_tasks(self) -> None:
        registration = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:followup-check",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:followup-check",
                "user_request": "在么",
                "observe_only": True,
            }
        )
        task_id = registration["task_id"]
        assert task_id is not None

        active_check = openclaw_hooks.should_send_short_followup_from_payload(
            {
                "task_id": task_id,
            }
        )
        self.assertTrue(active_check["should_send"])
        self.assertEqual(active_check["reason"], "task-active:received")

        openclaw_hooks.finalize_active_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:followup-check",
                "task_id": task_id,
                "success": True,
                "has_visible_output": True,
                "result_summary": "在。",
            }
        )

        inactive_check = openclaw_hooks.should_send_short_followup_from_payload(
            {
                "task_id": task_id,
            }
        )
        self.assertFalse(inactive_check["should_send"])
        self.assertEqual(inactive_check["reason"], "task-not-found")

    def test_finalize_active_uses_requested_task_binding(self) -> None:
        first = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:finalize-requested",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:finalize-requested",
                "user_request": "第一个任务",
                "estimated_steps": 3,
            }
        )
        second = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:finalize-requested",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:finalize-requested",
                "user_request": "在么",
                "observe_only": True,
            }
        )
        openclaw_hooks.activate_latest_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:finalize-requested",
                "task_id": second["task_id"],
            }
        )
        updated = openclaw_hooks.progress_active_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:finalize-requested",
                "task_id": second["task_id"],
                "progress_note": "已开始处理最新消息。",
            }
        )
        self.assertTrue(updated["updated"])

        finalized = openclaw_hooks.finalize_active_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:finalize-requested",
                "task_id": second["task_id"],
                "success": True,
                "result_summary": "最新消息已处理完成",
            }
        )
        self.assertTrue(finalized["updated"])
        self.assertEqual(finalized["task"]["task_id"], second["task_id"])
        self.assertEqual(finalized["task"]["status"], task_state_module.STATUS_DONE)

        original = openclaw_hooks.resolve_active_task_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:finalize-requested",
                "task_id": first["task_id"],
            }
        )
        self.assertTrue(original["found"])
        self.assertEqual(original["task_id"], first["task_id"])

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
        self.assertEqual(finalized["control_plane_message"]["event_name"], "task-failed")
        self.assertTrue(str(finalized["control_plane_message"]["text"]).startswith("当前任务已失败"))

    def test_taskmonitor_control_returns_control_plane_message(self) -> None:
        off = openclaw_hooks.taskmonitor_control_from_payload(
            {
                "session_key": "session:taskmonitor-control-plane",
                "action": "off",
            }
        )
        self.assertTrue(off["ok"])
        self.assertEqual(off["control_plane_message"]["event_name"], "taskmonitor-disabled")
        self.assertEqual(off["control_plane_message"]["priority"], "p1-task-management")
        self.assertEqual(off["control_plane_message"]["session_key"], "session:taskmonitor-control-plane")

    def test_resume_main_task_returns_control_plane_message(self) -> None:
        registration = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:resume-control-plane",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:resume-control-plane",
                "user_request": "继续处理这个较长任务并同步进展",
                "estimated_steps": 3,
            }
        )
        task_id = registration["task_id"]
        assert task_id is not None
        openclaw_hooks.activate_latest_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:resume-control-plane",
                "task_id": task_id,
            }
        )
        openclaw_hooks.blocked_active_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:resume-control-plane",
                "reason": "waiting-on-user-confirmation",
            }
        )

        resumed = openclaw_hooks.resume_main_task_from_payload(
            {
                "task_id": task_id,
                "progress_note": "继续推进并同步真实进展",
            },
            config_path=self.config_path,
        )

        self.assertTrue(resumed["updated"])
        self.assertEqual(resumed["task"]["task_id"], task_id)
        self.assertEqual(resumed["control_plane_message"]["event_name"], "task-resumed")
        self.assertEqual(resumed["control_plane_message"]["priority"], "p1-task-management")
        self.assertEqual(resumed["control_plane_message"]["task_id"], task_id)

    def test_cancel_main_queue_task_returns_control_plane_message(self) -> None:
        running_registration = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:cancel-control-plane:running",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:cancel-control-plane:running",
                "user_request": "先处理这个占位长任务",
                "estimated_steps": 3,
            },
            config_path=self.config_path,
        )
        running_task_id = running_registration["task_id"]
        assert running_task_id is not None
        openclaw_hooks.activate_latest_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:cancel-control-plane:running",
                "task_id": running_task_id,
            }
        )

        registration = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:cancel-control-plane",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:cancel-control-plane",
                "user_request": "帮我继续排队处理这个任务",
                "estimated_steps": 3,
            },
            config_path=self.config_path,
        )
        task_id = registration["task_id"]
        assert task_id is not None

        cancelled = openclaw_hooks.cancel_main_queue_task_from_payload(
            {
                "task_id": task_id,
                "reason": "user requested queued task cancel",
            },
            config_path=self.config_path,
        )

        self.assertEqual(cancelled["action"], "cancelled-queued-task")
        self.assertEqual(cancelled["task_id"], task_id)
        self.assertEqual(cancelled["control_plane_message"]["event_name"], "task-cancelled")
        self.assertEqual(cancelled["control_plane_message"]["priority"], "p1-task-management")
        self.assertEqual(cancelled["control_plane_message"]["task_id"], task_id)
        self.assertEqual(cancelled["control_plane_message"]["metadata"]["queue_position"], 1)

    def test_main_continuity_wrapper_returns_control_plane_message_for_idle_state(self) -> None:
        summary = openclaw_hooks.main_continuity_from_payload({}, config_path=self.config_path)

        self.assertEqual(summary["runbook_status"], "ok")
        self.assertIn("control_plane_message", summary)
        self.assertEqual(summary["control_plane_message"]["event_name"], "continuity-summary")
        self.assertEqual(summary["control_plane_message"]["priority"], "p1-task-management")

    def test_main_continuity_wrapper_reports_focus_session_in_control_plane_message(self) -> None:
        store = task_state_module.TaskStore(paths=self.paths)
        task = store.register_task(
            agent_id="main",
            session_key="session:continuity-wrapper",
            channel="telegram",
            chat_id="chat:continuity-wrapper",
            task_label="continuity wrapper task",
        )
        running = store.start_task(task.task_id)
        running.last_user_visible_update_at = "2020-01-01T00:00:00+00:00"
        running.meta["finalize_skipped_reason"] = "success-without-visible-progress"
        store.save_task(running)

        silence_monitor = load_runtime_module("silence_monitor")
        silence_monitor.process_overdue_tasks(paths=self.paths)

        summary = openclaw_hooks.main_continuity_from_payload(
            {"session_key": "session:continuity-wrapper"},
            config_path=self.config_path,
        )

        self.assertEqual(summary["runbook_status"], "warn")
        self.assertEqual(summary["control_plane_message"]["event_name"], "continuity-summary")
        self.assertEqual(summary["control_plane_message"]["session_key"], "session:continuity-wrapper")
        self.assertEqual(summary["control_plane_message"]["metadata"]["top_risk_session_key"], "session:continuity-wrapper")
        self.assertEqual(
            summary["control_plane_message"]["metadata"]["top_risk_session_user_status_code_counts"],
            {"blocked": 1},
        )
        self.assertEqual(
            summary["control_plane_message"]["metadata"]["top_risk_session_user_status_counts"],
            {"已阻塞": 1},
        )

    def test_main_tasks_summary_wrapper_reports_session_tasks(self) -> None:
        store = task_state_module.TaskStore(paths=self.paths)
        running = store.register_task(
            agent_id="main",
            session_key="session:tasks-wrapper",
            channel="telegram",
            chat_id="chat:tasks-wrapper",
            task_label="正在处理的任务",
        )
        store.start_task(running.task_id)
        queued = store.register_task(
            agent_id="main",
            session_key="session:tasks-wrapper",
            channel="telegram",
            chat_id="chat:tasks-wrapper",
            task_label="排队中的任务",
        )

        summary = openclaw_hooks.main_tasks_summary_from_payload(
            {"session_key": "session:tasks-wrapper"},
            config_path=self.config_path,
        )

        self.assertEqual(summary["task_count"], 2)
        self.assertEqual(summary["control_plane_message"]["event_name"], "main-tasks-summary")
        self.assertEqual(summary["control_plane_message"]["priority"], "p1-task-management")
        self.assertEqual(summary["control_plane_message"]["session_key"], "session:tasks-wrapper")
        self.assertIn("当前会话共有 2 条活动任务", summary["control_plane_message"]["text"])
        self.assertIn("处理中", summary["control_plane_message"]["text"])
        self.assertIn("排队中", summary["control_plane_message"]["text"])
        self.assertEqual(summary["tasks"][0]["user_facing_status"], "处理中")
        self.assertEqual(summary["tasks"][1]["user_facing_status"], "排队中")

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

    def test_finalize_active_marks_done_for_short_success_when_visible_output_exists(self) -> None:
        registration = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:short-visible-output",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:short-visible-output",
                "user_request": "在么",
                "observe_only": True,
            }
        )
        assert registration["task_id"] is not None
        openclaw_hooks.activate_latest_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:short-visible-output",
                "task_id": registration["task_id"],
            }
        )
        finalized = openclaw_hooks.finalize_active_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:short-visible-output",
                "task_id": registration["task_id"],
                "success": True,
                "has_visible_output": True,
                "result_summary": "在。",
            }
        )
        self.assertTrue(finalized["updated"])
        self.assertEqual(finalized["task"]["status"], task_state_module.STATUS_DONE)

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

    def test_finalize_active_does_not_materialize_legacy_post_run_followup(self) -> None:
        registration = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:compound-followup",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:compound-followup",
                "user_request": "你先查一下天气，然后5分钟后回复我信息；",
                "estimated_steps": 2,
            }
        )
        assert registration["task_id"] is not None
        finalized = openclaw_hooks.finalize_active_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:compound-followup",
                "task_id": registration["task_id"],
                "success": True,
                "has_visible_output": True,
                "result_summary": "天气接口本轮没有返回内容，我 5 分钟后再回来跟进。",
            }
        )
        self.assertTrue(finalized["updated"])
        self.assertEqual(finalized["task"]["status"], task_state_module.STATUS_DONE)
        self.assertNotIn("post_run_continuation_task_id", finalized["task"]["meta"])

    def test_fulfill_due_continuation_matches_due_reply_and_archives_task(self) -> None:
        store = task_state_module.TaskStore(paths=self.paths)
        observed = store.observe_task(
            agent_id="main",
            session_key="session:continuation-due",
            channel="telegram",
            account_id="default",
            chat_id="tg:test",
            task_label="continuation due",
        )
        scheduled = store.schedule_continuation(
            observed.task_id,
            continuation_kind="delayed-reply",
            due_at="2000-01-01T00:00:00+08:00",
            payload={"reply_text": "ok1", "wait_seconds": 1},
            reason="scheduled continuation wait",
        )

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
        store = task_state_module.TaskStore(paths=self.paths)
        observed = store.observe_task(
            agent_id="main",
            session_key="session:continuation-not-due",
            channel="telegram",
            account_id="default",
            chat_id="tg:test",
            task_label="continuation not due",
        )
        scheduled = store.schedule_continuation(
            observed.task_id,
            continuation_kind="delayed-reply",
            due_at="2099-01-01T00:00:00+08:00",
            payload={"reply_text": "ok1", "wait_seconds": 60},
            reason="scheduled continuation wait",
        )

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
        store = task_state_module.TaskStore(paths=self.paths)
        observed = store.observe_task(
            agent_id="main",
            session_key="session:wake",
            channel="telegram",
            account_id="default",
            chat_id="tg:test",
            task_label="wake task",
        )
        scheduled = store.schedule_continuation(
            observed.task_id,
            continuation_kind="delayed-reply",
            due_at="2099-01-01T00:00:00+08:00",
            payload={"reply_text": "ok1", "wait_seconds": 60},
            reason="scheduled continuation wait",
        )
        task_id = scheduled.task_id

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
        store = task_state_module.TaskStore(paths=self.paths)
        observed = store.observe_task(
            agent_id="main",
            session_key="session:wake-missing",
            channel="telegram",
            account_id="default",
            chat_id="tg:test",
            task_label="wake missing",
        )
        scheduled = store.schedule_continuation(
            observed.task_id,
            continuation_kind="delayed-reply",
            due_at="2099-01-01T00:00:00+08:00",
            payload={"reply_text": "ok1", "wait_seconds": 60},
            reason="scheduled continuation wait",
        )
        task_id = scheduled.task_id
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
        store = task_state_module.TaskStore(paths=self.paths)
        observed = store.observe_task(
            agent_id="main",
            session_key="session:delayed",
            channel="telegram",
            account_id="telegram-main",
            chat_id="chat:delayed",
            task_label="delayed task",
        )
        scheduled = store.schedule_continuation(
            observed.task_id,
            continuation_kind="delayed-reply",
            due_at="2020-01-01T00:00:00+00:00",
            payload={"reply_text": "ok1", "wait_seconds": 1},
            reason="scheduled continuation wait",
        )
        task_path = self.paths.inflight_dir / f"{scheduled.task_id}.json"

        claimed = openclaw_hooks.claim_due_continuations_from_payload({})
        self.assertEqual(claimed["claimed_count"], 1)
        self.assertEqual(claimed["tasks"][0]["reply_text"], "ok1")

        refreshed = json.loads(task_path.read_text(encoding="utf-8"))
        self.assertEqual(refreshed["status"], task_state_module.STATUS_RUNNING)
        self.assertEqual(refreshed["meta"]["continuation_state"], "claimed")

    def test_claim_due_continuations_sorts_same_due_tasks_by_creation_order(self) -> None:
        store = task_state_module.TaskStore(paths=self.paths)
        due_at = "2020-01-01T00:00:00+00:00"
        replies = ["111", "222", "333"]
        for index, reply in enumerate(replies):
            observed = store.observe_task(
                agent_id="main",
                session_key=f"session:delayed:{index}",
                channel="telegram",
                account_id="telegram-main",
                chat_id=f"chat:delayed:{index}",
                task_label=f"delayed task {index}",
            )
            store.schedule_continuation(
                observed.task_id,
                continuation_kind="delayed-reply",
                due_at=due_at,
                payload={"reply_text": reply, "wait_seconds": index + 1},
                reason="scheduled continuation wait",
            )

        claimed = openclaw_hooks.claim_due_continuations_from_payload({})

        self.assertEqual(claimed["claimed_count"], 3)
        self.assertEqual([item["reply_text"] for item in claimed["tasks"]], replies)

    def test_claim_due_continuations_limits_to_one_task_per_session_lane(self) -> None:
        store = task_state_module.TaskStore(paths=self.paths)
        due_at = "2020-01-01T00:00:00+00:00"
        observed_first = store.observe_task(
            agent_id="main",
            session_key="session:delayed:same-lane",
            channel="telegram",
            account_id="telegram-main",
            chat_id="chat:delayed:same-lane",
            task_label="delayed task 1",
        )
        store.schedule_continuation(
            observed_first.task_id,
            continuation_kind="delayed-reply",
            due_at=due_at,
            payload={"reply_text": "111", "wait_seconds": 1},
            reason="scheduled continuation wait",
        )
        observed_second = store.observe_task(
            agent_id="main",
            session_key="session:delayed:same-lane",
            channel="telegram",
            account_id="telegram-main",
            chat_id="chat:delayed:same-lane",
            task_label="delayed task 2",
        )
        second = store.schedule_continuation(
            observed_second.task_id,
            continuation_kind="delayed-reply",
            due_at=due_at,
            payload={"reply_text": "222", "wait_seconds": 2},
            reason="scheduled continuation wait",
        )

        claimed = openclaw_hooks.claim_due_continuations_from_payload({})

        self.assertEqual(claimed["claimed_count"], 1)
        self.assertEqual([item["reply_text"] for item in claimed["tasks"]], ["111"])
        refreshed_second = store.load_task(second.task_id, allow_archive=False)
        self.assertEqual(refreshed_second.status, task_state_module.STATUS_PAUSED)

    def test_claim_due_continuations_can_handoff_next_task_after_first_completion(self) -> None:
        store = task_state_module.TaskStore(paths=self.paths)
        due_at = "2020-01-01T00:00:00+00:00"
        replies = ["111", "222"]
        scheduled_ids: list[str] = []
        for reply in replies:
            observed = store.observe_task(
                agent_id="main",
                session_key="session:delayed:handoff",
                channel="telegram",
                account_id="telegram-main",
                chat_id="chat:delayed:handoff",
                task_label=f"delayed task {reply}",
            )
            scheduled = store.schedule_continuation(
                observed.task_id,
                continuation_kind="delayed-reply",
                due_at=due_at,
                payload={"reply_text": reply, "wait_seconds": 1},
                reason="scheduled continuation wait",
            )
            scheduled_ids.append(scheduled.task_id)

        first_claim = openclaw_hooks.claim_due_continuations_from_payload({})

        self.assertEqual(first_claim["claimed_count"], 1)
        self.assertEqual([item["reply_text"] for item in first_claim["tasks"]], ["111"])

        completed = openclaw_hooks.completed_from_payload(
            {
                "task_id": first_claim["tasks"][0]["task_id"],
                "result_summary": "continuation reply delivered: 111",
            }
        )
        self.assertEqual(completed["status"], task_state_module.STATUS_DONE)

        second_claim = openclaw_hooks.claim_due_continuations_from_payload({})

        self.assertEqual(second_claim["claimed_count"], 1)
        self.assertEqual([item["reply_text"] for item in second_claim["tasks"]], ["222"])
        refreshed_first = store.load_task(scheduled_ids[0])
        refreshed_second = store.load_task(scheduled_ids[1], allow_archive=False)
        self.assertEqual(refreshed_first.status, task_state_module.STATUS_DONE)
        self.assertEqual(refreshed_second.status, task_state_module.STATUS_RUNNING)


if __name__ == "__main__":
    unittest.main()
