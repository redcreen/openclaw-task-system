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

    def test_render_main_continuity_reports_no_risk_when_idle(self) -> None:
        rendered = main_ops.render_main_continuity(config_path=self._config_path(), paths=self.paths)

        self.assertIn("# Main Continuity", rendered)
        self.assertIn("- session_filter: all", rendered)
        self.assertIn("- No continuity risk is currently detected for main.", rendered)

    def test_get_main_continuity_summary_reports_empty_state(self) -> None:
        summary = main_ops.get_main_continuity_summary(config_path=self._config_path(), paths=self.paths)

        self.assertEqual(summary["session_filter"], "all")
        self.assertEqual(summary["active_monitored_task_count"], 0)
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
        self.assertIn("blocked-no-visible-progress", rendered)
        self.assertIn("main_ops.py resume", rendered)

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
        self.assertEqual(len(summary["manual_review"]), 1)
        self.assertEqual(summary["manual_review"][0]["task_label"], "focus json task")
        self.assertEqual(len(summary["by_session"]), 1)
        self.assertEqual(summary["by_session"][0]["session_key"], "session:main:focus-json")

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
        self.assertEqual(result["resumed_count"], 1)
        self.assertEqual(result["resumed"][0]["task_id"], first.task_id)
        resumed_first = self.store.load_task(first.task_id)
        resumed_second = self.store.load_task(second.task_id)
        resumed_unrelated = self.store.load_task(unrelated.task_id)
        self.assertEqual(resumed_first.status, task_state_module.STATUS_RUNNING)
        self.assertEqual(resumed_first.meta["last_progress_note"], "继续推进")
        self.assertEqual(resumed_second.status, "blocked")
        self.assertEqual(resumed_unrelated.status, "blocked")

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
        self.assertIn("- running_task_count: 1", rendered)
        self.assertIn("- session_lane_count: 2", rendered)
        self.assertIn("main queued", rendered)
        self.assertIn("code running", rendered)

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
        self.assertIn("- session_count: 2", rendered)
        self.assertIn("session:main:one | task_count=1", rendered)
        self.assertIn("session:main:two | task_count=1", rendered)
        self.assertIn("## Queue: code", rendered)
        self.assertIn("- queue_kind: single-session", rendered)

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
