from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime_loader import load_runtime_module, task_state_module


health_report = load_runtime_module("health_report")


class HealthReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="task-system-health-tests."))
        self.paths = task_state_module.TaskPaths.from_root(self.temp_dir)
        self.store = task_state_module.TaskStore(paths=self.paths)
        self.config_path = self.temp_dir / "task_system.json"
        self.config_path.write_text(
            json.dumps({"taskSystem": {"storageDir": str(self.paths.data_dir)}}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_artifact(self, directory: str, task_id: str) -> None:
        target = self.paths.data_dir / directory / f"{task_id}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"task_id": task_id}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def test_build_health_report_warns_on_blocked_and_stale_delivery(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:test",
            channel="telegram",
            chat_id="chat:test",
            task_label="health task",
        )
        self.store.block_task(task.task_id, "waiting for follow-up")
        self._write_artifact("processed-instructions", task.task_id)
        self._write_artifact("sent", task.task_id)

        report = health_report.build_health_report(config_path=self.config_path)

        self.assertEqual(report["status"], "warn")
        self.assertIn("blocked-active-tasks:1", report["issues"])
        self.assertIn("active-stale-delivery:1", report["issues"])
        self.assertEqual(report["overview"]["stale_delivery_task_count"], 1)
        self.assertTrue(any(entry["severity"] == "warn" for entry in report["issue_entries"]))

    def test_render_markdown_includes_status_and_checks(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:test",
            channel="telegram",
            chat_id="chat:test",
            task_label="health markdown task",
        )
        self.store.block_task(task.task_id, "waiting for follow-up")
        report = health_report.build_health_report(config_path=self.config_path)
        markdown = health_report.render_markdown(report)
        self.assertIn("# Task System Health", markdown)
        self.assertIn("- status: warn", markdown)
        self.assertIn("## Plugin Checks", markdown)
        self.assertIn("## Remediation", markdown)

    def test_build_health_report_uses_error_status_for_failed_instructions(self) -> None:
        task = self.store.register_task(
            agent_id="main",
            session_key="session:test",
            channel="telegram",
            chat_id="chat:test",
            task_label="health failed task",
        )
        failed_dir = self.paths.data_dir / "failed-instructions"
        failed_dir.mkdir(parents=True, exist_ok=True)
        (failed_dir / f"{task.task_id}.json").write_text(
            json.dumps({"task_id": task.task_id}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        report = health_report.build_health_report(config_path=self.config_path)

        self.assertEqual(report["status"], "error")
        self.assertIn("failed-instructions:1", report["issues"])
        failed_issue = next(entry for entry in report["issue_entries"] if entry["code"] == "failed-instructions:1")
        self.assertEqual(failed_issue["severity"], "error")

    def test_build_health_report_summarizes_failed_instruction_retryability(self) -> None:
        failed_dir = self.paths.data_dir / "failed-instructions"
        failed_dir.mkdir(parents=True, exist_ok=True)
        (failed_dir / "retryable.json").write_text(
            json.dumps(
                {
                    "task_id": "retryable",
                    "_last_failure_classification": "transport-retryable",
                    "_last_failure_retryable": True,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        dispatch_dir = self.paths.data_dir / "dispatch-results"
        dispatch_dir.mkdir(parents=True, exist_ok=True)
        (dispatch_dir / "retryable.json").write_text(
            json.dumps(
                {
                    "task_id": "retryable",
                    "stderr": "Network request failed with timeout\nHttpError: timeout",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (failed_dir / "nonretryable.json").write_text(
            json.dumps(
                {
                    "task_id": "nonretryable",
                    "_last_failure_classification": "auth",
                    "_last_failure_retryable": False,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        report = health_report.build_health_report(config_path=self.config_path)
        markdown = health_report.render_markdown(report)

        self.assertEqual(report["failed_instruction_summary"]["retryable"], 1)
        self.assertEqual(report["failed_instruction_summary"]["persistent_retryable"], 0)
        self.assertEqual(report["failed_instruction_summary"]["non_retryable"], 1)
        retryable_item = next(item for item in report["failed_instruction_summary"]["items"] if item["task_id"] == "retryable")
        self.assertEqual(retryable_item["retry_count"], 0)
        self.assertEqual(retryable_item["last_error_summary"], "Network request failed with timeout")
        self.assertIn("- resolved_failed_instruction_count: 0", markdown)
        self.assertIn("- failed_instruction_retryable_count: 1", markdown)
        self.assertIn("- failed_instruction_persistent_retryable_count: 0", markdown)
        self.assertIn("- failed_instruction_non_retryable_count: 1", markdown)
        self.assertIn("## Failed Instructions", markdown)

    def test_build_health_report_downgrades_acknowledged_delivery_outage(self) -> None:
        failed_dir = self.paths.data_dir / "failed-instructions"
        failed_dir.mkdir(parents=True, exist_ok=True)
        (failed_dir / "retryable.json").write_text(
            json.dumps(
                {
                    "task_id": "retryable",
                    "channel": "telegram",
                    "chat_id": "8705812936",
                    "_last_failure_classification": "transport-retryable",
                    "_last_failure_retryable": True,
                    "_retry_count": 1,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        diagnostics_dir = self.paths.data_dir / "diagnostics"
        diagnostics_dir.mkdir(parents=True, exist_ok=True)
        (diagnostics_dir / "delivery-outages.json").write_text(
            json.dumps(
                {
                    "schema": "openclaw.task-system.delivery-outages.v1",
                    "outages": [
                        {
                            "channel": "telegram",
                            "chat_id": "8705812936",
                            "reason": "network outage",
                            "acknowledged_at": "2026-04-02T12:00:00+00:00",
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        report = health_report.build_health_report(config_path=self.config_path)
        markdown = health_report.render_markdown(report)

        self.assertEqual(report["status"], "warn")
        self.assertEqual(report["acknowledged_failed_instruction_count"], 1)
        self.assertIn("## Acknowledged Delivery Outages", markdown)

    def test_build_health_report_surfaces_planning_anomaly_and_overdue_followup(self) -> None:
        source = self.store.register_task(
            agent_id="main",
            session_key="session:planning-health",
            channel="telegram",
            chat_id="chat:planning-health",
            task_label="planning health task",
        )
        source.meta["tool_followup_plan"] = {
            "plan_id": "plan_123",
            "status": "anomaly",
            "followup_due_at": "2020-01-01T00:00:00+00:00",
        }
        source.meta["planning_promise_guard"] = {
            "status": "anomaly",
            "expected_by_finalize": True,
        }
        source.meta["planning_anomaly"] = "promise-without-task"
        self.store.save_task(source)

        followup = self.store.observe_task(
            agent_id="main",
            session_key="session:planning-health",
            channel="telegram",
            chat_id="chat:planning-health",
            task_label="planning overdue follow-up",
            meta={"source": "tool-followup-plan", "plan_id": "plan_123"},
        )
        self.store.schedule_continuation(
            followup.task_id,
            continuation_kind="delayed-reply",
            due_at="2020-01-01T00:00:00+00:00",
            payload={"reply_text": "later", "wait_seconds": 60},
            reason="scheduled tool-assisted continuation wait",
        )

        report = health_report.build_health_report(config_path=self.config_path)
        markdown = health_report.render_markdown(report)

        self.assertEqual(report["status"], "error")
        self.assertIn("planning-promise-without-task:1", report["issues"])
        self.assertIn("planning-overdue-followups:1", report["issues"])
        self.assertEqual(report["overview"]["planning"]["health"]["status"], "error")
        self.assertEqual(report["planning_primary_recovery_action"]["kind"], "inspect-promise-without-task")
        self.assertIn("materialize a replacement follow-up", report["issue_entries"][0]["remediation"])
        self.assertIn("- planning_health_status: error", markdown)
        self.assertIn("- planning_primary_recovery_action_kind: inspect-promise-without-task", markdown)

    def test_build_health_report_surfaces_planning_timeouts(self) -> None:
        source = self.store.register_task(
            agent_id="main",
            session_key="session:planning-timeout",
            channel="telegram",
            chat_id="chat:planning-timeout",
            task_label="planning timeout task",
        )
        source.meta["tool_followup_plan"] = {
            "plan_id": "plan_timeout",
            "status": "timeout",
            "followup_due_at": "2099-01-01T00:00:00+00:00",
        }
        source.meta["planning_promise_guard"] = {
            "status": "timeout",
            "expected_by_finalize": True,
        }
        source.meta["planning_anomaly"] = "planner-timeout"
        self.store.save_task(source)

        report = health_report.build_health_report(config_path=self.config_path)
        markdown = health_report.render_markdown(report)

        self.assertEqual(report["status"], "warn")
        self.assertIn("planning-timeouts:1", report["issues"])
        self.assertEqual(report["overview"]["planning"]["health"]["status"], "warn")
        self.assertEqual(report["overview"]["planning"]["health"]["primary_reason"], "planner-timeout-observed")
        self.assertEqual(report["planning_primary_recovery_action"]["kind"], "inspect-planner-timeout")
        self.assertIn("planner-owned follow-up", report["issue_entries"][0]["remediation"])
        self.assertIn("- planning_health_timeout_rate: 1.0", markdown)
        self.assertIn("- planning_primary_recovery_action_kind: inspect-planner-timeout", markdown)

    def test_build_health_report_surfaces_plugin_install_drift(self) -> None:
        with patch.object(
            health_report,
            "build_install_drift_report",
            return_value={
                "ok": False,
                "installed_runtime_exists": True,
                "installed_runtime_dir": "/tmp/installed",
                "missing_in_installed": ["planning_acceptance.py"],
                "extra_in_installed": [],
            },
        ):
            report = health_report.build_health_report(config_path=self.config_path)
            markdown = health_report.render_markdown(report)

        self.assertIn("plugin-install-drift:1", report["issues"])
        self.assertIn("## Installed Runtime Drift", markdown)
        self.assertIn("planning_acceptance.py", markdown)


if __name__ == "__main__":
    unittest.main()
