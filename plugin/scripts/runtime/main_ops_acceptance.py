#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from main_ops import (
    get_main_continuity_summary,
    get_main_dashboard_summary,
    get_main_triage_summary,
    render_main_continuity,
    render_main_dashboard,
    render_main_triage,
)
from silence_monitor import process_overdue_tasks
from task_state import TaskPaths, TaskStore


@dataclass(frozen=True)
class MainOpsAcceptanceStep:
    step: str
    ok: bool
    detail: str


def _write_config(path: Path, data_dir: Path) -> None:
    path.write_text(
        json.dumps({"taskSystem": {"storageDir": str(data_dir)}}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _scenario_context(root: Path, name: str) -> tuple[Path, TaskPaths, TaskStore]:
    scenario_root = root / name
    scenario_root.mkdir(parents=True, exist_ok=True)
    data_dir = scenario_root / "data"
    config_path = scenario_root / "task_system.json"
    _write_config(config_path, data_dir)
    paths = TaskPaths.from_root(scenario_root, data_dir)
    return config_path, paths, TaskStore(paths=paths)


def run_main_ops_acceptance() -> dict[str, Any]:
    temp_dir = Path(tempfile.mkdtemp(prefix="task-system-main-ops-acceptance."))
    steps: list[MainOpsAcceptanceStep] = []
    try:
        focus_config, focus_paths, focus_store = _scenario_context(temp_dir, "dashboard-focus")
        focus_session = "session:main:ops-focus"
        focus_task = focus_store.register_task(
            agent_id="main",
            session_key=focus_session,
            channel="telegram",
            chat_id="chat:main:ops-focus",
            task_label="ops focus task",
        )
        focus_store.start_task(focus_task.task_id)
        focus_dashboard = get_main_dashboard_summary(
            config_path=focus_config,
            paths=focus_paths,
            session_key=focus_session,
        )
        rendered_focus = render_main_dashboard(
            config_path=focus_config,
            paths=focus_paths,
            session_key=focus_session,
        )
        steps.append(
            MainOpsAcceptanceStep(
                step="session-focused-dashboard-navigation-contract",
                ok=(
                    str(focus_dashboard.get("session_filter") or "") == focus_session
                    and str((focus_dashboard.get("producer_contract") or {}).get("focus_channel") or "") == "telegram"
                    and str((focus_dashboard.get("producer_contract") or {}).get("producer_mode") or "")
                    == "dispatch-side-priority-only"
                    and str(focus_dashboard.get("action_hint_command") or "") == "python3 scripts/runtime/main_ops.py lanes --json"
                    and f"- session_filter: {focus_session}" in rendered_focus
                    and f"main_ops.py continuity --session-key '{focus_session}'" in rendered_focus
                    and f"taskmonitor --session-key '{focus_session}' --action status --json" in rendered_focus
                ),
                detail=json.dumps(
                    {
                        "dashboard": {
                            "session_filter": focus_dashboard.get("session_filter"),
                            "producer_focus_channel": (focus_dashboard.get("producer_contract") or {}).get("focus_channel"),
                            "producer_mode": (focus_dashboard.get("producer_contract") or {}).get("producer_mode"),
                            "action_hint": focus_dashboard.get("action_hint"),
                            "action_hint_command": focus_dashboard.get("action_hint_command"),
                        },
                        "rendered_dashboard": rendered_focus,
                    },
                    ensure_ascii=False,
                ),
            )
        )

        promise_config, promise_paths, promise_store = _scenario_context(temp_dir, "promise-without-task")
        promise_session = "session:main:ops-planning-risk"
        promise_source = promise_store.register_task(
            agent_id="main",
            session_key=promise_session,
            channel="telegram",
            chat_id="chat:main:ops-planning-risk",
            task_label="planning anomaly source",
        )
        promise_source.meta["tool_followup_plan"] = {
            "plan_id": "plan_123",
            "status": "anomaly",
            "followup_due_at": "2020-01-01T00:00:00+00:00",
            "followup_summary": "5分钟后同步结果",
            "main_user_content_mode": "none",
        }
        promise_source.meta["planning_promise_guard"] = {
            "status": "anomaly",
            "expected_by_finalize": True,
        }
        promise_source.meta["planning_anomaly"] = "promise-without-task"
        promise_store.save_task(promise_source)
        promise_followup = promise_store.observe_task(
            agent_id="main",
            session_key=promise_session,
            channel="telegram",
            chat_id="chat:main:ops-planning-risk",
            task_label="planning overdue follow-up",
            meta={"source": "tool-followup-plan", "plan_id": "plan_123"},
        )
        promise_store.schedule_continuation(
            promise_followup.task_id,
            continuation_kind="delayed-reply",
            due_at="2020-01-01T00:00:00+00:00",
            payload={"reply_text": "later", "wait_seconds": 60},
            reason="scheduled tool-assisted continuation wait",
        )
        promise_dashboard = get_main_dashboard_summary(config_path=promise_config, paths=promise_paths)
        promise_continuity = get_main_continuity_summary(config_path=promise_config, paths=promise_paths)
        promise_triage = get_main_triage_summary(config_path=promise_config, paths=promise_paths)
        rendered_promise_dashboard = render_main_dashboard(
            config_path=promise_config,
            paths=promise_paths,
            compact=True,
        )
        rendered_promise_continuity = render_main_continuity(config_path=promise_config, paths=promise_paths)
        steps.append(
            MainOpsAcceptanceStep(
                step="promise-without-task-projects-ops-recovery-contract",
                ok=(
                    str(promise_dashboard.get("status") or "") == "error"
                    and int(((promise_dashboard.get("health") or {}).get("planning_promise_without_task_count") or 0)) == 1
                    and str(promise_dashboard.get("action_hint_command") or "")
                    == f"python3 scripts/runtime/main_ops.py continuity --session-key '{promise_session}'"
                    and int(promise_continuity.get("planning_anomaly_task_count") or 0) == 1
                    and int(promise_continuity.get("overdue_planned_followup_count") or 0) == 1
                    and str((promise_continuity.get("top_risk_session") or {}).get("session_key") or "") == promise_session
                    and str(promise_triage.get("primary_action_kind") or "") == "inspect-promise-without-task"
                    and str(promise_triage.get("primary_action_command") or "")
                    == f"python3 scripts/runtime/main_ops.py show {promise_source.task_id}"
                    and "- planning_promise_without_task: 1" in rendered_promise_dashboard
                    and "- planning_anomaly_task_count: 1" in rendered_promise_continuity
                ),
                detail=json.dumps(
                    {
                        "dashboard": {
                            "status": promise_dashboard.get("status"),
                            "planning_promise_without_task_count": (promise_dashboard.get("health") or {}).get(
                                "planning_promise_without_task_count"
                            ),
                            "planning_overdue_followup_count": (promise_dashboard.get("health") or {}).get(
                                "planning_overdue_followup_count"
                            ),
                            "action_hint_command": promise_dashboard.get("action_hint_command"),
                        },
                        "continuity": {
                            "planning_anomaly_task_count": promise_continuity.get("planning_anomaly_task_count"),
                            "overdue_planned_followup_count": promise_continuity.get("overdue_planned_followup_count"),
                            "top_risk_session": (promise_continuity.get("top_risk_session") or {}).get("session_key"),
                        },
                        "triage": {
                            "primary_action_kind": promise_triage.get("primary_action_kind"),
                            "primary_action_command": promise_triage.get("primary_action_command"),
                        },
                        "rendered_dashboard": rendered_promise_dashboard,
                        "rendered_continuity": rendered_promise_continuity,
                    },
                    ensure_ascii=False,
                ),
            )
        )

        timeout_config, timeout_paths, timeout_store = _scenario_context(temp_dir, "planner-timeout")
        timeout_task = timeout_store.register_task(
            agent_id="main",
            session_key="session:main:ops-planner-timeout",
            channel="telegram",
            chat_id="chat:main:ops-planner-timeout",
            task_label="planning timeout",
        )
        timeout_task.meta["tool_followup_plan"] = {
            "plan_id": "plan_timeout",
            "status": "timeout",
            "followup_due_at": "2099-01-01T00:00:00+00:00",
        }
        timeout_task.meta["planning_promise_guard"] = {
            "status": "timeout",
            "expected_by_finalize": True,
        }
        timeout_task.meta["planning_anomaly"] = "planner-timeout"
        timeout_store.save_task(timeout_task)
        timeout_store.complete_task(timeout_task.task_id)
        timeout_dashboard = get_main_dashboard_summary(config_path=timeout_config, paths=timeout_paths)
        timeout_triage = get_main_triage_summary(config_path=timeout_config, paths=timeout_paths)
        rendered_timeout_triage = render_main_triage(config_path=timeout_config, paths=timeout_paths)
        steps.append(
            MainOpsAcceptanceStep(
                step="planner-timeout-projects-ops-recovery-contract",
                ok=(
                    str(((timeout_dashboard.get("health") or {}).get("planning_health_status") or "")) == "warn"
                    and str((((timeout_dashboard.get("health") or {}).get("planning_primary_recovery_action") or {}).get("kind")) or "")
                    == "inspect-planner-timeout"
                    and str(timeout_dashboard.get("action_hint_command") or "")
                    == f"python3 scripts/runtime/main_ops.py show {timeout_task.task_id}"
                    and str(timeout_triage.get("primary_action_kind") or "") == "inspect-planner-timeout"
                    and str(timeout_triage.get("primary_action_command") or "")
                    == f"python3 scripts/runtime/main_ops.py show {timeout_task.task_id}"
                    and "- planning_health_status: warn" in rendered_timeout_triage
                ),
                detail=json.dumps(
                    {
                        "dashboard": {
                            "planning_health_status": (timeout_dashboard.get("health") or {}).get("planning_health_status"),
                            "planning_primary_recovery_action": (
                                (timeout_dashboard.get("health") or {}).get("planning_primary_recovery_action") or {}
                            ),
                            "action_hint_command": timeout_dashboard.get("action_hint_command"),
                        },
                        "triage": {
                            "planning_health_status": timeout_triage.get("planning_health_status"),
                            "primary_action_kind": timeout_triage.get("primary_action_kind"),
                            "primary_action_command": timeout_triage.get("primary_action_command"),
                        },
                        "rendered_triage": rendered_timeout_triage,
                    },
                    ensure_ascii=False,
                ),
            )
        )

        missing_config, missing_paths, missing_store = _scenario_context(temp_dir, "missing-followup-task")
        missing_session = "session:main:ops-missing-followup"
        missing_task = missing_store.register_task(
            agent_id="main",
            session_key=missing_session,
            channel="telegram",
            chat_id="chat:main:ops-missing-followup",
            task_label="missing follow-up task",
        )
        missing_task.meta["tool_followup_plan"] = {
            "plan_id": "plan_missing_task",
            "status": "scheduled",
            "followup_due_at": "2099-01-01T00:00:00+00:00",
            "followup_task_id": "task_missing_followup_record",
            "followup_summary": "5分钟后同步结果",
            "main_user_content_mode": "none",
        }
        missing_task.meta["planning_promise_guard"] = {
            "status": "scheduled",
            "expected_by_finalize": True,
            "promise_summary": "5分钟后同步结果",
        }
        missing_store.save_task(missing_task)
        missing_dashboard = get_main_dashboard_summary(config_path=missing_config, paths=missing_paths)
        missing_continuity = get_main_continuity_summary(config_path=missing_config, paths=missing_paths)
        missing_triage = get_main_triage_summary(config_path=missing_config, paths=missing_paths)
        rendered_missing_dashboard = render_main_dashboard(config_path=missing_config, paths=missing_paths)
        rendered_missing_continuity = render_main_continuity(config_path=missing_config, paths=missing_paths)
        steps.append(
            MainOpsAcceptanceStep(
                step="missing-followup-projects-ops-recovery-contract",
                ok=(
                    str(missing_dashboard.get("status") or "") == "error"
                    and int(((missing_dashboard.get("health") or {}).get("planning_followup_task_missing_count") or 0)) == 1
                    and str((missing_dashboard.get("action_hint_command") or ""))
                    == f"python3 scripts/runtime/main_ops.py continuity --session-key '{missing_session}'"
                    and int(missing_continuity.get("planning_anomaly_task_count") or 0) == 1
                    and str((missing_continuity.get("top_risk_session") or {}).get("session_key") or "") == missing_session
                    and str(missing_triage.get("primary_action_kind") or "") == "inspect-missing-followup-task"
                    and str(missing_triage.get("primary_action_command") or "")
                    == f"python3 scripts/runtime/main_ops.py show {missing_task.task_id}"
                    and f"- top_followup_session: {missing_session}" in rendered_missing_dashboard
                    and f"continuity --session-key '{missing_session}'" in rendered_missing_dashboard
                    and "- planning_anomaly_task_count: 1" in rendered_missing_continuity
                ),
                detail=json.dumps(
                    {
                        "dashboard": {
                            "status": missing_dashboard.get("status"),
                            "planning_followup_task_missing_count": (missing_dashboard.get("health") or {}).get(
                                "planning_followup_task_missing_count"
                            ),
                            "action_hint_command": missing_dashboard.get("action_hint_command"),
                        },
                        "continuity": {
                            "planning_anomaly_task_count": missing_continuity.get("planning_anomaly_task_count"),
                            "top_risk_session": (missing_continuity.get("top_risk_session") or {}).get("session_key"),
                        },
                        "triage": {
                            "primary_action_kind": missing_triage.get("primary_action_kind"),
                            "primary_action_command": missing_triage.get("primary_action_command"),
                        },
                        "rendered_dashboard": rendered_missing_dashboard,
                        "rendered_continuity": rendered_missing_continuity,
                    },
                    ensure_ascii=False,
                ),
            )
        )

        auto_config, auto_paths, auto_store = _scenario_context(temp_dir, "auto-resume")
        auto_task = auto_store.register_task(
            agent_id="main",
            session_key="session:main:ops-auto-resume",
            channel="telegram",
            chat_id="chat:main:ops-auto-resume",
            task_label="blocked main task",
        )
        auto_running = auto_store.start_task(auto_task.task_id)
        auto_running.last_user_visible_update_at = "2020-01-01T00:00:00+00:00"
        auto_running.meta["finalize_skipped_reason"] = "success-without-visible-progress"
        auto_store.save_task(auto_running)
        process_overdue_tasks(paths=auto_paths)
        auto_continuity = get_main_continuity_summary(config_path=auto_config, paths=auto_paths)
        auto_continuity_compact = get_main_continuity_summary(
            config_path=auto_config,
            paths=auto_paths,
            compact=True,
        )
        auto_continuity_issues = get_main_continuity_summary(
            config_path=auto_config,
            paths=auto_paths,
            only_issues=True,
        )
        auto_dashboard = get_main_dashboard_summary(config_path=auto_config, paths=auto_paths)
        auto_triage = get_main_triage_summary(config_path=auto_config, paths=auto_paths)
        auto_triage_compact = get_main_triage_summary(
            config_path=auto_config,
            paths=auto_paths,
            compact=True,
        )
        rendered_auto_dashboard = render_main_dashboard(
            config_path=auto_config,
            paths=auto_paths,
            only_issues=True,
        )
        rendered_auto_continuity_compact = render_main_continuity(
            config_path=auto_config,
            paths=auto_paths,
            compact=True,
        )
        rendered_auto_continuity_issues = render_main_continuity(
            config_path=auto_config,
            paths=auto_paths,
            only_issues=True,
        )
        rendered_auto_triage = render_main_triage(config_path=auto_config, paths=auto_paths)
        rendered_auto_triage_compact = render_main_triage(
            config_path=auto_config,
            paths=auto_paths,
            compact=True,
        )
        steps.append(
            MainOpsAcceptanceStep(
                step="watchdog-blocked-projects-auto-resume-contract",
                ok=(
                    bool(auto_continuity.get("auto_resume_ready"))
                    and bool(auto_continuity.get("auto_resume_safe_to_apply"))
                    and str(auto_continuity.get("primary_action_kind") or "") == "apply-auto-resume"
                    and str(auto_dashboard.get("action_hint_command") or "")
                    == "python3 scripts/runtime/main_ops.py continuity --auto-resume-if-safe"
                    and str(auto_triage.get("primary_action_kind") or "") == "apply-auto-resume"
                    and str(auto_triage.get("primary_action_command") or "")
                    == "python3 scripts/runtime/main_ops.py continuity --auto-resume-if-safe"
                    and "continuity --auto-resume-if-safe" in rendered_auto_dashboard
                    and "continuity --auto-resume-if-safe" in rendered_auto_triage
                ),
                detail=json.dumps(
                    {
                        "continuity": {
                            "auto_resume_ready": auto_continuity.get("auto_resume_ready"),
                            "auto_resume_safe_to_apply": auto_continuity.get("auto_resume_safe_to_apply"),
                            "primary_action_kind": auto_continuity.get("primary_action_kind"),
                            "primary_action_command": auto_continuity.get("primary_action_command"),
                        },
                        "dashboard": {
                            "status": auto_dashboard.get("status"),
                            "action_hint": auto_dashboard.get("action_hint"),
                            "action_hint_command": auto_dashboard.get("action_hint_command"),
                        },
                        "triage": {
                            "triage_status": auto_triage.get("triage_status"),
                            "primary_action_kind": auto_triage.get("primary_action_kind"),
                            "primary_action_command": auto_triage.get("primary_action_command"),
                        },
                        "rendered_dashboard": rendered_auto_dashboard,
                        "rendered_triage": rendered_auto_triage,
                    },
                    ensure_ascii=False,
                ),
            )
        )
        steps.append(
            MainOpsAcceptanceStep(
                step="operator-snapshot-views-contract",
                ok=(
                    bool(auto_continuity_compact.get("compact"))
                    and str((auto_continuity_compact.get("compact_summary") or {}).get("auto_resume_summary") or "")
                    == "safe"
                    and bool(auto_continuity_issues.get("only_issues"))
                    and bool((auto_continuity_issues.get("issue_summary") or {}).get("has_issues"))
                    and str((auto_continuity_issues.get("issue_summary") or {}).get("primary_action_kind") or "")
                    == "apply-auto-resume"
                    and bool(auto_triage_compact.get("compact"))
                    and str((auto_triage_compact.get("compact_summary") or {}).get("auto_resume_summary") or "")
                    == "safe"
                    and "- auto_resume: safe" in rendered_auto_continuity_compact
                    and "- primary_action: apply-auto-resume" in rendered_auto_continuity_compact
                    and "- watchdog_blocked_task_count: 1" in rendered_auto_continuity_issues
                    and "## Auto-Resumable" not in rendered_auto_continuity_issues
                    and "- auto_resume: safe" in rendered_auto_triage_compact
                    and "- primary_action: apply-auto-resume" in rendered_auto_triage_compact
                    and "## Next Actions" not in rendered_auto_triage_compact
                ),
                detail=json.dumps(
                    {
                        "continuity_compact": auto_continuity_compact.get("compact_summary"),
                        "continuity_issues": auto_continuity_issues.get("issue_summary"),
                        "triage_compact": auto_triage_compact.get("compact_summary"),
                        "rendered_continuity_compact": rendered_auto_continuity_compact,
                        "rendered_continuity_issues": rendered_auto_continuity_issues,
                        "rendered_triage_compact": rendered_auto_triage_compact,
                    },
                    ensure_ascii=False,
                ),
            )
        )

        return {
            "ok": all(step.ok for step in steps),
            "steps": [asdict(step) for step in steps],
            "tempDir": str(temp_dir),
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def render_markdown(payload: dict[str, Any]) -> str:
    lines = ["# Main Ops Acceptance", ""]
    lines.append(f"- ok: {payload['ok']}")
    for step in payload["steps"]:
        status = "ok" if step["ok"] else "failed"
        lines.append(f"- {step['step']}: {status}")
        lines.append(f"  detail: {step['detail']}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    payload = run_main_ops_acceptance()
    if args and args[0] == "--json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(payload), end="")
