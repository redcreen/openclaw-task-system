from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime_loader import load_runtime_module, task_state_module


main_ops = load_runtime_module("main_ops")


class MainOpsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="task-system-main-ops-tests."))
        self.paths = task_state_module.TaskPaths.from_root(self.temp_dir)
        self.store = task_state_module.TaskStore(paths=self.paths)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _config_path(self) -> Path:
        config_path = self.temp_dir / "task_system.json"
        config_path.write_text(
            json.dumps({"taskSystem": {"storageDir": str(self.paths.data_dir)}}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return config_path

    def test_list_main_tasks_filters_non_main_agents(self) -> None:
        main_task = self.store.register_task(
            agent_id="main",
            session_key="session:main",
            channel="telegram",
            chat_id="chat:main",
            task_label="main task",
        )
        self.store.register_task(
            agent_id="code",
            session_key="session:code",
            channel="telegram",
            chat_id="chat:code",
            task_label="code task",
        )

        tasks = main_ops.list_main_tasks(paths=self.paths)

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["task_id"], main_task.task_id)

    def test_render_main_list_includes_main_task(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:main",
            channel="telegram",
            chat_id="chat:main",
            task_label="visible main task",
        )

        rendered = main_ops.render_main_list(paths=self.paths)

        self.assertIn("# Main Tasks", rendered)
        self.assertIn(task.task_id, rendered)

    def test_render_main_health_includes_blocked_main_count(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:main",
            channel="telegram",
            chat_id="chat:main",
            task_label="blocked main task",
        )
        self.store.block_task(task.task_id, "waiting")

        rendered = main_ops.render_main_health(paths=self.paths)

        self.assertIn("# Main Ops Health", rendered)
        self.assertIn("- main_blocked_task_count: 1", rendered)

    def test_render_taskmonitor_status_reports_default_enabled(self) -> None:
        rendered = main_ops.render_taskmonitor_status("session:taskmonitor", config_path=self._config_path())

        self.assertIn("# TaskMonitor", rendered)
        self.assertIn("- session_key: session:taskmonitor", rendered)
        self.assertIn("- enabled: True", rendered)
        self.assertIn("- explicitly_overridden: False", rendered)

    def test_get_taskmonitor_status_reports_default_enabled(self) -> None:
        status = main_ops.get_taskmonitor_status("session:taskmonitor", config_path=self._config_path())

        self.assertEqual(status["session_key"], "session:taskmonitor")
        self.assertTrue(status["enabled"])
        self.assertFalse(status["explicitly_overridden"])
        self.assertEqual(status["override_count"], 0)

    def test_set_taskmonitor_state_updates_override_and_list(self) -> None:
        result = main_ops.set_taskmonitor_state(
            "session:taskmonitor",
            False,
            config_path=self._config_path(),
        )

        self.assertFalse(result["enabled"])
        rendered = main_ops.render_taskmonitor_overrides(config_path=self._config_path())
        self.assertIn("# TaskMonitor Overrides", rendered)
        self.assertIn("session:taskmonitor | enabled=False", rendered)

    def test_get_taskmonitor_overrides_returns_structured_list(self) -> None:
        main_ops.set_taskmonitor_state(
            "session:taskmonitor",
            False,
            config_path=self._config_path(),
        )

        overrides = main_ops.get_taskmonitor_overrides(config_path=self._config_path())

        self.assertEqual(overrides["override_count"], 1)
        self.assertEqual(overrides["overrides"][0]["session_key"], "session:taskmonitor")
        self.assertFalse(overrides["overrides"][0]["enabled"])

    def test_render_main_dashboard_reports_unified_summary(self) -> None:
        rendered = main_ops.render_main_dashboard(config_path=self._config_path(), paths=self.paths)

        self.assertIn("# Main Ops Dashboard", rendered)
        self.assertIn("- status: ok", rendered)
        self.assertIn("- queue_count: 0", rendered)
        self.assertIn("- lane_agent_count: 0", rendered)
        self.assertIn("- continuity_auto_resumable_task_count: 0", rendered)
        self.assertIn("- top_followup_session: none", rendered)
        self.assertIn("- action_hint: No immediate action needed.", rendered)
        self.assertIn("- action_hint_command: none", rendered)
        self.assertIn("main_ops.py continuity --json", rendered)

    def test_get_main_dashboard_summary_warns_when_continuity_risk_exists(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:main:dashboard-risk",
            channel="telegram",
            chat_id="chat:main:dashboard-risk",
            task_label="dashboard blocked task",
        )
        running = self.store.start_task(task.task_id)
        running.last_user_visible_update_at = "2020-01-01T00:00:00+00:00"
        running.meta["finalize_skipped_reason"] = "success-without-visible-progress"
        self.store.save_task(running)

        silence_monitor = load_runtime_module("silence_monitor")
        silence_monitor.process_overdue_tasks(paths=self.paths)

        summary = main_ops.get_main_dashboard_summary(config_path=self._config_path(), paths=self.paths)

        self.assertEqual(summary["status"], "warn")
        self.assertEqual(summary["continuity"]["auto_resumable_task_count"], 1)
        self.assertEqual(summary["top_followup_session"]["session_key"], "session:main:dashboard-risk")
        self.assertEqual(summary["top_followup_session"]["auto_resumable_count"], 1)
        self.assertEqual(summary["action_hint"], "Follow up session session:main:dashboard-risk first.")
        self.assertEqual(
            summary["action_hint_command"],
            "python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --session-key 'session:main:dashboard-risk'",
        )
        self.assertEqual(
            summary["suggested_next_commands"][0],
            "python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --session-key 'session:main:dashboard-risk'",
        )
        self.assertEqual(summary["health"]["main_blocked_task_count"], 1)
        self.assertEqual(summary["queues"]["queue_count"], 0)
        self.assertEqual(summary["taskmonitor"]["override_count"], 0)

    def test_render_main_dashboard_can_focus_one_session(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:main:dashboard-focus",
            channel="telegram",
            chat_id="chat:main:dashboard-focus",
            task_label="dashboard focus task",
        )
        self.store.start_task(task.task_id)

        rendered = main_ops.render_main_dashboard(
            config_path=self._config_path(),
            paths=self.paths,
            session_key="session:main:dashboard-focus",
        )

        self.assertIn("- session_filter: session:main:dashboard-focus", rendered)
        self.assertIn("- top_followup_session: none", rendered)
        self.assertIn("- action_hint: Review current lanes before changing queue behavior.", rendered)
        self.assertIn("- action_hint_command: python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py lanes --json", rendered)
        self.assertIn("main_ops.py continuity --session-key 'session:main:dashboard-focus'", rendered)
        self.assertIn("taskmonitor --session-key 'session:main:dashboard-focus' --action status --json", rendered)

    def test_render_main_dashboard_compact_uses_short_summary(self) -> None:
        rendered = main_ops.render_main_dashboard(
            config_path=self._config_path(),
            paths=self.paths,
            compact=True,
        )

        self.assertIn("# Main Ops Dashboard", rendered)
        self.assertIn("- scope: all", rendered)
        self.assertIn("- status: ok", rendered)
        self.assertIn("- continuity_risk: auto=0 manual=0", rendered)
        self.assertIn("- top_followup_session: none", rendered)
        self.assertIn("- action_hint: No immediate action needed.", rendered)
        self.assertIn("- action_hint_command: none", rendered)
        self.assertNotIn("## Commands", rendered)

    def test_render_main_dashboard_only_issues_reports_clean_state_briefly(self) -> None:
        rendered = main_ops.render_main_dashboard(
            config_path=self._config_path(),
            paths=self.paths,
            only_issues=True,
        )

        self.assertIn("# Main Ops Dashboard", rendered)
        self.assertIn("- scope: all", rendered)
        self.assertIn("- status: ok", rendered)
        self.assertIn("- No issues detected.", rendered)
        self.assertNotIn("## Commands", rendered)

    def test_render_main_dashboard_only_issues_focuses_on_problem_fields(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:main:issues-only",
            channel="telegram",
            chat_id="chat:main:issues-only",
            task_label="issues only blocked task",
        )
        running = self.store.start_task(task.task_id)
        running.last_user_visible_update_at = "2020-01-01T00:00:00+00:00"
        running.meta["finalize_skipped_reason"] = "success-without-visible-progress"
        self.store.save_task(running)

        silence_monitor = load_runtime_module("silence_monitor")
        silence_monitor.process_overdue_tasks(paths=self.paths)

        rendered = main_ops.render_main_dashboard(
            config_path=self._config_path(),
            paths=self.paths,
            only_issues=True,
        )

        self.assertIn("- status: warn", rendered)
        self.assertIn("- main_blocked_task_count: 1", rendered)
        self.assertIn("- continuity_risk: auto=1 manual=0", rendered)
        self.assertIn("- top_followup_session: session:main:issues-only", rendered)
        self.assertIn("- action_hint: Follow up session session:main:issues-only first.", rendered)
        self.assertIn(
            "- action_hint_command: python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --session-key 'session:main:issues-only'",
            rendered,
        )

    def test_get_main_dashboard_summary_filters_to_one_session(self) -> None:
        focus = self.store.register_task(
            agent_id="main",
            session_key="session:main:dashboard-focus-json",
            channel="telegram",
            chat_id="chat:main:dashboard-focus-json",
            task_label="focus queue task",
        )
        self.store.start_task(focus.task_id)
        other = self.store.register_task(
            agent_id="main",
            session_key="session:main:dashboard-other-json",
            channel="telegram",
            chat_id="chat:main:dashboard-other-json",
            task_label="other queue task",
        )
        self.store.start_task(other.task_id)
        main_ops.set_taskmonitor_state(
            "session:main:dashboard-focus-json",
            False,
            config_path=self._config_path(),
        )

        summary = main_ops.get_main_dashboard_summary(
            config_path=self._config_path(),
            paths=self.paths,
            session_key="session:main:dashboard-focus-json",
        )

        self.assertEqual(summary["session_filter"], "session:main:dashboard-focus-json")
        self.assertEqual(summary["queues"]["queue_count"], 1)
        self.assertEqual(summary["lanes"]["agent_count"], 1)
        self.assertEqual(summary["taskmonitor"]["mode"], "session")
        self.assertEqual(summary["taskmonitor"]["session_key"], "session:main:dashboard-focus-json")
        self.assertFalse(summary["taskmonitor"]["enabled"])
        self.assertEqual(summary["continuity"]["session_filter"], "session:main:dashboard-focus-json")
        self.assertIsNone(summary["top_followup_session"])
        self.assertEqual(summary["action_hint"], "Review current lanes before changing queue behavior.")
        self.assertEqual(
            summary["action_hint_command"],
            "python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py lanes --json",
        )

    def test_get_main_dashboard_summary_includes_compact_summary(self) -> None:
        summary = main_ops.get_main_dashboard_summary(
            config_path=self._config_path(),
            paths=self.paths,
            compact=True,
        )

        self.assertTrue(summary["compact"])
        self.assertEqual(summary["compact_summary"]["scope"], "all")
        self.assertEqual(summary["compact_summary"]["status"], "ok")
        self.assertEqual(summary["compact_summary"]["top_followup_session_summary"], "none")
        self.assertEqual(summary["compact_summary"]["action_hint"], "No immediate action needed.")
        self.assertEqual(summary["action_hint"], "No immediate action needed.")
        self.assertIsNone(summary["action_hint_command"])
        self.assertEqual(summary["compact_summary"]["action_hint_command_summary"], "none")
        self.assertEqual(summary["compact_summary"]["taskmonitor_summary"], "override_count=0")

    def test_get_main_dashboard_summary_includes_issue_summary(self) -> None:
        summary = main_ops.get_main_dashboard_summary(
            config_path=self._config_path(),
            paths=self.paths,
            only_issues=True,
        )

        self.assertTrue(summary["only_issues"])
        self.assertFalse(summary["issue_summary"]["has_issues"])
        self.assertIsNone(summary["issue_summary"]["action_hint"])
        self.assertIsNone(summary["issue_summary"]["action_hint_command"])

    def test_get_main_dashboard_summary_can_hint_taskmonitor_enable_for_session(self) -> None:
        main_ops.set_taskmonitor_state(
            "session:main:dashboard-taskmonitor-off",
            False,
            config_path=self._config_path(),
        )

        summary = main_ops.get_main_dashboard_summary(
            config_path=self._config_path(),
            paths=self.paths,
            session_key="session:main:dashboard-taskmonitor-off",
        )

        self.assertEqual(
            summary["action_hint"],
            "Taskmonitor is disabled for session:main:dashboard-taskmonitor-off; re-enable if you want watchdog coverage.",
        )
        self.assertEqual(
            summary["action_hint_command"],
            "python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py taskmonitor --session-key 'session:main:dashboard-taskmonitor-off' --action on",
        )

    def test_render_main_continuity_reports_no_risk_when_idle(self) -> None:
        rendered = main_ops.render_main_continuity(config_path=self._config_path(), paths=self.paths)

        self.assertIn("# Main Continuity", rendered)
        self.assertIn("- session_filter: all", rendered)
        self.assertIn("- top_risk_session: none", rendered)
        self.assertIn("- No continuity risk is currently detected for main.", rendered)

    def test_get_main_continuity_summary_reports_empty_state(self) -> None:
        summary = main_ops.get_main_continuity_summary(config_path=self._config_path(), paths=self.paths)

        self.assertEqual(summary["session_filter"], "all")
        self.assertEqual(summary["active_monitored_task_count"], 0)
        self.assertIsNone(summary["top_risk_session"])
        self.assertEqual(summary["auto_resumable"], [])
        self.assertEqual(summary["manual_review"], [])
        self.assertEqual(summary["not_recommended"], [])
        self.assertEqual(summary["by_session"], [])

    def test_render_main_continuity_includes_watchdog_blocked_task(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:main:blocked",
            channel="telegram",
            chat_id="chat:main:blocked",
            task_label="blocked main task",
        )
        running = self.store.start_task(task.task_id)
        running.last_user_visible_update_at = "2020-01-01T00:00:00+00:00"
        running.meta["finalize_skipped_reason"] = "success-without-visible-progress"
        self.store.save_task(running)

        silence_monitor = load_runtime_module("silence_monitor")
        silence_monitor.process_overdue_tasks(paths=self.paths)

        rendered = main_ops.render_main_continuity(config_path=self._config_path(), paths=self.paths)

        self.assertIn("## Auto-Resumable", rendered)
        self.assertIn("- top_risk_session: session:main:blocked", rendered)
        self.assertIn("blocked-no-visible-progress", rendered)
        self.assertIn("main_ops.py resume", rendered)
        self.assertIn("main_ops.py continuity --session-key 'session:main:blocked'", rendered)
        self.assertIn("main_ops.py lanes --json", rendered)
        self.assertIn("- execution_recommendation: parallel-safe", rendered)
        self.assertIn("## Execution Plan", rendered)
        self.assertIn("Run a dry-run first to preview which watchdog-blocked tasks are eligible.", rendered)

    def test_render_main_continuity_separates_manual_review_and_not_recommended(self) -> None:
        queued = self.store.register_task(
            agent_id="main",
            session_key="session:main:queued",
            channel="telegram",
            chat_id="chat:main:queued",
            task_label="queued overdue task",
        )
        queued_task = self.store.start_task(queued.task_id)
        queued_task.last_user_visible_update_at = "2020-01-01T00:00:00+00:00"
        self.store.save_task(queued_task)

        blocked = self.store.register_task(
            agent_id="main",
            session_key="session:main:blocked:manual",
            channel="telegram",
            chat_id="chat:main:blocked:manual",
            task_label="manual blocked task",
        )
        self.store.block_task(blocked.task_id, "waiting for human confirmation")

        rendered = main_ops.render_main_continuity(config_path=self._config_path(), paths=self.paths)

        self.assertIn("## Needs Manual Review", rendered)
        self.assertIn("queued overdue task", rendered)
        self.assertIn("## Not Recommended For Auto Resume", rendered)
        self.assertIn("waiting for human confirmation", rendered)
        self.assertIn("main_ops.py show", rendered)
        self.assertIn("## By Session", rendered)
        self.assertIn("session:main:queued | auto_resumable=0 | manual_review=1 | not_recommended=0", rendered)
        self.assertIn("session:main:blocked:manual | auto_resumable=0 | manual_review=0 | not_recommended=1", rendered)

    def test_render_main_continuity_can_filter_to_one_session(self) -> None:
        queued = self.store.register_task(
            agent_id="main",
            session_key="session:main:focus",
            channel="telegram",
            chat_id="chat:main:focus",
            task_label="focus overdue task",
        )
        queued_task = self.store.start_task(queued.task_id)
        queued_task.last_user_visible_update_at = "2020-01-01T00:00:00+00:00"
        self.store.save_task(queued_task)

        other = self.store.register_task(
            agent_id="main",
            session_key="session:main:other",
            channel="telegram",
            chat_id="chat:main:other",
            task_label="other blocked task",
        )
        self.store.block_task(other.task_id, "waiting elsewhere")

        rendered = main_ops.render_main_continuity(
            config_path=self._config_path(),
            paths=self.paths,
            session_key="session:main:focus",
        )

        self.assertIn("- session_filter: session:main:focus", rendered)
        self.assertIn("focus overdue task", rendered)
        self.assertNotIn("other blocked task", rendered)
        self.assertIn("session:main:focus | auto_resumable=0 | manual_review=1 | not_recommended=0", rendered)

    def test_get_main_continuity_summary_can_filter_to_one_session(self) -> None:
        focus = self.store.register_task(
            agent_id="main",
            session_key="session:main:focus-json",
            channel="telegram",
            chat_id="chat:main:focus-json",
            task_label="focus json task",
        )
        focus_task = self.store.start_task(focus.task_id)
        focus_task.last_user_visible_update_at = "2020-01-01T00:00:00+00:00"
        self.store.save_task(focus_task)

        other = self.store.register_task(
            agent_id="main",
            session_key="session:main:other-json",
            channel="telegram",
            chat_id="chat:main:other-json",
            task_label="other json task",
        )
        self.store.block_task(other.task_id, "other blocked")

        summary = main_ops.get_main_continuity_summary(
            config_path=self._config_path(),
            paths=self.paths,
            session_key="session:main:focus-json",
        )

        self.assertEqual(summary["session_filter"], "session:main:focus-json")
        self.assertEqual(summary["manual_review_task_count"], 1)
        self.assertEqual(summary["not_recommended_auto_resume_count"], 0)
        self.assertEqual(summary["execution_recommendation"], "parallel-safe")
        self.assertEqual(len(summary["manual_review"]), 1)
        self.assertEqual(summary["manual_review"][0]["task_label"], "focus json task")
        self.assertEqual(len(summary["by_session"]), 1)
        self.assertEqual(summary["by_session"][0]["session_key"], "session:main:focus-json")
        self.assertEqual(summary["top_risk_session"]["session_key"], "session:main:focus-json")
        self.assertEqual(summary["execution_plan"]["execution_recommendation"], "parallel-safe")
        self.assertIn("Inspect continuity and lanes output again after any resume action.", summary["execution_plan"]["steps"])
        self.assertIn(
            "python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --session-key 'session:main:focus-json'",
            summary["suggested_next_commands"],
        )

    def test_resume_watchdog_blocked_main_tasks_resumes_only_selected_candidates(self) -> None:
        first = self.store.register_task(
            agent_id="main",
            session_key="session:main:blocked:one",
            channel="telegram",
            chat_id="chat:main:blocked:one",
            task_label="blocked main task one",
        )
        second = self.store.register_task(
            agent_id="main",
            session_key="session:main:blocked:two",
            channel="telegram",
            chat_id="chat:main:blocked:two",
            task_label="blocked main task two",
        )
        unrelated = self.store.register_task(
            agent_id="main",
            session_key="session:main:manual",
            channel="telegram",
            chat_id="chat:main:manual",
            task_label="manual blocked task",
        )
        self.store.block_task(first.task_id, "watchdog blocked")
        blocked_second = self.store.block_task(second.task_id, "watchdog blocked")
        self.store.block_task(unrelated.task_id, "manual waiting")
        blocked_first = self.store.load_task(first.task_id)
        blocked_first.meta["watchdog_escalation"] = "blocked-no-visible-progress"
        blocked_first.updated_at = "2020-01-01T00:00:00+00:00"
        self.store.save_task(blocked_first)
        blocked_second.meta["watchdog_escalation"] = "blocked-no-visible-progress"
        blocked_second.updated_at = "2020-01-01T00:01:00+00:00"
        self.store.save_task(blocked_second)

        result = main_ops.resume_watchdog_blocked_main_tasks(
            config_path=self._config_path(),
            paths=self.paths,
            limit=1,
            note="继续推进",
        )

        self.assertEqual(result["candidate_count"], 2)
        self.assertEqual(result["eligible_count"], 2)
        self.assertEqual(result["resumed_count"], 1)
        self.assertEqual(result["respect_execution_advice"], False)
        self.assertEqual(result["resumed"][0]["task_id"], first.task_id)
        self.assertEqual(result["post_resume_summary"]["resumed_session_count"], 1)
        self.assertEqual(result["post_resume_summary"]["settled_session_count"], 0)
        self.assertEqual(result["post_resume_summary"]["needs_followup_session_count"], 1)
        self.assertEqual(result["post_resume_summary"]["status_counts"]["running"], 1)
        self.assertEqual(result["post_resume_summary"]["execution_recommendation"], "parallel-safe")
        self.assertEqual(result["post_resume_summary"]["sessions"][0]["session_key"], "session:main:blocked:one")
        self.assertEqual(result["post_resume_summary"]["sessions"][0]["followup_state"], "needs-followup")
        self.assertEqual(
            result["post_resume_summary"]["sessions"][0]["followup_state_reason"],
            "active-tasks-remain-after-resume",
        )
        self.assertEqual(result["post_resume_summary"]["sessions"][0]["followup_priority"], 1)
        self.assertEqual(result["post_resume_summary"]["followup_priorities"][0]["session_key"], "session:main:blocked:one")
        self.assertEqual(result["post_resume_summary"]["top_followup_session"]["session_key"], "session:main:blocked:one")
        self.assertEqual(result["post_resume_summary"]["top_followup_session"]["followup_priority"], 1)
        self.assertEqual(result["post_resume_summary"]["sessions"][0]["status_counts"]["running"], 1)
        self.assertIn(
            "python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --session-key 'session:main:blocked:one'",
            result["suggested_next_commands"],
        )
        resumed_first = self.store.load_task(first.task_id)
        resumed_second = self.store.load_task(second.task_id)
        resumed_unrelated = self.store.load_task(unrelated.task_id)
        self.assertEqual(resumed_first.status, task_state_module.STATUS_RUNNING)
        self.assertEqual(resumed_first.meta["last_progress_note"], "继续推进")
        self.assertEqual(resumed_second.status, "blocked")
        self.assertEqual(resumed_unrelated.status, "blocked")

    def test_resume_watchdog_blocked_main_tasks_can_filter_one_session(self) -> None:
        first = self.store.register_task(
            agent_id="main",
            session_key="session:main:focus",
            channel="telegram",
            chat_id="chat:main:focus",
            task_label="focus blocked task",
        )
        other = self.store.register_task(
            agent_id="main",
            session_key="session:main:other",
            channel="telegram",
            chat_id="chat:main:other",
            task_label="other blocked task",
        )
        blocked_first = self.store.block_task(first.task_id, "watchdog blocked")
        blocked_other = self.store.block_task(other.task_id, "watchdog blocked")
        blocked_first.meta["watchdog_escalation"] = "blocked-no-visible-progress"
        blocked_other.meta["watchdog_escalation"] = "blocked-no-visible-progress"
        self.store.save_task(blocked_first)
        self.store.save_task(blocked_other)

        result = main_ops.resume_watchdog_blocked_main_tasks(
            config_path=self._config_path(),
            paths=self.paths,
            session_key="session:main:focus",
            note="继续推进",
        )

        self.assertEqual(result["session_filter"], "session:main:focus")
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(result["eligible_count"], 1)
        self.assertEqual(result["resumed_count"], 1)
        self.assertEqual(result["resumed"][0]["task_id"], first.task_id)
        self.assertEqual(result["post_resume_summary"]["resumed_session_count"], 1)
        self.assertEqual(result["post_resume_summary"]["settled_session_count"], 0)
        self.assertEqual(result["post_resume_summary"]["needs_followup_session_count"], 1)
        self.assertEqual(result["post_resume_summary"]["status_counts"]["running"], 1)
        self.assertEqual(result["post_resume_summary"]["execution_recommendation"], "parallel-safe")
        self.assertEqual(result["post_resume_summary"]["sessions"][0]["session_key"], "session:main:focus")
        self.assertEqual(result["post_resume_summary"]["sessions"][0]["followup_state"], "needs-followup")
        self.assertEqual(
            result["post_resume_summary"]["sessions"][0]["followup_state_reason"],
            "active-tasks-remain-after-resume",
        )
        self.assertEqual(result["post_resume_summary"]["sessions"][0]["followup_priority"], 1)
        self.assertEqual(result["post_resume_summary"]["top_followup_session"]["session_key"], "session:main:focus")
        self.assertEqual(result["post_resume_summary"]["sessions"][0]["status_counts"]["running"], 1)
        self.assertIn(
            "python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --session-key 'session:main:focus'",
            result["suggested_next_commands"],
        )
        resumed_first = self.store.load_task(first.task_id)
        untouched_other = self.store.load_task(other.task_id)
        self.assertEqual(resumed_first.status, task_state_module.STATUS_RUNNING)
        self.assertEqual(untouched_other.status, "blocked")

    def test_resume_watchdog_blocked_main_tasks_can_respect_serial_execution_advice(self) -> None:
        running = self.store.register_task(
            agent_id="main",
            session_key="session:main:running",
            channel="telegram",
            chat_id="chat:main:running",
            task_label="running task",
        )
        self.store.start_task(running.task_id)
        resumable_same_session = self.store.register_task(
            agent_id="main",
            session_key="session:main:running",
            channel="telegram",
            chat_id="chat:main:running",
            task_label="same-session blocked task",
        )
        resumable_other_session = self.store.register_task(
            agent_id="main",
            session_key="session:main:other",
            channel="telegram",
            chat_id="chat:main:other",
            task_label="other-session blocked task",
        )
        self.store.register_task(
            agent_id="main",
            session_key="session:main:queued",
            channel="telegram",
            chat_id="chat:main:queued",
            task_label="queued sibling task",
        )
        blocked_same = self.store.block_task(resumable_same_session.task_id, "watchdog blocked")
        blocked_other = self.store.block_task(resumable_other_session.task_id, "watchdog blocked")
        blocked_same.meta["watchdog_escalation"] = "blocked-no-visible-progress"
        blocked_other.meta["watchdog_escalation"] = "blocked-no-visible-progress"
        self.store.save_task(blocked_same)
        self.store.save_task(blocked_other)

        result = main_ops.resume_watchdog_blocked_main_tasks(
            config_path=self._config_path(),
            paths=self.paths,
            respect_execution_advice=True,
            note="继续推进",
        )

        self.assertEqual(result["pre_resume_execution_recommendation"], "serial")
        self.assertEqual(result["candidate_count"], 2)
        self.assertEqual(result["eligible_count"], 1)
        self.assertEqual(result["resumed_count"], 1)
        self.assertEqual(result["resumed"][0]["task_id"], resumable_same_session.task_id)
        self.assertEqual(result["post_resume_summary"]["settled_session_count"], 0)
        self.assertEqual(result["post_resume_summary"]["needs_followup_session_count"], 1)
        self.assertEqual(result["post_resume_summary"]["sessions"][0]["session_key"], "session:main:running")
        self.assertEqual(result["post_resume_summary"]["sessions"][0]["followup_state"], "needs-followup")
        self.assertEqual(
            result["post_resume_summary"]["sessions"][0]["followup_state_reason"],
            "active-tasks-remain-after-resume",
        )
        self.assertEqual(result["post_resume_summary"]["sessions"][0]["followup_priority"], 1)
        self.assertEqual(result["post_resume_summary"]["top_followup_session"]["session_key"], "session:main:running")
        self.assertEqual(result["post_resume_summary"]["sessions"][0]["status_counts"]["running"], 1)
        self.assertEqual(result["post_resume_summary"]["sessions"][0]["status_counts"]["queued"], 1)
        self.assertEqual(len(result["skipped"]), 1)
        self.assertEqual(result["skipped"][0]["task_id"], resumable_other_session.task_id)
        resumed_same = self.store.load_task(resumable_same_session.task_id)
        blocked_other_after = self.store.load_task(resumable_other_session.task_id)
        self.assertEqual(resumed_same.status, task_state_module.STATUS_QUEUED)
        self.assertEqual(blocked_other_after.status, "blocked")

    def test_resume_watchdog_blocked_main_tasks_supports_dry_run(self) -> None:
        first = self.store.register_task(
            agent_id="main",
            session_key="session:main:dryrun",
            channel="telegram",
            chat_id="chat:main:dryrun",
            task_label="dry-run blocked task",
        )
        blocked = self.store.block_task(first.task_id, "watchdog blocked")
        blocked.meta["watchdog_escalation"] = "blocked-no-visible-progress"
        self.store.save_task(blocked)

        result = main_ops.resume_watchdog_blocked_main_tasks(
            config_path=self._config_path(),
            paths=self.paths,
            dry_run=True,
            note="继续推进",
        )

        self.assertEqual(result["dry_run"], True)
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(result["eligible_count"], 1)
        self.assertEqual(result["resumed_count"], 1)
        self.assertEqual(result["resumed"][0]["task_id"], first.task_id)
        self.assertEqual(result["resumed"][0]["dry_run"], True)
        self.assertEqual(result["post_resume_summary"]["settled_session_count"], 1)
        self.assertEqual(result["post_resume_summary"]["needs_followup_session_count"], 0)
        self.assertEqual(result["post_resume_summary"]["sessions"][0]["followup_state"], "settled")
        self.assertEqual(
            result["post_resume_summary"]["sessions"][0]["followup_state_reason"],
            "no-active-tasks-after-resume",
        )
        self.assertEqual(result["post_resume_summary"]["followup_priorities"], [])
        self.assertIsNone(result["post_resume_summary"]["top_followup_session"])
        refreshed = self.store.load_task(first.task_id)
        self.assertEqual(refreshed.status, "blocked")

    def test_render_resume_watchdog_blocked_result_groups_followup_state(self) -> None:
        rendered = main_ops.render_resume_watchdog_blocked_result(
            {
                "session_filter": "all",
                "candidate_count": 2,
                "eligible_count": 2,
                "resumed_count": 2,
                "dry_run": False,
                "respect_execution_advice": False,
                "post_resume_summary": {
                    "settled_session_count": 1,
                    "needs_followup_session_count": 1,
                    "execution_recommendation": "parallel-safe",
                    "top_followup_session": {
                        "session_key": "session:main:followup",
                        "followup_priority": 1,
                        "active_task_count": 1,
                        "status_counts": {"running": 1},
                        "next_command": "python3 ... continuity --session-key 'session:main:followup'",
                    },
                    "sessions": [
                        {
                            "session_key": "session:main:followup",
                            "followup_state": "needs-followup",
                            "followup_state_reason": "active-tasks-remain-after-resume",
                            "followup_priority": 1,
                            "active_task_count": 1,
                            "status_counts": {"running": 1},
                            "task_labels": ["followup task"],
                            "next_command": "python3 ... continuity --session-key 'session:main:followup'",
                        },
                        {
                            "session_key": "session:main:settled",
                            "followup_state": "settled",
                            "followup_state_reason": "no-active-tasks-after-resume",
                            "followup_priority": None,
                            "active_task_count": 0,
                            "status_counts": {},
                            "next_command": "python3 ... continuity --session-key 'session:main:settled'",
                        },
                    ],
                },
                "suggested_next_commands": ["python3 ... lanes --json"],
                "skipped": [
                    {
                        "task_id": "task_skip",
                        "session_key": "session:main:skipped",
                        "reason": "blocked-by-serial-execution-advice",
                    }
                ],
            }
        )

        self.assertIn("# Continuity Resume", rendered)
        self.assertIn("## Follow-up Priorities", rendered)
        self.assertIn("P1 | session:main:followup", rendered)
        self.assertIn("reason=active-tasks-remain-after-resume", rendered)
        self.assertIn("## Needs Follow-up", rendered)
        self.assertIn("session:main:followup", rendered)
        self.assertIn("## Settled", rendered)
        self.assertIn("session:main:settled", rendered)
        self.assertIn("reason=no-active-tasks-after-resume", rendered)
        self.assertIn("## Skipped", rendered)
        self.assertIn("blocked-by-serial-execution-advice", rendered)
        self.assertIn("## Suggested Commands", rendered)

    def test_render_queue_lanes_groups_tasks_by_agent_and_session(self) -> None:
        main_running = self.store.register_task(
            agent_id="main",
            session_key="session:main:run",
            channel="telegram",
            chat_id="chat:main:run",
            task_label="main running",
        )
        self.store.start_task(main_running.task_id)
        self.store.register_task(
            agent_id="main",
            session_key="session:main:queued",
            channel="telegram",
            chat_id="chat:main:queued",
            task_label="main queued",
        )
        code_running = self.store.register_task(
            agent_id="code",
            session_key="session:code:run",
            channel="telegram",
            chat_id="chat:code:run",
            task_label="code running",
        )
        self.store.start_task(code_running.task_id)

        rendered = main_ops.render_queue_lanes(paths=self.paths)

        self.assertIn("# Queue Lanes", rendered)
        self.assertIn("## Agent: main", rendered)
        self.assertIn("## Agent: code", rendered)
        self.assertIn("- lane_kind: shared", rendered)
        self.assertIn("- sharing_reason: agent main currently has 2 active sessions in the same lane", rendered)
        self.assertIn("- shared_with_running_lane: True", rendered)
        self.assertIn("- execution_recommendation: serial", rendered)
        self.assertIn("- running_task_count: 1", rendered)
        self.assertIn("- session_lane_count: 2", rendered)
        self.assertIn("- shared_sessions:", rendered)
        self.assertIn("session:main:run", rendered)
        self.assertIn("session:main:queued", rendered)
        self.assertIn("main queued", rendered)
        self.assertIn("code running", rendered)

    def test_get_queue_lanes_summary_reports_agents(self) -> None:
        main_running = self.store.register_task(
            agent_id="main",
            session_key="session:main:run",
            channel="telegram",
            chat_id="chat:main:run",
            task_label="main running",
        )
        self.store.start_task(main_running.task_id)
        code_queued = self.store.register_task(
            agent_id="code",
            session_key="session:code:queued",
            channel="telegram",
            chat_id="chat:code:queued",
            task_label="code queued",
        )

        summary = main_ops.get_queue_lanes_summary(paths=self.paths)

        self.assertEqual(summary["agent_count"], 2)
        self.assertEqual(summary["agents"][0]["agent_id"], "code")
        self.assertEqual(summary["agents"][1]["agent_id"], "main")
        self.assertEqual(summary["agents"][1]["lane_kind"], "single-session")
        self.assertEqual(
            summary["agents"][1]["sharing_reason"],
            "agent main currently has only one active session in the lane",
        )
        self.assertEqual(summary["agents"][1]["shared_with_running_lane"], True)
        self.assertEqual(summary["agents"][1]["execution_recommendation"], "parallel-safe")
        self.assertEqual(summary["agents"][1]["running_task_count"], 1)
        self.assertEqual(summary["agents"][1]["shared_sessions"], [])
        self.assertEqual(summary["agents"][0]["queued_head"][0]["task_id"], code_queued.task_id)

    def test_get_queue_lanes_summary_reports_serial_per_session_for_shared_idle_lane(self) -> None:
        self.store.register_task(
            agent_id="main",
            session_key="session:main:one",
            channel="telegram",
            chat_id="chat:main:one",
            task_label="main queued one",
        )
        self.store.register_task(
            agent_id="main",
            session_key="session:main:two",
            channel="telegram",
            chat_id="chat:main:two",
            task_label="main queued two",
        )

        summary = main_ops.get_queue_lanes_summary(paths=self.paths)

        self.assertEqual(summary["agents"][0]["agent_id"], "main")
        self.assertEqual(summary["agents"][0]["lane_kind"], "shared")
        self.assertEqual(summary["agents"][0]["shared_with_running_lane"], False)
        self.assertEqual(summary["agents"][0]["execution_recommendation"], "serial-per-session")

    def test_render_queue_lanes_includes_due_paused_continuations(self) -> None:
        observed = self.store.observe_task(
            agent_id="main",
            session_key="session:main:delayed",
            channel="telegram",
            account_id="default",
            chat_id="chat:main:delayed",
            task_label="delayed paused",
        )
        self.store.schedule_continuation(
            observed.task_id,
            continuation_kind="delayed-reply",
            due_at="2000-01-01T00:00:00+00:00",
            payload={"reply_text": "111", "wait_seconds": 60},
            reason="scheduled continuation wait",
        )

        rendered = main_ops.render_queue_lanes(paths=self.paths)

        self.assertIn("- paused_task_count: 1", rendered)
        self.assertIn("- due_paused_task_count: 1", rendered)
        self.assertIn("- due_paused_tasks:", rendered)
        self.assertIn("delayed paused", rendered)

    def test_render_queue_topology_groups_sessions_under_agent_queue(self) -> None:
        first = self.store.register_task(
            agent_id="main",
            session_key="session:main:one",
            channel="telegram",
            chat_id="chat:main:one",
            task_label="main task one",
        )
        self.store.start_task(first.task_id)
        self.store.register_task(
            agent_id="main",
            session_key="session:main:two",
            channel="telegram",
            chat_id="chat:main:two",
            task_label="main task two",
        )
        self.store.register_task(
            agent_id="code",
            session_key="session:code:one",
            channel="telegram",
            chat_id="chat:code:one",
            task_label="code task one",
        )

        rendered = main_ops.render_queue_topology(paths=self.paths)

        self.assertIn("# Queue Topology", rendered)
        self.assertIn("- queue_count: 2", rendered)
        self.assertIn("## Queue: main", rendered)
        self.assertIn("- queue_kind: shared", rendered)
        self.assertIn(
            "- sharing_reason: agent main queue is shared because 2 sessions currently map to the same agent queue",
            rendered,
        )
        self.assertIn("- shared_with_running_lane: True", rendered)
        self.assertIn("- execution_recommendation: serial", rendered)
        self.assertIn("- shared_sessions:", rendered)
        self.assertIn("- session_count: 2", rendered)
        self.assertIn("session:main:one | task_count=1", rendered)
        self.assertIn("session:main:two | task_count=1", rendered)
        self.assertIn("## Queue: code", rendered)
        self.assertIn("- queue_kind: single-session", rendered)

    def test_get_queue_topology_summary_reports_queue_structure(self) -> None:
        first = self.store.register_task(
            agent_id="main",
            session_key="session:main:one",
            channel="telegram",
            chat_id="chat:main:one",
            task_label="main task one",
        )
        self.store.start_task(first.task_id)
        self.store.register_task(
            agent_id="main",
            session_key="session:main:two",
            channel="telegram",
            chat_id="chat:main:two",
            task_label="main task two",
        )

        summary = main_ops.get_queue_topology_summary(paths=self.paths)

        self.assertEqual(summary["queue_count"], 1)
        self.assertEqual(summary["queues"][0]["agent_id"], "main")
        self.assertEqual(summary["queues"][0]["queue_kind"], "shared")
        self.assertEqual(
            summary["queues"][0]["sharing_reason"],
            "agent main queue is shared because 2 sessions currently map to the same agent queue",
        )
        self.assertEqual(summary["queues"][0]["shared_with_running_lane"], True)
        self.assertEqual(summary["queues"][0]["execution_recommendation"], "serial")
        self.assertEqual(summary["queues"][0]["shared_sessions"], ["session:main:one", "session:main:two"])
        self.assertEqual(summary["queues"][0]["session_count"], 2)
        self.assertEqual(len(summary["queues"][0]["sessions"]), 2)

    def test_render_main_triage_includes_resume_and_retry_actions(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:main",
            channel="telegram",
            chat_id="chat:main",
            task_label="blocked main task",
        )
        self.store.block_task(task.task_id, "waiting")
        failed_dir = self.paths.data_dir / "failed-instructions"
        failed_dir.mkdir(parents=True, exist_ok=True)
        task_state_module.atomic_write_json(
            failed_dir / "retryable.json",
            {
                "task_id": "retryable",
                "_last_failure_classification": "transport-retryable",
                "_last_failure_retryable": True,
                "_retry_count": 2,
            },
        )
        dispatch_dir = self.paths.data_dir / "dispatch-results"
        dispatch_dir.mkdir(parents=True, exist_ok=True)
        task_state_module.atomic_write_json(
            dispatch_dir / "retryable.json",
            {
                "task_id": "retryable",
                "stderr": "Network request failed with timeout\nHttpError: timeout",
            },
        )
        task_state_module.atomic_write_json(
            failed_dir / "nonretryable.json",
            {
                "task_id": "nonretryable",
                "chat_id": "@example",
                "_last_failure_classification": "auth",
                "_last_failure_retryable": False,
            },
        )

        rendered = main_ops.render_main_triage(paths=self.paths)

        self.assertIn("# Main Ops Triage", rendered)
        self.assertIn(task.task_id, rendered)
        self.assertIn("Persistent retryable failures detected", rendered)
        self.assertNotIn("repair --execute-retries --execution-context host", rendered)
        self.assertIn("## Retryable Failed Instructions", rendered)
        self.assertIn("retry_count=2", rendered)
        self.assertIn("last_error: Network request failed with timeout", rendered)
        self.assertIn("## Non-Retryable Failed Instructions", rendered)
        self.assertIn("chat_id=@example", rendered)

    def test_render_main_triage_includes_blocked_age_and_sweep_hint(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:main",
            channel="telegram",
            chat_id="chat:main",
            task_label="aged blocked main task",
        )
        blocked = self.store.block_task(task.task_id, "waiting")
        task_path = self.paths.inflight_dir / f"{blocked.task_id}.json"
        payload = json.loads(task_path.read_text(encoding="utf-8"))
        payload["updated_at"] = "2026-04-01T00:00:00+00:00"
        task_state_module.atomic_write_json(task_path, payload)

        rendered = main_ops.render_main_triage(paths=self.paths)

        self.assertIn("Current blocked age:", rendered)
        self.assertIn("main_ops.py sweep --fail-stale-blocked-after-minutes 60", rendered)

    def test_repair_system_cleans_stale_delivery_artifacts(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:main",
            channel="telegram",
            chat_id="chat:main",
            task_label="repair target",
        )
        processed_dir = self.paths.data_dir / "processed-instructions"
        processed_dir.mkdir(parents=True, exist_ok=True)
        task_state_module.atomic_write_json(processed_dir / f"{task.task_id}.json", {"task_id": task.task_id})
        stale_path = self.paths.data_dir / "sent" / f"{task.task_id}.json"
        stale_path.parent.mkdir(parents=True, exist_ok=True)
        stale_path.write_text("{}", encoding="utf-8")

        result = main_ops.repair_system(paths=self.paths)

        self.assertEqual(result["health_before"]["status"], "warn")
        self.assertFalse(stale_path.exists())
        self.assertEqual(result["health_after"]["status"], "ok")
        self.assertEqual(len(result["stale_cleanup"]), 1)

    def test_repair_system_can_retry_failed_instructions(self) -> None:
        with (
            patch.object(main_ops, "annotate_failed_instruction_metadata", return_value=[{"name": "legacy.json"}]) as annotate_mock,
            patch.object(main_ops, "retry_failed_instructions", return_value=[{"name": "failed.json"}]) as retry_mock,
        ):
            result = main_ops.repair_system(
                paths=self.paths,
                execute_retries=True,
                openclaw_bin="/tmp/openclaw",
                execution_context="host",
            )

        annotate_mock.assert_called_once()
        retry_mock.assert_called_once()
        self.assertEqual(result["annotated_failures"], [{"name": "legacy.json"}])
        self.assertEqual(result["retry_results"], [{"name": "failed.json"}])

    def test_sweep_main_tasks_fails_stale_blocked_task(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:main",
            channel="telegram",
            chat_id="chat:main",
            task_label="stale blocked task",
        )
        blocked = self.store.block_task(task.task_id, "waiting")
        task_path = self.paths.inflight_dir / f"{blocked.task_id}.json"
        payload = json.loads(task_path.read_text(encoding="utf-8"))
        payload["updated_at"] = "2026-04-01T00:00:00+00:00"
        task_state_module.atomic_write_json(task_path, payload)

        result = main_ops.sweep_main_tasks(
            paths=self.paths,
            fail_stale_blocked_after_minutes=60,
            reason="stale blocked cleanup",
        )

        self.assertEqual(result["blocked_main_task_count"], 1)
        self.assertEqual(result["actions"][0]["action"], "failed")
        archived_path = self.paths.archive_dir / f"{task.task_id}.json"
        self.assertTrue(archived_path.exists())

    def test_cancel_main_queue_task_by_queue_position_archives_selected_task(self) -> None:
        first = self.store.register_task(
            agent_id="main",
            session_key="session:main:1",
            channel="telegram",
            chat_id="chat:main:1",
            task_label="queued main task 1",
        )
        second = self.store.register_task(
            agent_id="main",
            session_key="session:main:2",
            channel="telegram",
            chat_id="chat:main:2",
            task_label="queued main task 2",
        )

        result = main_ops.cancel_main_queue_task(paths=self.paths, queue_position=2)

        self.assertEqual(result["action"], "cancelled-queued-task")
        self.assertEqual(result["task_id"], second.task_id)
        self.assertEqual(result["queue_position"], 2)
        self.assertTrue((self.paths.archive_dir / f"{second.task_id}.json").exists())
        self.assertTrue((self.paths.inflight_dir / f"{first.task_id}.json").exists())

    def test_cancel_main_queue_task_by_task_id_rejects_running_task(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:main:running",
            channel="telegram",
            chat_id="chat:main:running",
            task_label="running main task",
        )
        self.store.start_task(task.task_id)

        result = main_ops.cancel_main_queue_task(paths=self.paths, task_id=task.task_id)

        self.assertEqual(result["action"], "noop")
        self.assertEqual(result["reason"], "task-not-queued")
        self.assertEqual(result["status"], task_state_module.STATUS_RUNNING)
        self.assertTrue((self.paths.inflight_dir / f"{task.task_id}.json").exists())

    def test_cancel_main_queue_task_returns_out_of_range_for_unknown_position(self) -> None:
        self.store.register_task(
            agent_id="main",
            session_key="session:main:1",
            channel="telegram",
            chat_id="chat:main:1",
            task_label="queued main task 1",
        )

        result = main_ops.cancel_main_queue_task(paths=self.paths, queue_position=3)

        self.assertEqual(result["action"], "noop")
        self.assertEqual(result["reason"], "queue-position-out-of-range")
        self.assertEqual(result["queued_count"], 1)

    def test_resolve_main_failures_can_select_non_retryable_without_apply(self) -> None:
        failed_dir = self.paths.data_dir / "failed-instructions"
        failed_dir.mkdir(parents=True, exist_ok=True)
        task_state_module.atomic_write_json(
            failed_dir / "nonretryable.json",
            {
                "task_id": "nonretryable",
                "_last_failure_classification": "transport-nonretryable",
                "_last_failure_retryable": False,
            },
        )

        result = main_ops.resolve_main_failures(paths=self.paths, include_non_retryable=True)

        self.assertEqual(result["resolved_count"], 1)
        self.assertFalse(result["findings"][0]["applied"])

    def test_resolve_main_failures_can_apply_persistent_retryable_resolution(self) -> None:
        failed_dir = self.paths.data_dir / "failed-instructions"
        failed_dir.mkdir(parents=True, exist_ok=True)
        task_state_module.atomic_write_json(
            failed_dir / "retryable.json",
            {
                "task_id": "retryable",
                "_last_failure_classification": "transport-retryable",
                "_last_failure_retryable": True,
                "_retry_count": 2,
            },
        )

        result = main_ops.resolve_main_failures(
            paths=self.paths,
            include_persistent_retryable=True,
            apply_changes=True,
            reason="cleanup",
        )

        self.assertEqual(result["resolved_count"], 1)
        resolved_path = self.paths.data_dir / "resolved-failed-instructions" / "retryable.json"
        self.assertTrue(resolved_path.exists())

    def test_render_delivery_diagnose_includes_probe_command(self) -> None:
        failed_dir = self.paths.data_dir / "failed-instructions"
        failed_dir.mkdir(parents=True, exist_ok=True)
        task_state_module.atomic_write_json(
            failed_dir / "retryable.json",
            {
                "task_id": "retryable",
                "channel": "telegram",
                "chat_id": "8705812936",
                "_last_failure_classification": "transport-retryable",
                "_last_failure_retryable": True,
                "_retry_count": 1,
            },
        )
        dispatch_dir = self.paths.data_dir / "dispatch-results"
        dispatch_dir.mkdir(parents=True, exist_ok=True)
        task_state_module.atomic_write_json(
            dispatch_dir / "retryable.json",
            {
                "task_id": "retryable",
                "stderr": "Network request failed with timeout",
            },
        )

        rendered = main_ops.render_delivery_diagnose(paths=self.paths)

        self.assertIn("# Delivery Diagnose", rendered)
        self.assertIn("message send --channel telegram --target 8705812936", rendered)
        self.assertIn("last_error: Network request failed with timeout", rendered)

    def test_acknowledge_and_clear_delivery_outage(self) -> None:
        entry = main_ops.acknowledge_delivery_outage(
            channel="telegram",
            chat_id="8705812936",
            reason="network outage",
            paths=self.paths,
        )
        self.assertEqual(entry["channel"], "telegram")

        cleared = main_ops.clear_delivery_outage(
            channel="telegram",
            chat_id="8705812936",
            paths=self.paths,
        )
        self.assertEqual(cleared["removed"], 1)

    def test_stop_main_queue_cancels_running_task_and_promotes_next(self) -> None:
        first = self.store.register_task(
            agent_id="main",
            session_key="session:main:1",
            channel="telegram",
            chat_id="chat:main:1",
            task_label="running task",
        )
        self.store.start_task(first.task_id)
        second = self.store.register_task(
            agent_id="main",
            session_key="session:main:2",
            channel="telegram",
            chat_id="chat:main:2",
            task_label="queued task",
        )

        with patch.object(
            main_ops,
            "_cancel_host_session",
            return_value={
                "ok": True,
                "stdout": "cancelled",
                "stderr": "",
                "returncode": 0,
                "command": ["openclaw", "tasks", "cancel", "session:main:1"],
            },
        ):
            result = main_ops.stop_main_queue(paths=self.paths, reason="manual stop")

        self.assertEqual(result["action"], "stopped-current")
        self.assertEqual(result["remaining_running_count"], 1)
        self.assertEqual(result["remaining_queued_count"], 0)
        promoted = self.store.load_task(second.task_id)
        self.assertEqual(promoted.status, task_state_module.STATUS_RUNNING)

    def test_stop_main_queue_cancels_queue_head_when_nothing_running(self) -> None:
        queued = self.store.register_task(
            agent_id="main",
            session_key="session:main:q1",
            channel="telegram",
            chat_id="chat:main:q1",
            task_label="queued head",
        )
        self.store.register_task(
            agent_id="main",
            session_key="session:main:q2",
            channel="telegram",
            chat_id="chat:main:q2",
            task_label="queued tail",
        )

        result = main_ops.stop_main_queue(paths=self.paths, reason="manual stop")

        self.assertEqual(result["action"], "stopped-queued-head")
        self.assertEqual(result["remaining_queued_count"], 0)
        self.assertEqual(result["remaining_running_count"], 1)
        self.assertTrue((self.paths.archive_dir / f"{queued.task_id}.json").exists())

    def test_stop_all_main_queue_cancels_running_and_queued_tasks(self) -> None:
        running = self.store.register_task(
            agent_id="main",
            session_key="session:main:run",
            channel="telegram",
            chat_id="chat:main:run",
            task_label="running task",
        )
        self.store.start_task(running.task_id)
        queued = self.store.register_task(
            agent_id="main",
            session_key="session:main:queued",
            channel="telegram",
            chat_id="chat:main:queued",
            task_label="queued task",
        )

        with patch.object(
            main_ops,
            "_cancel_host_session",
            return_value={
                "ok": True,
                "stdout": "cancelled",
                "stderr": "",
                "returncode": 0,
                "command": ["openclaw", "tasks", "cancel", "session:main:run"],
            },
        ):
            result = main_ops.stop_all_main_queue(paths=self.paths, reason="stop all")

        self.assertEqual(result["action"], "stopped-all")
        self.assertEqual(result["cancelled_count"], 2)
        self.assertEqual(result["remaining_active_count"], 0)
        self.assertTrue((self.paths.archive_dir / f"{running.task_id}.json").exists())
        self.assertTrue((self.paths.archive_dir / f"{queued.task_id}.json").exists())

    def test_purge_task_records_removes_matching_inflight_and_archive(self) -> None:
        keep = self.store.register_task(
            agent_id="main",
            session_key="session:keep",
            channel="telegram",
            chat_id="chat:keep",
            task_label="keep task",
        )
        inflight = self.store.register_task(
            agent_id="main",
            session_key="session:purge",
            channel="telegram",
            chat_id="chat:purge",
            task_label="purge inflight",
        )
        archived_source = self.store.register_task(
            agent_id="main",
            session_key="session:purge",
            channel="telegram",
            chat_id="chat:purge",
            task_label="purge archived",
        )
        self.store.complete_task(archived_source.task_id, archive=True)

        result = main_ops.purge_task_records(
            paths=self.paths,
            session_key="session:purge",
        )

        self.assertEqual(result["action"], "purged-task-records")
        self.assertEqual(result["deleted_count"], 2)
        self.assertFalse((self.paths.inflight_dir / f"{inflight.task_id}.json").exists())
        self.assertFalse((self.paths.archive_dir / f"{archived_source.task_id}.json").exists())
        self.assertTrue((self.paths.inflight_dir / f"{keep.task_id}.json").exists())

    def test_purge_task_records_can_limit_to_inflight(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:inflight-only",
            channel="telegram",
            chat_id="chat:inflight-only",
            task_label="purge later",
        )
        self.store.complete_task(task.task_id, archive=True)

        result = main_ops.purge_task_records(
            paths=self.paths,
            session_key="session:inflight-only",
            include_archive=False,
        )

        self.assertEqual(result["deleted_count"], 0)
        self.assertTrue((self.paths.archive_dir / f"{task.task_id}.json").exists())


if __name__ == "__main__":
    unittest.main()
