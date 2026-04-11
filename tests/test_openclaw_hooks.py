from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
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
        self.assertIn("routing_decision", result)
        self.assertEqual(result["routing_decision"], decision["routing_decision"])
        self.assertEqual(result["routing_decision"]["routing_status"], "decided")
        self.assertEqual(result["routing_decision"]["classification"], "queueing")
        self.assertEqual(result["routing_decision"]["execution_decision"], "queue-as-new-task")
        self.assertIsInstance(result["wd_receipt"], dict)
        self.assertTrue(str(result["wd_receipt"]["user_visible_wd"]).startswith("[wd]"))
        self.assertIsInstance(result["control_plane_message"], dict)
        self.assertEqual(result["control_plane_message"]["event_name"], "same-session-routing-receipt")
        self.assertEqual(result["control_plane_message"]["priority"], "p0-receive-ack")
        self.assertIn("排第", str(result["control_plane_message"]["text"]))
        self.assertIn("排第", str(result["wd_receipt"]["user_visible_wd"]))

    def test_register_from_payload_records_same_session_followup_routing_context(self) -> None:
        first = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:same-session-followup",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:same-session-followup",
                "user_id": "ou_test",
                "user_request": "先帮我整理这份需求",
            }
        )

        second = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:same-session-followup",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:same-session-followup",
                "user_id": "ou_test",
                "user_request": "再补充一个边界条件",
                "observe_only": True,
            }
        )
        routing = second["routing_decision"]
        self.assertEqual(routing["routing_status"], "decided")
        self.assertTrue(routing["same_session_followup"])
        self.assertEqual(routing["classification"], "steering")
        self.assertEqual(routing["execution_decision"], "interrupt-and-restart")
        self.assertEqual(routing["reason_code"], "active-task-safe-restart")
        self.assertEqual(routing["active_task_id"], first["task_id"])
        self.assertEqual(routing["target_task_id"], second["task_id"])
        self.assertEqual(routing["wd_receipt"]["decision"], "interrupt-and-restart")
        self.assertTrue(str(second["control_plane_message"]["text"]).startswith("当前任务已按这次更新重新开始"))

        task = task_state_module.TaskStore(paths=self.paths).load_task(second["task_id"])
        self.assertEqual(task.meta.get("same_session_routing"), routing)

    def test_register_from_payload_reuses_stale_observed_task_with_merge_receipt(self) -> None:
        first = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:stale-observed-takeover",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:stale-observed-takeover",
                "user_id": "ou_test",
                "user_request": "在么",
                "observe_only": True,
            }
        )
        store = task_state_module.TaskStore(paths=self.paths)

        second = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:stale-observed-takeover",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:stale-observed-takeover",
                "user_id": "ou_test",
                "user_request": "帮我写一份简历，自己看情况写",
                "observe_only": True,
            }
        )

        self.assertEqual(second["task_id"], first["task_id"])
        routing = second["routing_decision"]
        self.assertTrue(routing["same_session_followup"])
        self.assertEqual(routing["classification"], "steering")
        self.assertEqual(routing["execution_decision"], "merge-before-start")
        self.assertEqual(routing["reason_code"], "stale-observed-task-takeover")
        self.assertEqual(second["wd_receipt"]["decision"], "merge-before-start")
        self.assertTrue(str(second["control_plane_message"]["text"]).startswith("这次更新已并入当前任务"))

        reused = store.load_task(first["task_id"])
        self.assertEqual(reused.meta.get("original_user_request"), "帮我写一份简历，自己看情况写")
        self.assertEqual(reused.monitor_state, "normal")

    def test_register_from_payload_loads_same_session_classifier_from_config(self) -> None:
        classifier_script = self.temp_dir / "same_session_classifier.py"
        classifier_script.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "import json",
                    "import sys",
                    "payload = json.load(sys.stdin)",
                    'print(json.dumps({"classification": "queueing", "confidence": 0.91, "needs_confirmation": False, "reason_code": "config-driven-classifier", "reason_text": f\'Classifier handled: {payload.get(\"new_message\")}\'}, ensure_ascii=False))',
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        self.config_path.write_text(
            json.dumps(
                {
                    "taskSystem": {
                        "storageDir": str(self.paths.data_dir),
                        "agents": {
                            "main": {
                                "sameSessionRouting": {
                                    "enabled": True,
                                    "classifier": {
                                        "enabled": True,
                                        "command": [sys.executable, str(classifier_script)],
                                        "timeoutMs": 1000,
                                        "minConfidence": 0.75,
                                    },
                                }
                            }
                        },
                    }
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        first = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:config-classifier",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:config-classifier",
                "user_id": "ou_test",
                "user_request": "Please rewrite this resume",
                "estimated_steps": 3,
            },
            config_path=self.config_path,
        )
        second = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:config-classifier",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:config-classifier",
                "user_id": "ou_test",
                "user_request": "再来一个版本",
                "observe_only": True,
            },
            config_path=self.config_path,
        )

        routing = second["routing_decision"]
        self.assertEqual(routing["decision_source"], "classifier")
        self.assertTrue(routing["classifier_invoked"])
        self.assertEqual(routing["classification"], "queueing")
        self.assertEqual(routing["execution_decision"], "queue-as-new-task")
        self.assertEqual(routing["reason_code"], "config-driven-classifier")
        self.assertEqual(routing["active_task_id"], first["task_id"])

    def test_register_from_payload_activates_collecting_window_without_registering_task(self) -> None:
        self.config_path.write_text(
            json.dumps(
                {
                    "taskSystem": {
                        "storageDir": str(self.paths.data_dir),
                        "agents": {"main": {"sameSessionRouting": {"collectingWindowSeconds": 9}}},
                    }
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        result = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:collecting-window",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:collecting-window",
                "user_id": "ou_test",
                "user_request": "我接下来会连续发三条，你先别开始",
            },
            config_path=self.config_path,
        )
        self.assertFalse(result["should_register_task"])
        self.assertIsNone(result["task_id"])
        self.assertEqual(result["routing_decision"]["classification"], "collect-more")
        self.assertEqual(result["routing_decision"]["execution_decision"], "enter-collecting-window")
        self.assertEqual(result["session_state"]["status"], "collecting")
        self.assertEqual(result["session_state"]["window_seconds"], 9)
        self.assertEqual(result["session_state"]["buffered_message_count"], 0)

    def test_register_from_payload_buffers_messages_while_collecting_window_is_active(self) -> None:
        first = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:collecting-window-buffer",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:collecting-window-buffer",
                "user_id": "ou_test",
                "user_request": "我接下来会连续发三条，你先别开始",
            }
        )
        self.assertFalse(first["should_register_task"])

        second = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:collecting-window-buffer",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:collecting-window-buffer",
                "user_id": "ou_test",
                "user_request": "第一条：整理目录",
            }
        )
        self.assertFalse(second["should_register_task"])
        self.assertEqual(second["classification_reason"], "collecting-window-buffered")
        self.assertEqual(second["routing_decision"]["reason_code"], "collecting-window-active")
        self.assertEqual(second["session_state"]["buffered_message_count"], 1)

    def test_claim_due_collecting_windows_materializes_buffered_request(self) -> None:
        openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:collecting-window-due",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:collecting-window-due",
                "user_id": "ou_test",
                "user_request": "我接下来会连续发三条，你先别开始",
            }
        )
        openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:collecting-window-due",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:collecting-window-due",
                "user_id": "ou_test",
                "user_request": "第一条：整理目录",
            }
        )
        openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:collecting-window-due",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:collecting-window-due",
                "user_id": "ou_test",
                "user_request": "第二条：补 README",
            }
        )
        session_dir = self.paths.data_dir / "sessions"
        session_path = next(session_dir.glob("*.json"))
        state = json.loads(session_path.read_text(encoding="utf-8"))
        collecting = dict(state["same_session_collecting"])
        collecting["expires_at"] = (datetime.now(timezone.utc).astimezone() - timedelta(seconds=1)).isoformat()
        state["same_session_collecting"] = collecting
        session_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        claimed = openclaw_hooks.claim_due_collecting_windows_from_payload({}, config_path=self.config_path)
        self.assertEqual(claimed["claimed_count"], 1)
        task_payload = claimed["tasks"][0]
        self.assertEqual(task_payload["session_key"], "session:collecting-window-due")
        self.assertIn("第一条：整理目录", task_payload["combined_user_request"])
        self.assertIn("第二条：补 README", task_payload["combined_user_request"])

        store = task_state_module.TaskStore(paths=self.paths)
        task = store.load_task(task_payload["task_id"], allow_archive=False)
        self.assertIn("第一条：整理目录", str(task.meta.get("original_user_request") or ""))
        self.assertIn("第二条：补 README", str(task.meta.get("original_user_request") or ""))

    def test_claim_due_collecting_windows_releases_existing_prestart_task(self) -> None:
        first = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:collecting-window-existing-task",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:collecting-window-existing-task",
                "user_id": "ou_test",
                "user_request": "帮我整理这个目录",
                "observe_only": True,
            }
        )
        self.assertTrue(first["should_register_task"])
        openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:collecting-window-existing-task",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:collecting-window-existing-task",
                "user_id": "ou_test",
                "user_request": "我接下来会连续发两条，你先别开始",
            }
        )
        session_dir = self.paths.data_dir / "sessions"
        session_path = next(session_dir.glob("*.json"))
        state = json.loads(session_path.read_text(encoding="utf-8"))
        collecting = dict(state["same_session_collecting"])
        collecting["expires_at"] = (datetime.now(timezone.utc).astimezone() - timedelta(seconds=1)).isoformat()
        state["same_session_collecting"] = collecting
        session_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        claimed = openclaw_hooks.claim_due_collecting_windows_from_payload({}, config_path=self.config_path)
        self.assertEqual(claimed["claimed_count"], 1)
        task_payload = claimed["tasks"][0]
        self.assertEqual(task_payload["task_id"], first["task_id"])

    def test_sync_source_reply_target_updates_task_meta(self) -> None:
        registered = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:reply-target",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:reply-target",
                "user_id": "ou_test",
                "user_request": "帮我查一下天气",
                "observe_only": True,
            },
            config_path=self.config_path,
        )
        result = openclaw_hooks.dispatch(
            "sync-source-reply-target",
            {
                "agent_id": "main",
                "session_key": "session:reply-target",
                "task_id": registered["task_id"],
                "reply_to_id": "om_source_message",
                "thread_id": "thread_source",
            },
            config_path=self.config_path,
        )
        self.assertTrue(result["updated"])
        task = task_state_module.TaskStore(paths=self.paths).load_task(registered["task_id"])
        self.assertEqual(task.meta.get("source_reply_to_id"), "om_source_message")
        self.assertEqual(task.meta.get("source_thread_id"), "thread_source")

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

    def test_should_send_short_followup_for_running_task_explains_pending_plan_materialization(self) -> None:
        store = task_state_module.TaskStore(paths=self.paths)
        task = store.register_task(
            agent_id="main",
            session_key="session:running-plan",
            channel="feishu",
            account_id="feishu1-main",
            chat_id="chat:running-plan",
            task_label="running planned task",
        )
        store.start_task(task.task_id)
        store.touch_task(
            task.task_id,
            user_visible=False,
            meta={
                "tool_followup_plan": {
                    "plan_id": "plan_123",
                    "status": "planned",
                    "followup_due_at": "2099-01-01T00:05:00+00:00",
                    "followup_summary": "5分钟后同步结论",
                }
            },
        )

        result = openclaw_hooks.should_send_short_followup_from_payload({"task_id": task.task_id})

        self.assertTrue(result["should_send"])
        self.assertIn("正在把 5分钟后同步结论 物化成真实 follow-up 任务", result["followup_message"])
        self.assertEqual(result["control_plane_message"]["metadata"]["planning_plan_status"], "planned")
        self.assertEqual(result["control_plane_message"]["metadata"]["planning_followup_summary"], "5分钟后同步结论")

    def test_should_send_short_followup_for_running_task_reports_planning_anomaly(self) -> None:
        store = task_state_module.TaskStore(paths=self.paths)
        task = store.register_task(
            agent_id="main",
            session_key="session:running-anomaly",
            channel="feishu",
            account_id="feishu1-main",
            chat_id="chat:running-anomaly",
            task_label="running anomaly task",
        )
        store.start_task(task.task_id)
        store.touch_task(
            task.task_id,
            user_visible=False,
            meta={
                "planning_anomaly": "promise-without-task",
                "planning_promise_guard": {
                    "promise_summary": "10分钟后提醒看结果",
                    "status": "anomaly",
                },
            },
        )

        result = openclaw_hooks.should_send_short_followup_from_payload({"task_id": task.task_id})

        self.assertTrue(result["should_send"])
        self.assertIn("还没有成功落成真实任务", result["followup_message"])
        self.assertIn("我会补建真实任务", result["followup_message"])
        self.assertEqual(result["control_plane_message"]["metadata"]["planning_anomaly"], "promise-without-task")
        self.assertEqual(result["control_plane_message"]["metadata"]["planning_promise_summary"], "10分钟后提醒看结果")
        self.assertEqual(
            result["control_plane_message"]["metadata"]["planning_recovery_hint"],
            "inspect-source-task-and-recreate-or-clear-promise",
        )

    def test_should_send_short_followup_for_running_task_reports_planner_timeout(self) -> None:
        store = task_state_module.TaskStore(paths=self.paths)
        task = store.register_task(
            agent_id="main",
            session_key="session:running-timeout",
            channel="feishu",
            account_id="feishu1-main",
            chat_id="chat:running-timeout",
            task_label="running timeout task",
        )
        store.start_task(task.task_id)
        store.touch_task(
            task.task_id,
            user_visible=False,
            meta={
                "planning_anomaly": "planner-timeout",
                "planning_promise_guard": {
                    "promise_summary": "10分钟后同步结果",
                    "status": "timeout",
                },
                "tool_followup_plan": {
                    "status": "timeout",
                    "followup_summary": "10分钟后同步结果",
                },
            },
        )

        result = openclaw_hooks.should_send_short_followup_from_payload({"task_id": task.task_id})

        self.assertTrue(result["should_send"])
        self.assertIn("planning 路径刚才超时了", result["followup_message"])
        self.assertEqual(result["control_plane_message"]["metadata"]["planning_anomaly"], "planner-timeout")
        self.assertEqual(
            result["control_plane_message"]["metadata"]["planning_recovery_hint"],
            "inspect-source-task-after-planner-timeout",
        )

    def test_should_send_short_followup_for_running_task_reports_missing_followup_task(self) -> None:
        store = task_state_module.TaskStore(paths=self.paths)
        task = store.register_task(
            agent_id="main",
            session_key="session:running-missing-followup-task",
            channel="feishu",
            account_id="feishu1-main",
            chat_id="chat:running-missing-followup-task",
            task_label="running missing follow-up task",
        )
        store.start_task(task.task_id)
        store.touch_task(
            task.task_id,
            user_visible=False,
            meta={
                "planning_promise_guard": {
                    "promise_summary": "10分钟后同步结果",
                    "status": "scheduled",
                },
                "tool_followup_plan": {
                    "status": "scheduled",
                    "followup_summary": "10分钟后同步结果",
                    "followup_task_id": "task_missing_followup_record",
                },
            },
        )

        result = openclaw_hooks.should_send_short_followup_from_payload({"task_id": task.task_id})

        self.assertTrue(result["should_send"])
        self.assertIn("真实任务记录缺失了", result["followup_message"])
        self.assertIn("补建或重新关联", result["followup_message"])
        self.assertEqual(result["control_plane_message"]["metadata"]["planning_anomaly"], "followup-task-missing")
        self.assertEqual(
            result["control_plane_message"]["metadata"]["planning_recovery_hint"],
            "inspect-source-task-and-relink-followup-task",
        )

    def test_should_send_short_followup_for_running_task_reports_overdue_materialization(self) -> None:
        store = task_state_module.TaskStore(paths=self.paths)
        task = store.register_task(
            agent_id="main",
            session_key="session:running-overdue-materialize",
            channel="telegram",
            chat_id="chat:running-overdue-materialize",
            task_label="running overdue materialization task",
        )
        store.start_task(task.task_id)
        task = store.load_task(task.task_id, allow_archive=False)
        followup = store.observe_task(
            agent_id="main",
            session_key="session:running-overdue-materialize",
            channel="telegram",
            chat_id="chat:running-overdue-materialize",
            task_label="late materialized follow-up",
            meta={"source": "tool-followup-plan", "plan_id": "plan_late_materialize"},
        )
        task.meta.update(
            {
                "tool_followup_plan": {
                    "plan_id": "plan_late_materialize",
                    "status": "scheduled",
                    "followup_due_at": "2000-01-01T00:00:00+00:00",
                    "followup_task_id": followup.task_id,
                    "followup_summary": "5分钟后同步结果",
                    "overdue_on_materialize": True,
                },
                "planning_promise_guard": {
                    "status": "scheduled",
                    "expected_by_finalize": True,
                    "promise_summary": "5分钟后同步结果",
                },
            }
        )
        store.save_task(task)

        result = openclaw_hooks.should_send_short_followup_from_payload(
            {"task_id": task.task_id},
            config_path=self.config_path,
        )

        self.assertTrue(result["should_send"])
        self.assertIn("已过原定时间后才落成", result["followup_message"])
        self.assertIn("重新约定新的时间", result["followup_message"])
        self.assertEqual(result["control_plane_message"]["metadata"]["planning_anomaly"], None)
        self.assertEqual(
            result["control_plane_message"]["metadata"]["planning_recovery_hint"],
            "inspect-source-task-and-reschedule-late-followup",
        )

    def test_should_send_short_followup_for_running_task_reports_current_stage(self) -> None:
        store = task_state_module.TaskStore(paths=self.paths)
        task = store.register_task(
            agent_id="main",
            session_key="session:running-stage-summary",
            channel="feishu",
            account_id="feishu1-main",
            chat_id="chat:running-stage-summary",
            task_label="整理发布说明",
            meta={
                "original_user_request": "整理发布说明并给出上线建议",
                "estimated_steps": 4,
            },
        )
        store.start_task(task.task_id)

        result = openclaw_hooks.should_send_short_followup_from_payload({"task_id": task.task_id})

        self.assertTrue(result["should_send"])
        self.assertIn("正在推进：整理发布说明并给出上线建议", result["followup_message"])
        self.assertIn("预计约 4 个阶段", result["followup_message"])
        self.assertIn("第 1 个阶段", result["followup_message"])
        self.assertEqual(result["control_plane_message"]["metadata"]["running_target"], "整理发布说明并给出上线建议")
        self.assertEqual(result["control_plane_message"]["metadata"]["estimated_steps"], 4)
        self.assertEqual(result["control_plane_message"]["metadata"]["progress_update_count"], 0)
        self.assertEqual(result["control_plane_message"]["metadata"]["current_stage"], 1)

    def test_progress_from_payload_increments_progress_update_count(self) -> None:
        store = task_state_module.TaskStore(paths=self.paths)
        task = store.register_task(
            agent_id="main",
            session_key="session:progress-count",
            channel="feishu",
            account_id="feishu1-main",
            chat_id="chat:progress-count",
            task_label="progress count task",
            meta={"estimated_steps": 4},
        )
        store.start_task(task.task_id)

        updated = openclaw_hooks.progress_from_payload(
            {
                "task_id": task.task_id,
                "progress_note": "已完成仓库扫描",
            }
        )

        self.assertEqual(updated["meta"]["progress_update_count"], 1)
        self.assertTrue(str(updated["meta"]["last_progress_note_at"]).strip())

    def test_should_send_short_followup_for_running_task_uses_stage_summary_after_progress_updates(self) -> None:
        store = task_state_module.TaskStore(paths=self.paths)
        task = store.register_task(
            agent_id="main",
            session_key="session:running-stage-progress",
            channel="feishu",
            account_id="feishu1-main",
            chat_id="chat:running-stage-progress",
            task_label="修复支付回调",
            meta={"estimated_steps": 4},
        )
        store.start_task(task.task_id)
        store.touch_task(
            task.task_id,
            user_visible=False,
            meta={"progress_update_count": 2},
        )

        result = openclaw_hooks.should_send_short_followup_from_payload({"task_id": task.task_id})

        self.assertTrue(result["should_send"])
        self.assertIn("正在推进：修复支付回调", result["followup_message"])
        self.assertIn("第 3 个阶段", result["followup_message"])
        self.assertEqual(result["control_plane_message"]["metadata"]["progress_update_count"], 2)
        self.assertEqual(result["control_plane_message"]["metadata"]["current_stage"], 3)

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

    def test_resolve_active_exposes_structured_gate_from_promise_guard(self) -> None:
        registration = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:promise-gate",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:promise-gate",
                "user_request": "2分钟后提醒我查天气",
                "estimated_steps": 2,
            }
        )
        task_id = registration["task_id"]
        assert task_id is not None

        guarded = openclaw_hooks.attach_promise_guard_from_payload(
            {
                "source_task_id": task_id,
                "promise_summary": "2分钟后同步天气结果",
                "followup_due_at": "2026-04-06T19:07:33+08:00",
            }
        )
        self.assertTrue(guarded["armed"])
        self.assertTrue(guarded["require_structured_user_content"])
        self.assertEqual(guarded["main_user_content_mode"], "none")

        resolved = openclaw_hooks.resolve_active_task_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:promise-gate",
                "task_id": task_id,
            }
        )
        self.assertTrue(resolved["found"])
        self.assertTrue(resolved["require_structured_user_content"])
        self.assertEqual(resolved["main_user_content_mode"], "none")

    def test_create_followup_plan_and_schedule_materializes_real_followup_task(self) -> None:
        registration = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:planning-materialize",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:planning-materialize",
                "user_request": "先查天气，5分钟后回来同步结果",
                "estimated_steps": 3,
            },
            config_path=self.config_path,
        )
        task_id = registration["task_id"]
        assert task_id is not None

        plan = openclaw_hooks.create_followup_plan_from_payload(
            {
                "source_task_id": task_id,
                "followup_kind": "delayed-reply",
                "followup_due_at": "2099-01-01T00:05:00+00:00",
                "followup_message": "5分钟后回来同步天气结果",
                "followup_summary": "5分钟后同步天气结果",
                "main_user_content_mode": "none",
                "reply_to_id": "om_source_message",
                "thread_id": "thread_source_message",
            },
            config_path=self.config_path,
        )
        self.assertTrue(plan["accepted"])

        scheduled = openclaw_hooks.schedule_followup_from_plan_from_payload(
            {
                "source_task_id": task_id,
                "plan_id": plan["plan_id"],
            },
            config_path=self.config_path,
        )
        self.assertTrue(scheduled["scheduled"])
        self.assertEqual(scheduled["status"], task_state_module.STATUS_PAUSED)
        followup_task_id = scheduled["task_id"]

        store = task_state_module.TaskStore(paths=self.paths)
        source = store.load_task(task_id, allow_archive=False)
        followup = store.load_task(followup_task_id, allow_archive=False)
        self.assertEqual(source.meta["tool_followup_plan"]["status"], "scheduled")
        self.assertEqual(source.meta["tool_followup_plan"]["followup_task_id"], followup_task_id)
        self.assertEqual(followup.meta["continuation_kind"], "delayed-reply")
        self.assertEqual(followup.meta["continuation_due_at"], "2099-01-01T00:05:00+00:00")
        self.assertEqual(followup.meta["continuation_payload"]["reply_text"], "5分钟后回来同步天气结果")

    def test_create_followup_plan_and_schedule_preserve_plain_followup_message(self) -> None:
        registration = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:planning-materialize-plain",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:planning-materialize-plain",
                "user_request": "先查天气，5分钟后回来同步结果",
                "estimated_steps": 3,
            },
            config_path=self.config_path,
        )
        task_id = registration["task_id"]
        assert task_id is not None

        plan = openclaw_hooks.create_followup_plan_from_payload(
            {
                "source_task_id": task_id,
                "followup_kind": "delayed-reply",
                "followup_due_at": "2099-01-01T00:05:00+00:00",
                "followup_message": "5分钟后回来同步天气结果",
                "main_user_content_mode": "none",
            },
            config_path=self.config_path,
        )
        self.assertTrue(plan["accepted"])

        scheduled = openclaw_hooks.schedule_followup_from_plan_from_payload(
            {
                "source_task_id": task_id,
                "plan_id": plan["plan_id"],
            },
            config_path=self.config_path,
        )
        self.assertTrue(scheduled["scheduled"])

        store = task_state_module.TaskStore(paths=self.paths)
        source = store.load_task(task_id, allow_archive=False)
        followup = store.load_task(scheduled["task_id"], allow_archive=False)
        self.assertEqual(
            source.meta["tool_followup_plan"]["followup_message"],
            "5分钟后回来同步天气结果",
        )
        self.assertEqual(
            source.meta["tool_followup_plan"]["followup_summary"],
            "5分钟后回来同步天气结果",
        )

    def test_create_followup_plan_derives_summary_from_time_expression_and_message(self) -> None:
        registration = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:planning-summary-fallback",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:planning-summary-fallback",
                "user_request": "先查天气，之后回来汇报",
                "estimated_steps": 3,
            },
            config_path=self.config_path,
        )
        task_id = registration["task_id"]
        assert task_id is not None

        plan = openclaw_hooks.create_followup_plan_from_payload(
            {
                "source_task_id": task_id,
                "followup_kind": "delayed-reply",
                "followup_due_at": "2099-01-01T00:05:00+00:00",
                "original_time_expression": "5分钟后",
                "followup_message": "回来继续汇报天气结果",
                "main_user_content_mode": "none",
            },
            config_path=self.config_path,
        )

        self.assertTrue(plan["accepted"])
        self.assertEqual(plan["runtime_contract"]["followup_summary"], "5分钟后回来继续汇报天气结果")

        finalized = openclaw_hooks.finalize_planned_followup_from_payload(
            {
                "source_task_id": task_id,
                "plan_id": plan["plan_id"],
            },
            config_path=self.config_path,
        )
        self.assertEqual(finalized["followup_summary"], "5分钟后回来继续汇报天气结果")

    def test_finalize_planned_followup_marks_promise_without_task_anomaly(self) -> None:
        registration = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:planning-anomaly",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:planning-anomaly",
                "user_request": "10分钟后提醒我看结果",
                "estimated_steps": 2,
            },
            config_path=self.config_path,
        )
        task_id = registration["task_id"]
        assert task_id is not None

        guarded = openclaw_hooks.attach_promise_guard_from_payload(
            {
                "source_task_id": task_id,
                "promise_summary": "10分钟后提醒看结果",
                "followup_due_at": "2099-01-01T00:10:00+00:00",
            },
            config_path=self.config_path,
        )
        self.assertTrue(guarded["armed"])

        plan = openclaw_hooks.create_followup_plan_from_payload(
            {
                "source_task_id": task_id,
                "followup_due_at": "2099-01-01T00:10:00+00:00",
                "followup_message": "10分钟后提醒你看结果",
                "followup_summary": "10分钟后提醒看结果",
                "main_user_content_mode": "none",
            },
            config_path=self.config_path,
        )
        self.assertTrue(plan["accepted"])

        finalized = openclaw_hooks.finalize_planned_followup_from_payload(
            {
                "source_task_id": task_id,
                "plan_id": plan["plan_id"],
            },
            config_path=self.config_path,
        )
        self.assertFalse(finalized["ok"])
        self.assertFalse(finalized["promise_fulfilled"])
        self.assertEqual(finalized["reason"], "promise-without-task")

        store = task_state_module.TaskStore(paths=self.paths)
        source = store.load_task(task_id, allow_archive=False)
        self.assertEqual(source.meta["planning_anomaly"], "promise-without-task")
        self.assertEqual(source.meta["planning_promise_guard"]["status"], "anomaly")
        self.assertEqual(source.meta["tool_followup_plan"]["status"], "anomaly")

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

    def test_finalize_active_uses_task_target_for_generic_completion_receipt(self) -> None:
        registration = openclaw_hooks.register_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:generic-completion-receipt",
                "channel": "feishu",
                "account_id": "feishu1-main",
                "chat_id": "chat:generic-completion-receipt",
                "user_request": "帮我继续排查这个问题并回我结果",
                "estimated_steps": 3,
            }
        )
        assert registration["task_id"] is not None
        openclaw_hooks.activate_latest_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:generic-completion-receipt",
                "task_id": registration["task_id"],
            }
        )
        finalized = openclaw_hooks.finalize_active_from_payload(
            {
                "agent_id": "main",
                "session_key": "session:generic-completion-receipt",
                "task_id": registration["task_id"],
                "success": True,
                "has_visible_output": True,
                "result_summary": "",
            }
        )
        self.assertTrue(finalized["updated"])
        self.assertEqual(
            finalized["control_plane_message"]["text"],
            "当前任务已完成：帮我继续排查这个问题并回我结果",
        )

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
        store = task_state_module.TaskStore(paths=self.paths)
        task = store.load_task(registration["task_id"], allow_archive=False)
        task.meta["post_run_continuation_plan"] = {
            "kind": "delayed-reply",
            "due_at": "2099-01-01T00:05:00+00:00",
            "reply_text": "5 分钟后回来同步",
            "wait_seconds": 300,
        }
        store.save_task(task)
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
        self.assertNotIn("post_run_continuation_plan", finalized["task"]["meta"])
        self.assertNotIn("post_run_continuation_task_id", finalized["task"]["meta"])
        self.assertEqual(
            finalized["task"]["meta"]["legacy_post_run_continuation_reason"],
            "structured-tool-plan-required",
        )

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

    def test_claim_due_continuations_claims_all_due_tasks_in_same_session_lane(self) -> None:
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

        self.assertEqual(claimed["claimed_count"], 2)
        self.assertEqual([item["reply_text"] for item in claimed["tasks"]], ["111", "222"])
        refreshed_second = store.load_task(second.task_id, allow_archive=False)
        self.assertEqual(refreshed_second.status, task_state_module.STATUS_RUNNING)

    def test_claim_due_continuations_orders_tasks_by_due_time_within_same_session(self) -> None:
        store = task_state_module.TaskStore(paths=self.paths)
        plans = [
            ("333", "2020-01-01T00:03:00+00:00"),
            ("555", "2020-01-01T00:05:00+00:00"),
            ("111", "2020-01-01T00:01:00+00:00"),
        ]
        for reply, due_at in plans:
            observed = store.observe_task(
                agent_id="main",
                session_key="session:delayed:due-order",
                channel="telegram",
                account_id="telegram-main",
                chat_id="chat:delayed:due-order",
                task_label=f"delayed task {reply}",
            )
            store.schedule_continuation(
                observed.task_id,
                continuation_kind="delayed-reply",
                due_at=due_at,
                payload={"reply_text": reply, "wait_seconds": 1},
                reason="scheduled continuation wait",
            )

        claimed = openclaw_hooks.claim_due_continuations_from_payload({})

        self.assertEqual(claimed["claimed_count"], 3)
        self.assertEqual([item["reply_text"] for item in claimed["tasks"]], ["111", "333", "555"])

    def test_claim_due_continuations_is_not_blocked_by_running_main_task_in_same_session(self) -> None:
        store = task_state_module.TaskStore(paths=self.paths)
        session_key = "session:delayed:running-main"
        running = store.observe_task(
            agent_id="main",
            session_key=session_key,
            channel="telegram",
            account_id="telegram-main",
            chat_id="chat:delayed:running-main",
            task_label="long running main task",
        )
        running.status = task_state_module.STATUS_RUNNING
        store.save_task(running)

        observed = store.observe_task(
            agent_id="main",
            session_key=session_key,
            channel="telegram",
            account_id="telegram-main",
            chat_id="chat:delayed:running-main",
            task_label="delayed follow-up",
        )
        scheduled = store.schedule_continuation(
            observed.task_id,
            continuation_kind="delayed-reply",
            due_at="2020-01-01T00:00:00+00:00",
            payload={"reply_text": "111", "wait_seconds": 1},
            reason="scheduled continuation wait",
        )

        claimed = openclaw_hooks.claim_due_continuations_from_payload({})

        self.assertEqual(claimed["claimed_count"], 1)
        self.assertEqual([item["reply_text"] for item in claimed["tasks"]], ["111"])
        refreshed = store.load_task(scheduled.task_id, allow_archive=False)
        self.assertEqual(refreshed.status, task_state_module.STATUS_RUNNING)


if __name__ == "__main__":
    unittest.main()
