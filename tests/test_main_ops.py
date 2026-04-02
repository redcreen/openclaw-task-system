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


if __name__ == "__main__":
    unittest.main()
