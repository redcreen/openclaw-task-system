from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from runtime_loader import load_runtime_module, task_state_module


task_status = load_runtime_module("task_status")


class TaskStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="task-system-status-tests."))
        self.paths = task_state_module.TaskPaths.from_root(self.temp_dir)
        self.store = task_state_module.TaskStore(paths=self.paths)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_build_status_summary_returns_expected_fields(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:test",
            channel="feishu",
            chat_id="chat:test",
            task_label="status task",
        )
        task = self.store.start_task(task.task_id)
        summary = task_status.build_status_summary(task.task_id, paths=self.paths)
        self.assertEqual(summary["task_id"], task.task_id)
        self.assertEqual(summary["status"], task_state_module.STATUS_RUNNING)
        self.assertEqual(summary["task_label"], "status task")
        self.assertIn("delivery", summary)
        self.assertIn("queue", summary)
        self.assertEqual(summary["delivery"]["state"], "not-requested")
        self.assertFalse(summary["delivery"]["stale_intermediate_exists"])
        self.assertEqual(summary["delivery"]["stale_intermediate_count"], 0)
        self.assertFalse(summary["delivery"]["dispatch_result_exists"])

    def test_render_status_markdown_includes_key_lines(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:test",
            channel="feishu",
            chat_id="chat:test",
            task_label="status markdown task",
        )
        markdown = task_status.render_status_markdown(task.task_id, paths=self.paths)
        self.assertIn(f"# Task Status: {task.task_id}", markdown)
        self.assertIn("- status: queued", markdown)
        self.assertIn("- queue.position: 1", markdown)
        self.assertIn("- delivery.state: not-requested", markdown)
        self.assertIn("- delivery.stale_intermediate_exists: False", markdown)
        self.assertIn("- delivery.outbox_exists: False", markdown)

    def test_build_status_summary_projects_same_session_routing(self) -> None:
        task = self.store.observe_task(
            agent_id="main",
            session_key="session:routing",
            channel="feishu",
            chat_id="chat:routing",
            task_label="routing task",
            meta={
                "same_session_routing": {
                    "schema": "openclaw.task-system.same-session-routing.v1",
                    "version": 1,
                    "routing_status": "recorded-only",
                    "same_session_followup": True,
                    "classification": None,
                    "execution_decision": None,
                    "reason_code": "phase1-same-session-followup-recorded",
                }
            },
        )

        summary = task_status.build_status_summary(task.task_id, paths=self.paths)

        self.assertIsInstance(summary["same_session_routing"], dict)
        self.assertEqual(summary["same_session_routing"]["routing_status"], "recorded-only")
        self.assertTrue(summary["same_session_routing"]["same_session_followup"])

        markdown = task_status.render_status_markdown(task.task_id, paths=self.paths)
        self.assertIn("- same_session_routing.routing_status: recorded-only", markdown)
        self.assertIn("- same_session_routing.reason_code: phase1-same-session-followup-recorded", markdown)

    def test_list_inflight_statuses_returns_registered_task(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:test",
            channel="feishu",
            chat_id="chat:test",
            task_label="status list task",
        )
        statuses = task_status.list_inflight_statuses(paths=self.paths)
        self.assertEqual(len(statuses), 1)
        self.assertEqual(statuses[0]["task_id"], task.task_id)

    def test_render_inflight_markdown_includes_task_line(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:test",
            channel="feishu",
            chat_id="chat:test",
            task_label="status list markdown task",
        )
        markdown = task_status.render_inflight_markdown(paths=self.paths)
        self.assertIn("# Active Tasks", markdown)
        self.assertIn(task.task_id, markdown)
        self.assertIn("delivery=not-requested", markdown)

    def test_build_system_overview_returns_counts(self) -> None:
        active = self.store.register_task(
            agent_id="main",
            session_key="session:active",
            channel="telegram",
            chat_id="chat:active",
            task_label="overview active task",
        )
        self.store.start_task(active.task_id)
        completed = self.store.register_task(
            agent_id="main",
            session_key="session:done",
            channel="telegram",
            chat_id="chat:done",
            task_label="overview completed task",
        )
        self.store.complete_task(completed.task_id)
        processed_dir = self.paths.data_dir / "processed-instructions"
        processed_dir.mkdir(parents=True, exist_ok=True)
        (processed_dir / f"{completed.task_id}.json").write_text(
            json.dumps({"task_id": completed.task_id}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        sent_dir = self.paths.data_dir / "sent"
        sent_dir.mkdir(parents=True, exist_ok=True)
        (sent_dir / f"{completed.task_id}.json").write_text(
            json.dumps({"task_id": completed.task_id}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        overview = task_status.build_system_overview(paths=self.paths)
        self.assertEqual(overview["active_task_count"], 1)
        self.assertEqual(overview["archived_task_count"], 1)
        self.assertEqual(overview["active_status_counts"], {"running": 1})
        self.assertEqual(overview["active_delivery_counts"], {"not-requested": 1})
        self.assertEqual(overview["active_stale_delivery_task_count"], 0)
        self.assertEqual(overview["active_stale_delivery_artifact_count"], 0)
        self.assertEqual(overview["stale_delivery_task_count"], 1)
        self.assertEqual(overview["stale_delivery_artifact_count"], 1)
        self.assertEqual(overview["archived_status_counts"], {"done": 1})
        self.assertEqual(overview["resolved_failed_instruction_count"], 0)

    def test_build_status_summary_reports_queue_position(self) -> None:
        first = self.store.register_task(
            agent_id="main",
            session_key="session:first",
            channel="telegram",
            chat_id="chat:first",
            task_label="first task",
        )
        self.store.start_task(first.task_id)
        second = self.store.register_task(
            agent_id="main",
            session_key="session:second",
            channel="telegram",
            chat_id="chat:second",
            task_label="second task",
        )
        first_summary = task_status.build_status_summary(first.task_id, paths=self.paths)
        second_summary = task_status.build_status_summary(second.task_id, paths=self.paths)
        self.assertEqual(first_summary["queue"]["position"], 1)
        self.assertTrue(first_summary["queue"]["is_running"])
        self.assertEqual(second_summary["queue"]["position"], 2)
        self.assertEqual(second_summary["queue"]["ahead_count"], 1)
        self.assertEqual(second_summary["queue"]["active_count"], 2)
        self.assertEqual(second_summary["queue"]["running_count"], 1)
        self.assertEqual(second_summary["queue"]["queued_count"], 1)
        self.assertEqual(first_summary["user_facing_status_code"], "running")
        self.assertEqual(first_summary["user_facing_status"], "处理中")
        self.assertEqual(second_summary["user_facing_status_code"], "queued")
        self.assertEqual(second_summary["user_facing_status"], "排队中")

    def test_build_queue_snapshot_includes_received_tasks(self) -> None:
        running = self.store.register_task(
            agent_id="main",
            session_key="session:running",
            channel="feishu",
            chat_id="chat:running",
            task_label="running task",
        )
        self.store.start_task(running.task_id)
        observed = self.store.observe_task(
            agent_id="main",
            session_key="session:received",
            channel="feishu",
            chat_id="chat:received",
            task_label="received task",
        )

        snapshot = task_status.build_queue_snapshot(paths=self.paths)
        self.assertEqual(snapshot["active_count"], 2)
        self.assertEqual(snapshot["running_count"], 1)
        self.assertEqual(snapshot["queued_count"], 1)
        self.assertEqual(snapshot["items"][0]["task_id"], running.task_id)
        self.assertEqual(snapshot["items"][1]["task_id"], observed.task_id)
        self.assertEqual(snapshot["items"][1]["status"], task_state_module.STATUS_RECEIVED)

    def test_build_status_summary_maps_waiting_queue_head_to_pending_start(self) -> None:
        queued = self.store.register_task(
            agent_id="main",
            session_key="session:pending-start",
            channel="telegram",
            chat_id="chat:pending-start",
            task_label="pending start task",
        )

        summary = task_status.build_status_summary(queued.task_id, paths=self.paths)

        self.assertEqual(summary["queue"]["position"], 1)
        self.assertEqual(summary["user_facing_status_code"], "pending-start")
        self.assertEqual(summary["user_facing_status"], "待开始")

    def test_render_overview_markdown_includes_counts(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:test",
            channel="telegram",
            chat_id="chat:test",
            task_label="overview markdown task",
        )
        self.store.start_task(task.task_id)
        markdown = task_status.render_overview_markdown(paths=self.paths)
        self.assertIn("# Task System Overview", markdown)
        self.assertIn("- active_task_count: 1", markdown)
        self.assertIn("- active_stale_delivery_task_count: 0", markdown)
        self.assertIn("- stale_delivery_task_count: 0", markdown)
        self.assertIn("- resolved_failed_instruction_count: 0", markdown)
        self.assertIn("- active_status_counts: {\"running\": 1}", markdown)
        self.assertIn("pos=1", markdown)
        self.assertIn(task.task_id, markdown)

    def test_build_status_summary_can_resolve_paths_from_config_file(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:test",
            channel="feishu",
            chat_id="chat:test",
            task_label="status config task",
        )
        config_dir = self.temp_dir / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "task_system.json"
        config_path.write_text(
            json.dumps({"taskSystem": {"storageDir": str(self.paths.data_dir)}}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        summary = task_status.build_status_summary(task.task_id, config_path=config_path)
        self.assertEqual(summary["task_id"], task.task_id)

    def test_build_status_summary_includes_delivery_artifacts(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:test",
            channel="telegram",
            chat_id="chat:test",
            task_label="status delivery task",
        )
        dispatch_dir = self.paths.data_dir / "dispatch-results"
        dispatch_dir.mkdir(parents=True, exist_ok=True)
        (dispatch_dir / f"{task.task_id}.json").write_text(
            json.dumps(
                {
                    "schema": "openclaw.task-system.dispatch-result.v1",
                    "task_id": task.task_id,
                    "action": "send",
                    "reason": "supported",
                    "execution_context": "dry-run",
                    "requested_execution_context": "host",
                    "exit_code": None,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        summary = task_status.build_status_summary(task.task_id, paths=self.paths)
        self.assertTrue(summary["delivery"]["dispatch_result_exists"])
        self.assertEqual(summary["delivery"]["state"], "not-requested")
        self.assertFalse(summary["delivery"]["stale_intermediate_exists"])
        self.assertEqual(summary["delivery"]["dispatch_action"], "send")
        self.assertEqual(summary["delivery"]["dispatch_execution_context"], "dry-run")
        self.assertEqual(summary["delivery"]["dispatch_requested_execution_context"], "host")

    def test_build_status_summary_reports_processed_delivery_state(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:test",
            channel="telegram",
            chat_id="chat:test",
            task_label="status processed task",
        )
        processed_dir = self.paths.data_dir / "processed-instructions"
        processed_dir.mkdir(parents=True, exist_ok=True)
        (processed_dir / f"{task.task_id}.json").write_text(
            json.dumps({"task_id": task.task_id}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        dispatch_dir = self.paths.data_dir / "dispatch-results"
        dispatch_dir.mkdir(parents=True, exist_ok=True)
        (dispatch_dir / f"{task.task_id}.json").write_text(
            json.dumps(
                {
                    "schema": "openclaw.task-system.dispatch-result.v1",
                    "task_id": task.task_id,
                    "action": "send",
                    "reason": "supported",
                    "execution_context": "host",
                    "requested_execution_context": "host",
                    "exit_code": 0,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        summary = task_status.build_status_summary(task.task_id, paths=self.paths)
        self.assertEqual(summary["delivery"]["state"], "processed")
        self.assertFalse(summary["delivery"]["stale_intermediate_exists"])

    def test_build_status_summary_reports_skipped_delivery_state(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:test",
            channel="agent",
            chat_id="chat:test",
            task_label="status skipped task",
        )
        processed_dir = self.paths.data_dir / "processed-instructions"
        processed_dir.mkdir(parents=True, exist_ok=True)
        (processed_dir / f"{task.task_id}.json").write_text(
            json.dumps({"task_id": task.task_id}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        dispatch_dir = self.paths.data_dir / "dispatch-results"
        dispatch_dir.mkdir(parents=True, exist_ok=True)
        (dispatch_dir / f"{task.task_id}.json").write_text(
            json.dumps(
                {
                    "schema": "openclaw.task-system.dispatch-result.v1",
                    "task_id": task.task_id,
                    "action": "skip",
                    "reason": "internal-agent-channel",
                    "execution_context": "local",
                    "requested_execution_context": "host",
                    "exit_code": None,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        summary = task_status.build_status_summary(task.task_id, paths=self.paths)
        self.assertEqual(summary["delivery"]["state"], "skipped")
        self.assertFalse(summary["delivery"]["stale_intermediate_exists"])

    def test_build_status_summary_reports_stale_intermediate_artifacts(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:test",
            channel="telegram",
            chat_id="chat:test",
            task_label="status stale task",
        )
        processed_dir = self.paths.data_dir / "processed-instructions"
        processed_dir.mkdir(parents=True, exist_ok=True)
        (processed_dir / f"{task.task_id}.json").write_text(
            json.dumps({"task_id": task.task_id}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        sent_dir = self.paths.data_dir / "sent"
        sent_dir.mkdir(parents=True, exist_ok=True)
        (sent_dir / f"{task.task_id}.json").write_text(
            json.dumps({"task_id": task.task_id}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        summary = task_status.build_status_summary(task.task_id, paths=self.paths)
        self.assertTrue(summary["delivery"]["stale_intermediate_exists"])
        self.assertEqual(summary["delivery"]["stale_intermediate_count"], 1)

    def test_build_status_summary_projects_planning_anomaly_and_overdue_followup(self) -> None:
        source = self.store.register_task(
            agent_id="main",
            session_key="session:planning-status",
            channel="feishu",
            chat_id="chat:planning-status",
            task_label="planning source task",
        )
        source.meta["tool_followup_plan"] = {
            "plan_id": "plan_123",
            "status": "anomaly",
            "followup_due_at": "2020-01-01T00:00:00+00:00",
            "followup_summary": "5分钟后同步结果",
            "main_user_content_mode": "none",
        }
        source.meta["planning_promise_guard"] = {
            "status": "anomaly",
            "expected_by_finalize": True,
            "main_user_content_mode": "none",
        }
        source.meta["planning_anomaly"] = "promise-without-task"
        self.store.save_task(source)

        followup = self.store.observe_task(
            agent_id="main",
            session_key="session:planning-status",
            channel="feishu",
            chat_id="chat:planning-status",
            task_label="planned follow-up",
            meta={"source": "tool-followup-plan", "plan_id": "plan_123"},
        )
        self.store.schedule_continuation(
            followup.task_id,
            continuation_kind="delayed-reply",
            due_at="2020-01-01T00:00:00+00:00",
            payload={"reply_text": "稍后同步", "wait_seconds": 60},
            reason="scheduled tool-assisted continuation wait",
        )

        source_summary = task_status.build_status_summary(source.task_id, paths=self.paths)
        followup_summary = task_status.build_status_summary(followup.task_id, paths=self.paths)
        overview = task_status.build_system_overview(paths=self.paths)
        markdown = task_status.render_overview_markdown(paths=self.paths)

        self.assertTrue(source_summary["planning"]["promise_without_task"])
        self.assertEqual(source_summary["planning"]["anomaly"], "promise-without-task")
        self.assertEqual(
            source_summary["planning"]["recovery_action"]["kind"],
            "inspect-promise-without-task",
        )
        self.assertTrue(followup_summary["planning"]["overdue_followup"])
        self.assertEqual(overview["planning"]["promise_without_task_count"], 1)
        self.assertEqual(overview["planning"]["overdue_followup_count"], 1)
        self.assertEqual(overview["planning"]["anomaly_counts"], {"promise-without-task": 1})
        self.assertEqual(
            overview["planning"]["recovery_action_counts"],
            {"inspect-overdue-followup": 1, "inspect-promise-without-task": 1},
        )
        self.assertEqual(
            overview["planning"]["primary_recovery_action"]["kind"],
            "inspect-promise-without-task",
        )
        self.assertEqual(overview["planning"]["health"]["status"], "error")
        self.assertEqual(overview["planning"]["health"]["primary_reason"], "promise-without-task-present")
        self.assertIn("- planning_promise_without_task_count: 1", markdown)
        self.assertIn("- planning_overdue_followup_count: 1", markdown)
        self.assertIn("- planning_health_status: error", markdown)
        self.assertIn("- planning_primary_recovery_action_kind: inspect-promise-without-task", markdown)

    def test_build_system_overview_projects_planning_health_from_archived_and_active_tasks(self) -> None:
        healthy = self.store.register_task(
            agent_id="main",
            session_key="session:planning-healthy",
            channel="feishu",
            chat_id="chat:planning-healthy",
            task_label="healthy planning task",
        )
        healthy.meta["tool_followup_plan"] = {
            "plan_id": "plan_ok",
            "status": "fulfilled",
            "followup_due_at": "2099-01-01T00:00:00+00:00",
        }
        healthy.meta["planning_promise_guard"] = {
            "status": "fulfilled",
            "expected_by_finalize": True,
        }
        self.store.save_task(healthy)
        self.store.complete_task(healthy.task_id)

        pending = self.store.register_task(
            agent_id="main",
            session_key="session:planning-pending",
            channel="feishu",
            chat_id="chat:planning-pending",
            task_label="pending planning task",
        )
        pending.meta["tool_followup_plan"] = {
            "plan_id": "plan_pending",
            "status": "planned",
            "followup_due_at": "2099-01-01T00:00:00+00:00",
        }
        pending.meta["planning_promise_guard"] = {
            "status": "armed",
            "expected_by_finalize": True,
        }
        self.store.save_task(pending)

        overview = task_status.build_system_overview(paths=self.paths)

        self.assertEqual(overview["planning"]["health"]["status"], "warn")
        self.assertEqual(overview["planning"]["health"]["primary_reason"], "tool-path-not-fully-closed")
        self.assertEqual(overview["planning"]["health"]["sample_task_count"], 2)
        self.assertEqual(overview["planning"]["health"]["success_count"], 1)
        self.assertEqual(overview["planning"]["health"]["tool_call_completion_count"], 1)
        self.assertEqual(overview["planning"]["health"]["success_rate"], 0.5)
        self.assertEqual(overview["planning"]["health"]["tool_call_completion_rate"], 0.5)
        self.assertEqual(overview["planning"]["primary_recovery_action"]["kind"], "inspect-pending-plan")

    def test_build_status_summary_projects_planner_timeout_recovery_action(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:planning-timeout",
            channel="feishu",
            chat_id="chat:planning-timeout",
            task_label="planner timeout task",
        )
        task.meta["tool_followup_plan"] = {
            "plan_id": "plan_timeout",
            "status": "timeout",
            "followup_due_at": "2099-01-01T00:00:00+00:00",
        }
        task.meta["planning_promise_guard"] = {
            "status": "timeout",
            "expected_by_finalize": True,
        }
        task.meta["planning_anomaly"] = "planner-timeout"
        self.store.save_task(task)

        summary = task_status.build_status_summary(task.task_id, paths=self.paths)
        overview = task_status.build_system_overview(paths=self.paths)

        self.assertEqual(summary["planning"]["recovery_action"]["kind"], "inspect-planner-timeout")
        self.assertEqual(overview["planning"]["primary_recovery_action"]["kind"], "inspect-planner-timeout")
