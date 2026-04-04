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
