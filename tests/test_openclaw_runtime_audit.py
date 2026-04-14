from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from runtime_loader import load_runtime_module
except ModuleNotFoundError:
    from tests.runtime_loader import load_runtime_module


openclaw_runtime_audit = load_runtime_module("openclaw_runtime_audit")


class OpenClawRuntimeAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="openclaw-runtime-audit-tests."))
        self.openclaw_home = self.temp_dir / ".openclaw"
        (self.openclaw_home / "tasks").mkdir(parents=True, exist_ok=True)
        (self.openclaw_home / "delivery-queue" / "failed").mkdir(parents=True, exist_ok=True)
        (self.openclaw_home / "cron" / "runs").mkdir(parents=True, exist_ok=True)
        (self.openclaw_home / "logs").mkdir(parents=True, exist_ok=True)
        self._init_task_db()

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _init_task_db(self) -> None:
        connection = sqlite3.connect(str(self.openclaw_home / "tasks" / "runs.sqlite"))
        try:
            connection.executescript(
                """
                CREATE TABLE task_runs (
                  task_id TEXT PRIMARY KEY,
                  runtime TEXT NOT NULL,
                  source_id TEXT,
                  owner_key TEXT NOT NULL,
                  scope_kind TEXT NOT NULL,
                  child_session_key TEXT,
                  parent_task_id TEXT,
                  agent_id TEXT,
                  run_id TEXT,
                  label TEXT,
                  task TEXT NOT NULL,
                  status TEXT NOT NULL,
                  delivery_status TEXT NOT NULL,
                  notify_policy TEXT NOT NULL,
                  created_at INTEGER NOT NULL,
                  started_at INTEGER,
                  ended_at INTEGER,
                  last_event_at INTEGER,
                  cleanup_after INTEGER,
                  error TEXT,
                  progress_summary TEXT,
                  terminal_summary TEXT,
                  terminal_outcome TEXT,
                  parent_flow_id TEXT
                );
                """
            )
            connection.commit()
        finally:
            connection.close()

    def _insert_task(
        self,
        *,
        task_id: str,
        status: str,
        created_at: datetime,
        last_event_at: datetime,
        label: str,
        task: str,
        delivery_status: str = "not_applicable",
        terminal_summary: str | None = None,
        error: str | None = None,
    ) -> None:
        connection = sqlite3.connect(str(self.openclaw_home / "tasks" / "runs.sqlite"))
        try:
            connection.execute(
                """
                INSERT INTO task_runs (
                  task_id, runtime, owner_key, scope_kind, agent_id, run_id, label, task, status,
                  delivery_status, notify_policy, created_at, started_at, ended_at, last_event_at,
                  cleanup_after, error, progress_summary, terminal_summary, terminal_outcome, parent_flow_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    "openclaw",
                    "owner:main",
                    "session",
                    "main",
                    f"run:{task_id}",
                    label,
                    task,
                    status,
                    delivery_status,
                    "default",
                    int(created_at.timestamp() * 1000),
                    int(created_at.timestamp() * 1000),
                    int(last_event_at.timestamp() * 1000) if status == "succeeded" else None,
                    int(last_event_at.timestamp() * 1000),
                    None,
                    error,
                    None,
                    terminal_summary,
                    None,
                    None,
                ),
            )
            connection.commit()
        finally:
            connection.close()

    def test_build_audit_surfaces_stale_running_tasks_and_user_history(self) -> None:
        now = datetime.now(tz=timezone.utc)
        self._insert_task(
            task_id="task-success",
            status="succeeded",
            created_at=now - timedelta(hours=1),
            last_event_at=now - timedelta(minutes=50),
            label="用户问：帮我总结今天进展",
            task="帮我总结今天进展",
            terminal_summary="已完成汇总并回复用户。",
        )
        self._insert_task(
            task_id="task-stale",
            status="running",
            created_at=now - timedelta(hours=30),
            last_event_at=now - timedelta(hours=28),
            label="用户问：我爱吃什么？",
            task="我爱吃什么？",
        )
        (self.openclaw_home / "logs" / "config-health.json").write_text(
            json.dumps({"entries": {}}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        report = openclaw_runtime_audit.build_openclaw_runtime_audit(
            openclaw_home=self.openclaw_home,
            lookback_hours=48,
            recent_limit=5,
            stale_running_hours=6,
        )

        self.assertEqual(report["status"], "error")
        self.assertEqual(len(report["stale_running_tasks"]), 1)
        self.assertEqual(report["recent_tasks"]["task_count"], 2)
        self.assertEqual(report["recent_tasks"]["recent_user_visible_history"][0]["request_excerpt"], "用户问：帮我总结今天进展")
        self.assertEqual(report["recent_tasks"]["recent_user_visible_history"][0]["reply_excerpt"], "已完成汇总并回复用户。")

    def test_build_audit_surfaces_failed_deliveries_and_cron_errors(self) -> None:
        now = datetime.now(tz=timezone.utc)
        self._insert_task(
            task_id="task-ok",
            status="succeeded",
            created_at=now - timedelta(hours=2),
            last_event_at=now - timedelta(hours=2),
            label="测试请求",
            task="测试请求",
            delivery_status="delivered",
            terminal_summary="测试回复",
        )
        (self.openclaw_home / "delivery-queue" / "failed" / "failed-1.json").write_text(
            json.dumps(
                {
                    "id": "failed-1",
                    "channel": "telegram",
                    "to": "slash:123",
                    "retryCount": 2,
                    "enqueuedAt": int((now - timedelta(minutes=20)).timestamp() * 1000),
                    "lastAttemptAt": int((now - timedelta(minutes=10)).timestamp() * 1000),
                    "lastError": "chat not found",
                    "payloads": [{"text": "reply text"}],
                    "mirror": {"sessionKey": "agent:main:telegram:test"},
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (self.openclaw_home / "cron" / "runs" / "job-1.jsonl").write_text(
            json.dumps(
                {
                    "ts": int((now - timedelta(minutes=5)).timestamp() * 1000),
                    "jobId": "job-1",
                    "action": "finished",
                    "status": "error",
                    "error": "Delivering to Feishu requires target",
                    "summary": "提醒发送失败",
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        (self.openclaw_home / "logs" / "config-health.json").write_text(
            json.dumps(
                {
                    "entries": {
                        str(self.openclaw_home / "openclaw.json"): {
                            "lastObservedSuspiciousSignature": None
                        }
                    }
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        report = openclaw_runtime_audit.build_openclaw_runtime_audit(
            openclaw_home=self.openclaw_home,
            lookback_hours=24,
            recent_limit=5,
        )
        markdown = openclaw_runtime_audit.render_markdown(report)

        self.assertEqual(report["status"], "warn")
        self.assertEqual(report["failed_deliveries"]["count"], 1)
        self.assertEqual(report["cron"]["error_count"], 1)
        self.assertIn("failed-deliveries", [item["code"] for item in report["issue_entries"]])
        self.assertIn("cron-delivery-errors", [item["code"] for item in report["issue_entries"]])
        self.assertIn("# OpenClaw Runtime Audit", markdown)
        self.assertIn("## User View", markdown)
        self.assertIn("## Recent Cron Events", markdown)

    def test_recent_user_view_filters_internal_runtime_noise(self) -> None:
        now = datetime.now(tz=timezone.utc)
        self._insert_task(
            task_id="task-internal",
            status="succeeded",
            created_at=now - timedelta(minutes=30),
            last_event_at=now - timedelta(minutes=25),
            label="[Subagent Context] You are running as a subagent",
            task="[Subagent Context] You are running as a subagent",
        )
        self._insert_task(
            task_id="task-user",
            status="succeeded",
            created_at=now - timedelta(minutes=20),
            last_event_at=now - timedelta(minutes=10),
            label="用户问：今天处理了什么？",
            task="今天处理了什么？",
            terminal_summary="已经整理今天的处理结果。",
        )
        (self.openclaw_home / "logs" / "config-health.json").write_text(
            json.dumps({"entries": {}}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        report = openclaw_runtime_audit.build_openclaw_runtime_audit(
            openclaw_home=self.openclaw_home,
            lookback_hours=24,
            recent_limit=5,
        )

        history = report["recent_tasks"]["recent_user_visible_history"]
        self.assertEqual(report["recent_tasks"]["task_count"], 2)
        self.assertEqual(report["recent_tasks"]["user_task_count"], 1)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["task_id"], "task-user")
