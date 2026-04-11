#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from argparse import ArgumentParser
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from channel_acceptance import build_channel_acceptance_summary, render_channel_acceptance_summary
from delivery_reconcile import reconcile_delivery_artifacts
from delivery_outage import acknowledge_outage, clear_outage
from health_report import build_health_report
from instruction_executor import (
    annotate_failed_instruction_metadata,
    resolve_failed_instructions,
    retry_failed_instructions,
)
from main_task_adapter import block_main_task, fail_main_task, finish_main_task, resume_main_task
from plugin_install_drift import build_install_drift_report
from producer_contract import (
    build_producer_contract_summary,
    infer_channel_from_session_key,
    render_producer_contract_summary,
)
from silence_monitor import scan_tasks
from task_config import load_task_system_config
from task_status import build_planning_health_summary, list_inflight_statuses, render_overview_markdown, render_status_markdown
from task_state import STATUS_QUEUED, STATUS_RUNNING, TaskPaths, TaskStore, default_paths
from taskmonitor_state import get_taskmonitor_enabled, list_taskmonitor_overrides, set_taskmonitor_enabled
from user_status import project_user_facing_status


def _resolve_paths(config_path: Optional[Path], *, paths: Optional[TaskPaths] = None) -> TaskPaths:
    if paths is not None:
        return paths
    config = load_task_system_config(config_path=config_path)
    return config.build_paths() or default_paths()


def _observed_channels_for_main(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
) -> list[str]:
    return sorted(
        {
            str(status.get("channel") or "").strip().lower()
            for status in list_inflight_statuses(config_path=config_path, paths=paths)
            if str(status.get("agent_id") or "") == "main" and str(status.get("channel") or "").strip()
        }
    )


def list_main_tasks(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
) -> list[dict[str, object]]:
    return [
        status
        for status in list_inflight_statuses(config_path=config_path, paths=paths)
        if status["agent_id"] == "main"
    ]


def render_main_list(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
) -> str:
    tasks = list_main_tasks(config_path=config_path, paths=paths)
    if not tasks:
        return "# Main Tasks\n\n- none\n"
    lines = ["# Main Tasks", ""]
    for task in tasks:
        lines.append(
            f"- {task['task_id']} | {task['status']} | user_status={_task_user_facing_status(task)} | delivery={task['delivery']['state']} | {task['task_label']}"
        )
    return "\n".join(lines) + "\n"


def render_main_health(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
) -> str:
    summary = get_main_health_summary(config_path=config_path, paths=paths)
    lines = [
        "# Main Ops Health",
        "",
        f"- status: {summary['status']}",
        f"- main_active_task_count: {summary['main_active_task_count']}",
        f"- main_blocked_task_count: {summary['main_blocked_task_count']}",
        f"- planning_pending_task_count: {summary['planning_pending_task_count']}",
        f"- planning_promise_without_task_count: {summary['planning_promise_without_task_count']}",
        f"- planning_overdue_followup_count: {summary['planning_overdue_followup_count']}",
        f"- planning_health_status: {summary['planning_health_status']}",
        f"- planning_health_timeout_count: {summary['planning_health_timeout_count']}",
        f"- failed_instruction_count: {summary['failed_instruction_count']}",
        f"- active_stale_delivery_task_count: {summary['active_stale_delivery_task_count']}",
    ]
    if isinstance(summary.get("planning_primary_recovery_action"), dict):
        lines.append(
            f"- planning_primary_recovery_action_kind: {summary['planning_primary_recovery_action'].get('kind')}"
        )
        lines.append(
            f"- planning_primary_recovery_action_command: {summary['planning_primary_recovery_action'].get('command') or 'none'}"
        )
    if summary["blocked_main_tasks"]:
        lines.append("")
        lines.append("## Blocked Main Tasks")
        lines.append("")
        for task in summary["blocked_main_tasks"]:
            lines.append(f"- {task['task_id']} | {task['task_label']}")
    return "\n".join(lines) + "\n"


def get_main_health_summary(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
) -> dict[str, object]:
    report = build_health_report(config_path=config_path, paths=paths)
    overview = report["overview"]
    blocked_main = [
        task for task in overview["active_tasks"] if task["agent_id"] == "main" and task["status"] == "blocked"
    ]
    planning = overview.get("planning") if isinstance(overview.get("planning"), dict) else {}
    return {
        "status": report["status"],
        "main_active_task_count": len(
            [task for task in overview["active_tasks"] if task["agent_id"] == "main"]
        ),
        "main_blocked_task_count": len(blocked_main),
        "planning_pending_task_count": int(planning.get("planning_pending_task_count", 0) or 0),
        "planning_promise_without_task_count": int(planning.get("promise_without_task_count", 0) or 0),
        "planning_overdue_followup_count": int(planning.get("overdue_followup_count", 0) or 0),
        "planning_health_status": str((planning.get("health") or {}).get("status") or "unknown"),
        "planning_health_timeout_count": int(((planning.get("health") or {}).get("timeout_count") or 0)),
        "planning_health_sample_task_count": int(((planning.get("health") or {}).get("sample_task_count") or 0)),
        "planning_primary_recovery_action": planning.get("primary_recovery_action")
        if isinstance(planning.get("primary_recovery_action"), dict)
        else None,
        "failed_instruction_count": overview["failed_instruction_count"],
        "active_stale_delivery_task_count": overview["active_stale_delivery_task_count"],
        "blocked_main_tasks": blocked_main,
    }


def get_main_planning_summary(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
    session_key: Optional[str] = None,
) -> dict[str, object]:
    resolved_paths = _resolve_paths(config_path, paths=paths)
    normalized_session_key = str(session_key or "").strip() or None
    statuses = [
        status
        for status in list_inflight_statuses(config_path=config_path, paths=resolved_paths)
        if str(status.get("agent_id") or "") == "main"
        and (normalized_session_key is None or str(status.get("session_key") or "") == normalized_session_key)
    ]
    planning_items = [
        status
        for status in statuses
        if isinstance(status.get("planning"), dict) and bool(status["planning"].get("tool_path_used"))
    ]
    anomaly_items = [
        status for status in planning_items if bool((status.get("planning") or {}).get("anomaly"))
    ]
    pending_items = [
        status for status in planning_items if bool((status.get("planning") or {}).get("planning_pending"))
    ]
    overdue_items = [
        status for status in planning_items if bool((status.get("planning") or {}).get("overdue_followup"))
    ]
    planned_followups = [
        {
            "task_id": str(status.get("task_id") or ""),
            "session_key": str(status.get("session_key") or ""),
            "task_label": str(status.get("task_label") or ""),
            "status": str(status.get("status") or ""),
            "planning": status.get("planning"),
            "user_facing_status_code": str(status.get("user_facing_status_code") or ""),
            "user_facing_status": str(status.get("user_facing_status") or ""),
        }
        for status in sorted(
            planning_items,
            key=lambda item: (
                not bool((item.get("planning") or {}).get("anomaly")),
                not bool((item.get("planning") or {}).get("overdue_followup")),
                str(item.get("created_at") or ""),
                str(item.get("task_id") or ""),
            ),
        )
    ]
    primary_action = {
        "kind": "none",
        "summary": "No planning anomaly requires immediate action.",
        "command": None,
        "session_key": normalized_session_key,
    }
    if anomaly_items:
        first = anomaly_items[0]
        recovery_action = (
            (first.get("planning") or {}).get("recovery_action")
            if isinstance(first.get("planning"), dict)
            else None
        )
        primary_action = {
            "kind": str((recovery_action or {}).get("kind") or "inspect-planning-anomaly"),
            "summary": str((recovery_action or {}).get("summary") or "Inspect the planning anomaly first."),
            "command": str((recovery_action or {}).get("command") or f"python3 scripts/runtime/main_ops.py show {first['task_id']}"),
            "session_key": (recovery_action or {}).get("session_key") or first.get("session_key"),
        }
    elif overdue_items:
        first = overdue_items[0]
        recovery_action = (
            (first.get("planning") or {}).get("recovery_action")
            if isinstance(first.get("planning"), dict)
            else None
        )
        primary_action = {
            "kind": str((recovery_action or {}).get("kind") or "inspect-overdue-followup"),
            "summary": str((recovery_action or {}).get("summary") or "Inspect the overdue planned follow-up first."),
            "command": str((recovery_action or {}).get("command") or f"python3 scripts/runtime/main_ops.py show {first['task_id']}"),
            "session_key": (recovery_action or {}).get("session_key") or first.get("session_key"),
        }
    elif pending_items:
        first = pending_items[0]
        recovery_action = (
            (first.get("planning") or {}).get("recovery_action")
            if isinstance(first.get("planning"), dict)
            else None
        )
        primary_action = {
            "kind": str((recovery_action or {}).get("kind") or "inspect-pending-plan"),
            "summary": str((recovery_action or {}).get("summary") or "Inspect the pending plan first."),
            "command": str((recovery_action or {}).get("command") or f"python3 scripts/runtime/main_ops.py show {first['task_id']}"),
            "session_key": (recovery_action or {}).get("session_key") or first.get("session_key"),
        }
    status = "ok"
    if anomaly_items:
        status = "error"
    elif overdue_items or pending_items:
        status = "warn"
    suggested_next_commands = [
        *([primary_action["command"]] if primary_action["command"] else []),
        "python3 scripts/runtime/main_ops.py dashboard --json",
        "python3 scripts/runtime/main_ops.py continuity --json",
        "python3 scripts/runtime/main_ops.py triage --json",
    ]
    deduped_commands: list[str] = []
    for command in suggested_next_commands:
        if command and command not in deduped_commands:
            deduped_commands.append(command)
    planning_health = build_planning_health_summary(planning_items)
    return {
        "session_filter": normalized_session_key or "all",
        "status": status,
        "planning_task_count": len(planning_items),
        "planning_pending_task_count": len(pending_items),
        "planning_anomaly_task_count": len(anomaly_items),
        "overdue_planned_followup_count": len(overdue_items),
        "planning_health": planning_health,
        "planning_recovery_action_counts": dict(
            sorted(
                Counter(
                    str(((item.get("planning") or {}).get("recovery_action") or {}).get("kind") or "")
                    for item in planning_items
                    if str(((item.get("planning") or {}).get("recovery_action") or {}).get("kind") or "") not in {"", "none"}
                ).items()
            )
        ),
        "primary_recovery_action": primary_action,
        "primary_action_kind": primary_action["kind"],
        "primary_action_command": primary_action["command"],
        "primary_action_summary": primary_action["summary"],
        "requires_action": status != "ok",
        "primary_action": primary_action,
        "suggested_next_commands": deduped_commands,
        "tasks": planned_followups,
    }


def render_main_planning(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
    session_key: Optional[str] = None,
) -> str:
    summary = get_main_planning_summary(config_path=config_path, paths=paths, session_key=session_key)
    lines = [
        "# Main Planning",
        "",
        f"- session_filter: {summary['session_filter']}",
        f"- status: {summary['status']}",
        f"- planning_task_count: {summary['planning_task_count']}",
        f"- planning_pending_task_count: {summary['planning_pending_task_count']}",
        f"- planning_anomaly_task_count: {summary['planning_anomaly_task_count']}",
        f"- overdue_planned_followup_count: {summary['overdue_planned_followup_count']}",
        f"- planning_health_status: {summary['planning_health']['status']}",
        f"- planning_health_primary_reason: {summary['planning_health']['primary_reason']}",
        f"- planning_health_sample_task_count: {summary['planning_health']['sample_task_count']}",
        f"- planning_health_success_rate: {summary['planning_health']['success_rate']}",
        f"- planning_health_timeout_rate: {summary['planning_health']['timeout_rate']}",
        f"- planning_health_tool_call_completion_rate: {summary['planning_health']['tool_call_completion_rate']}",
        f"- planning_primary_recovery_action_kind: {summary['primary_recovery_action']['kind']}",
        f"- planning_primary_recovery_action_command: {summary['primary_recovery_action']['command'] or 'none'}",
        f"- planning_recovery_action_counts: {json.dumps(summary['planning_recovery_action_counts'], ensure_ascii=False)}",
        f"- primary_action_kind: {summary['primary_action_kind']}",
        f"- primary_action_summary: {summary['primary_action_summary']}",
        f"- primary_action_command: {summary['primary_action_command'] or 'none'}",
    ]
    tasks = summary.get("tasks", [])
    if isinstance(tasks, list) and tasks:
        lines.extend(["", "## Tasks", ""])
        for item in tasks:
            planning = item.get("planning") if isinstance(item.get("planning"), dict) else {}
            lines.append(
                f"- {item['task_id']} | {item['status']} | plan_status={planning.get('plan_status') or 'none'} | anomaly={planning.get('anomaly') or 'none'} | overdue={planning.get('overdue_followup')} | {item['task_label']}"
            )
            if planning.get("followup_summary"):
                lines.append(f"  followup_summary: {planning['followup_summary']}")
            if planning.get("followup_due_at"):
                lines.append(f"  followup_due_at: {planning['followup_due_at']}")
            recovery_action = planning.get("recovery_action") if isinstance(planning.get("recovery_action"), dict) else {}
            if recovery_action and str(recovery_action.get("kind") or "") != "none":
                lines.append(f"  recovery_action: {recovery_action.get('kind')}")
                lines.append(f"  recovery_command: {recovery_action.get('command')}")
    return "\n".join(lines) + "\n"


def get_main_plugin_install_drift_summary() -> dict[str, object]:
    report = build_install_drift_report()
    missing_in_installed = list(report.get("missing_in_installed", []))
    extra_in_installed = list(report.get("extra_in_installed", []))
    status = "ok"
    primary_action = {
        "kind": "none",
        "summary": "Installed runtime is in sync with the installable plugin payload.",
        "command": None,
    }
    if not bool(report.get("installed_runtime_exists")):
        status = "error"
        primary_action = {
            "kind": "inspect-installed-runtime",
            "summary": "Installed runtime is missing; inspect local OpenClaw plugin installation first.",
            "command": "python3 scripts/runtime/plugin_install_drift.py --json",
        }
    elif missing_in_installed or extra_in_installed:
        status = "warn"
        primary_action = {
            "kind": "inspect-installed-runtime",
            "summary": "Installed runtime drift is detected; inspect missing or extra files first.",
            "command": "python3 scripts/runtime/plugin_install_drift.py --json",
        }
    suggested_next_commands = [
        *(["python3 scripts/runtime/plugin_install_drift.py --json"] if status != "ok" else []),
        "python3 scripts/runtime/plugin_doctor.py --json",
        "python3 scripts/runtime/health_report.py --json",
    ]
    deduped_commands: list[str] = []
    for command in suggested_next_commands:
        if command and command not in deduped_commands:
            deduped_commands.append(command)
    return {
        "status": status,
        "installed_runtime_exists": bool(report.get("installed_runtime_exists")),
        "source_runtime_dir": report.get("source_runtime_dir"),
        "installed_runtime_dir": report.get("installed_runtime_dir"),
        "source_file_count": int(report.get("source_file_count", 0) or 0),
        "installed_file_count": int(report.get("installed_file_count", 0) or 0),
        "missing_in_installed_count": len(missing_in_installed),
        "extra_in_installed_count": len(extra_in_installed),
        "missing_in_installed": missing_in_installed,
        "extra_in_installed": extra_in_installed,
        "primary_action_kind": primary_action["kind"],
        "primary_action_command": primary_action["command"],
        "requires_action": status != "ok",
        "primary_action": primary_action,
        "suggested_next_commands": deduped_commands,
        "report": report,
    }


def render_main_plugin_install_drift() -> str:
    summary = get_main_plugin_install_drift_summary()
    lines = [
        "# Main Plugin Install Drift",
        "",
        f"- status: {summary['status']}",
        f"- installed_runtime_exists: {summary['installed_runtime_exists']}",
        f"- source_file_count: {summary['source_file_count']}",
        f"- installed_file_count: {summary['installed_file_count']}",
        f"- missing_in_installed_count: {summary['missing_in_installed_count']}",
        f"- extra_in_installed_count: {summary['extra_in_installed_count']}",
        f"- primary_action_kind: {summary['primary_action_kind']}",
        f"- primary_action_command: {summary['primary_action_command'] or 'none'}",
    ]
    if summary["missing_in_installed"]:
        lines.extend(["", "## Missing In Installed", ""])
        for name in summary["missing_in_installed"]:
            lines.append(f"- {name}")
    if summary["extra_in_installed"]:
        lines.extend(["", "## Extra In Installed", ""])
        for name in summary["extra_in_installed"]:
            lines.append(f"- {name}")
    return "\n".join(lines) + "\n"


def _derive_execution_recommendation(
    *,
    shared_kind: str,
    shared_with_running_lane: bool,
) -> str:
    if shared_kind == "shared" and shared_with_running_lane:
        return "serial"
    if shared_kind == "shared":
        return "serial-per-session"
    return "parallel-safe"


def _summarize_agent_execution_strategy(
    agent_id: str,
    tasks: list[object],
) -> dict[str, object]:
    session_keys = sorted({str(task.session_key) for task in tasks})
    running_sessions = sorted({str(task.session_key) for task in tasks if str(task.status) == STATUS_RUNNING})
    lane_kind = "shared" if len(session_keys) > 1 else "single-session"
    shared_with_running_lane = len(running_sessions) > 0
    execution_recommendation = _derive_execution_recommendation(
        shared_kind=lane_kind,
        shared_with_running_lane=shared_with_running_lane,
    )
    if lane_kind == "shared":
        execution_reason = (
            f"agent {agent_id} currently has {len(session_keys)} active sessions sharing the same lane"
        )
    else:
        execution_reason = f"agent {agent_id} currently has one active session in the lane"
    return {
        "lane_kind": lane_kind,
        "session_count": len(session_keys),
        "shared_sessions": session_keys if len(session_keys) > 1 else [],
        "shared_with_running_lane": shared_with_running_lane,
        "execution_recommendation": execution_recommendation,
        "execution_reason": execution_reason,
    }


def _build_continuity_execution_plan(
    *,
    session_filter: str,
    execution_recommendation: str,
    auto_resumable_task_count: int,
    suggested_next_commands: list[str],
) -> dict[str, object]:
    plan_steps: list[str] = []
    if auto_resumable_task_count > 0:
        plan_steps.append("Run a dry-run first to preview which watchdog-blocked tasks are eligible.")
        if execution_recommendation == "serial":
            plan_steps.append("Use --respect-execution-advice so only the currently allowed session is resumed.")
        plan_steps.append("If the dry-run looks correct, rerun without --dry-run to apply the resume.")
    else:
        plan_steps.append("No auto-resumable continuity action is pending right now.")
    plan_steps.append("Inspect continuity and lanes output again after any resume action.")
    return {
        "session_filter": session_filter,
        "execution_recommendation": execution_recommendation,
        "steps": plan_steps,
        "commands": suggested_next_commands,
    }


def render_main_continuity(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
    session_key: Optional[str] = None,
) -> str:
    resolved_paths = _resolve_paths(config_path, paths=paths)
    runtime_config = load_task_system_config(config_path=config_path)
    store = TaskStore(paths=resolved_paths)
    normalized_session_key = str(session_key or "").strip() or None
    main_tasks = store.find_inflight_tasks(agent_id="main")
    if normalized_session_key:
        main_tasks = [task for task in main_tasks if task.session_key == normalized_session_key]
    inflight_statuses = {
        str(status["task_id"]): status
        for status in list_inflight_statuses(config_path=config_path, paths=resolved_paths)
        if str(status.get("agent_id")) == "main"
        and (normalized_session_key is None or str(status.get("session_key")) == normalized_session_key)
    }
    queue_like_tasks = [task for task in main_tasks if task.status in {"received", "queued", "running", "paused"}]
    execution_strategy = _summarize_agent_execution_strategy("main", queue_like_tasks)
    blocked_without_watchdog = [
        task
        for task in main_tasks
        if task.status == "blocked" and not str(task.meta.get("watchdog_escalation") or "").strip()
    ]
    watchdog_blocked = [
        task
        for task in main_tasks
        if task.status == "blocked" and str(task.meta.get("watchdog_escalation") or "").strip()
    ]
    monitored_tasks = [
        task
        for task in main_tasks
        if task.status in {"received", "queued", "running"}
    ]
    main_tasks_by_id = {task.task_id: task for task in main_tasks}
    monitor = runtime_config.agent_config("main").silence_monitor
    continuity_findings = (
        scan_tasks(
            monitored_tasks,
            timeout_seconds=monitor.silent_timeout_seconds,
            resend_interval_seconds=monitor.resend_interval_seconds,
        )
        if monitor.enabled
        else []
    )
    overdue_findings = [finding for finding in continuity_findings if finding.silence_seconds > monitor.silent_timeout_seconds]
    auto_resumable = sorted(watchdog_blocked, key=lambda item: item.updated_at, reverse=True)
    overdue_by_task_id = {finding.task_id: finding for finding in overdue_findings}
    auto_resumable_ids = {task.task_id for task in auto_resumable}
    manual_review = sorted(
        [finding for finding in overdue_findings if finding.task_id not in auto_resumable_ids],
        key=lambda item: (-item.silence_seconds, item.task_id),
    )
    not_recommended = sorted(
        blocked_without_watchdog,
        key=lambda item: item.updated_at,
        reverse=True,
    )
    session_summary: dict[str, dict[str, object]] = {}

    def ensure_session(session_key: str) -> dict[str, object]:
        bucket = session_summary.get(session_key)
        if bucket is None:
            bucket = {
                "session_key": session_key,
                "auto_resumable_count": 0,
                "manual_review_count": 0,
                "not_recommended_count": 0,
                "planning_anomaly_count": 0,
                "overdue_followup_count": 0,
                "task_labels": [],
                "user_facing_status_counts": {},
                "user_facing_status_code_counts": {},
            }
            session_summary[session_key] = bucket
        return bucket

    for task in auto_resumable:
        bucket = ensure_session(task.session_key)
        bucket["auto_resumable_count"] = int(bucket["auto_resumable_count"]) + 1
        bucket["task_labels"].append(task.task_label)
    for finding in manual_review:
        task = main_tasks_by_id.get(finding.task_id)
        bucket = ensure_session(finding.session_key)
        bucket["manual_review_count"] = int(bucket["manual_review_count"]) + 1
        if task:
            bucket["task_labels"].append(task.task_label)
    for task in not_recommended:
        bucket = ensure_session(task.session_key)
        bucket["not_recommended_count"] = int(bucket["not_recommended_count"]) + 1
        bucket["task_labels"].append(task.task_label)
    for task in main_tasks:
        status_entry = inflight_statuses.get(task.task_id)
        planning = status_entry.get("planning") if isinstance(status_entry, dict) and isinstance(status_entry.get("planning"), dict) else {}
        if planning.get("anomaly") or planning.get("overdue_followup"):
            bucket = ensure_session(task.session_key)
            bucket["task_labels"].append(task.task_label)

    for task in main_tasks:
        bucket = session_summary.get(task.session_key)
        if bucket is None:
            continue
        status_entry = inflight_statuses.get(task.task_id)
        if status_entry:
            projection = _task_user_facing_projection(status_entry)
            label_counts = bucket["user_facing_status_counts"]
            if isinstance(label_counts, dict):
                label = projection["label"]
                label_counts[label] = int(label_counts.get(label, 0)) + 1
            code_counts = bucket["user_facing_status_code_counts"]
            if isinstance(code_counts, dict):
                code = projection["code"]
                code_counts[code] = int(code_counts.get(code, 0)) + 1
            planning = status_entry.get("planning") if isinstance(status_entry.get("planning"), dict) else {}
            if planning.get("anomaly"):
                bucket["planning_anomaly_count"] = int(bucket["planning_anomaly_count"]) + 1
            if planning.get("overdue_followup"):
                bucket["overdue_followup_count"] = int(bucket["overdue_followup_count"]) + 1

    suggested_next_commands = [
        "python3 scripts/runtime/main_ops.py lanes --json",
        *(
            [
                f"python3 scripts/runtime/main_ops.py continuity --session-key '{normalized_session_key}'"
            ]
            if normalized_session_key
            else []
        ),
    ]
    execution_plan = _build_continuity_execution_plan(
        session_filter=normalized_session_key or "all",
        execution_recommendation=str(execution_strategy["execution_recommendation"]),
        auto_resumable_task_count=len(auto_resumable),
        suggested_next_commands=suggested_next_commands,
    )
    top_risk_session_key = None
    if session_summary:
        top_risk_session_key = sorted(
            session_summary,
            key=lambda key: (
                -(
                    int(session_summary[key]["auto_resumable_count"])
                    + int(session_summary[key]["manual_review_count"])
                    + int(session_summary[key]["not_recommended_count"])
                ),
                key,
            ),
        )[0]
    primary_action = {
        "kind": "none",
        "summary": "No immediate continuity action is needed.",
        "command": None,
        "session_key": None,
    }
    auto_resume_command_parts = [
        "python3 scripts/runtime/main_ops.py continuity --resume-watchdog-blocked",
        *([f"--session-key '{normalized_session_key}'"] if normalized_session_key else []),
        *(["--respect-execution-advice"] if str(execution_strategy["execution_recommendation"]) == "serial" else []),
    ]
    auto_resume_if_safe_command = " ".join(
        [
            "python3 scripts/runtime/main_ops.py continuity --auto-resume-if-safe",
            *([f"--session-key '{normalized_session_key}'"] if normalized_session_key else []),
        ]
    )
    auto_resume_if_safe_command = " ".join(
        [
            "python3 scripts/runtime/main_ops.py continuity --auto-resume-if-safe",
            *([f"--session-key '{normalized_session_key}'"] if normalized_session_key else []),
        ]
    )
    auto_resume_if_safe_command = " ".join(
        [
            "python3 scripts/runtime/main_ops.py continuity --auto-resume-if-safe",
            *([f"--session-key '{normalized_session_key}'"] if normalized_session_key else []),
        ]
    )
    auto_resume_preview_command = (
        " ".join([*auto_resume_command_parts, "--dry-run"])
        if auto_resumable
        else None
    )
    auto_resume_has_blockers = bool(manual_review or not_recommended)
    auto_resume_apply_command = " ".join(auto_resume_command_parts) if auto_resumable else None
    if auto_resumable and not auto_resume_has_blockers and auto_resume_apply_command:
        primary_action = {
            "kind": "apply-auto-resume",
            "summary": "Apply the watchdog auto-resume plan now.",
            "command": auto_resume_if_safe_command,
            "session_key": normalized_session_key or top_risk_session_key,
        }
    elif auto_resumable and auto_resume_preview_command:
        primary_action = {
            "kind": "preview-auto-resume",
            "summary": "Preview watchdog auto-resume candidates first.",
            "command": auto_resume_preview_command,
            "session_key": normalized_session_key or top_risk_session_key,
        }
    elif top_risk_session_key:
        primary_action = {
            "kind": "followup-session",
            "summary": f"Inspect continuity for session {top_risk_session_key} first.",
            "command": f"python3 scripts/runtime/main_ops.py continuity --session-key '{top_risk_session_key}'",
            "session_key": top_risk_session_key,
        }

    lines = [
        "# Main Continuity",
        "",
        f"- session_filter: {normalized_session_key or 'all'}",
        f"- silence_monitor_enabled: {monitor.enabled}",
        f"- silent_timeout_seconds: {monitor.silent_timeout_seconds}",
        f"- resend_interval_seconds: {monitor.resend_interval_seconds}",
        f"- execution_recommendation: {execution_strategy['execution_recommendation']}",
        f"- execution_reason: {execution_strategy['execution_reason']}",
        f"- active_monitored_task_count: {len(monitored_tasks)}",
        f"- overdue_monitored_task_count: {len(overdue_findings)}",
        f"- watchdog_blocked_task_count: {len(watchdog_blocked)}",
        f"- auto_resumable_task_count: {len(auto_resumable)}",
        f"- manual_review_task_count: {len(manual_review)}",
        f"- not_recommended_auto_resume_count: {len(not_recommended)}",
        f"- planning_anomaly_task_count: {sum(int(bucket['planning_anomaly_count']) for bucket in session_summary.values())}",
        f"- overdue_planned_followup_count: {sum(int(bucket['overdue_followup_count']) for bucket in session_summary.values())}",
        f"- top_risk_session: {top_risk_session_key or 'none'}",
        f"- primary_action: {primary_action['kind']}",
        f"- primary_action_command: {primary_action['command'] or 'none'}",
    ]

    if auto_resumable:
        lines.extend(["", "## Auto-Resumable", ""])
        for task in auto_resumable:
            lines.append(
                f"- {task.task_id} | escalation={task.meta.get('watchdog_escalation')} | updated_at={task.updated_at}"
            )
            if task.task_id in overdue_by_task_id:
                finding = overdue_by_task_id[task.task_id]
                lines.append(
                    f"  detail: silence={finding.silence_seconds}s | notify={finding.should_notify} | reason={finding.reason}"
                )
            lines.append(
                f"  resume: python3 scripts/runtime/main_ops.py resume {task.task_id} --note \"继续推进并同步真实进展\""
            )
            lines.append(
                f"  next: python3 scripts/runtime/main_ops.py continuity --session-key '{task.session_key}'"
            )
            lines.append(
                f"  lanes: python3 scripts/runtime/main_ops.py lanes --json"
            )

    if manual_review:
        lines.extend(["", "## Needs Manual Review", ""])
        for finding in manual_review:
            task = main_tasks_by_id.get(finding.task_id)
            lines.append(
                f"- {finding.task_id} | {finding.status} | label={task.task_label if task else ''} | silence={finding.silence_seconds}s | notify={finding.should_notify} | reason={finding.reason}"
            )

    if not_recommended:
        lines.extend(["", "## Not Recommended For Auto Resume", ""])
        for task in not_recommended:
            lines.append(
                f"- {task.task_id} | block_reason={task.block_reason} | updated_at={task.updated_at}"
            )
            lines.append(
                f"  inspect: python3 scripts/runtime/main_ops.py show {task.task_id}"
            )

    if session_summary:
        lines.extend(["", "## By Session", ""])
        for session_key, bucket in sorted(
            session_summary.items(),
            key=lambda item: (
                -(
                    int(item[1]["auto_resumable_count"])
                    + int(item[1]["manual_review_count"])
                    + int(item[1]["not_recommended_count"])
                ),
                item[0],
            ),
        ):
            unique_labels = sorted({str(label) for label in bucket["task_labels"] if str(label).strip()})
            lines.append(
                f"- {session_key} | auto_resumable={bucket['auto_resumable_count']} | manual_review={bucket['manual_review_count']} | not_recommended={bucket['not_recommended_count']} | planning_anomaly={bucket['planning_anomaly_count']} | overdue_followup={bucket['overdue_followup_count']}"
            )
            status_counts = bucket.get("user_facing_status_counts")
            if isinstance(status_counts, dict) and status_counts:
                ordered = sorted(status_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))
                lines.append(
                    "  user_statuses: "
                    + ", ".join(f"{label}:{count}" for label, count in ordered)
                )
            if unique_labels:
                lines.append(f"  labels: {', '.join(unique_labels[:3])}")

    lines.extend(["", "## Execution Plan", ""])
    for step in execution_plan["steps"]:
        lines.append(f"- {step}")
    if execution_plan["commands"]:
        lines.append("- suggested_commands:")
        for command in execution_plan["commands"]:
            lines.append(f"  {command}")

    if not auto_resumable and not manual_review and not not_recommended:
        lines.extend(["", "## Status", "", "- No continuity risk is currently detected for main."])

    return "\n".join(lines) + "\n"


def get_main_continuity_summary(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
    session_key: Optional[str] = None,
) -> dict[str, object]:
    resolved_paths = _resolve_paths(config_path, paths=paths)
    runtime_config = load_task_system_config(config_path=config_path)
    store = TaskStore(paths=resolved_paths)
    normalized_session_key = str(session_key or "").strip() or None
    main_tasks = store.find_inflight_tasks(agent_id="main")
    if normalized_session_key:
        main_tasks = [task for task in main_tasks if task.session_key == normalized_session_key]
    inflight_statuses = {
        str(status["task_id"]): status
        for status in list_inflight_statuses(config_path=config_path, paths=resolved_paths)
        if str(status.get("agent_id")) == "main"
        and (normalized_session_key is None or str(status.get("session_key")) == normalized_session_key)
    }
    queue_like_tasks = [task for task in main_tasks if task.status in {"received", "queued", "running", "paused"}]
    execution_strategy = _summarize_agent_execution_strategy("main", queue_like_tasks)
    blocked_without_watchdog = [
        task
        for task in main_tasks
        if task.status == "blocked" and not str(task.meta.get("watchdog_escalation") or "").strip()
    ]
    watchdog_blocked = [
        task
        for task in main_tasks
        if task.status == "blocked" and str(task.meta.get("watchdog_escalation") or "").strip()
    ]
    monitored_tasks = [
        task
        for task in main_tasks
        if task.status in {"received", "queued", "running"}
    ]
    main_tasks_by_id = {task.task_id: task for task in main_tasks}
    monitor = runtime_config.agent_config("main").silence_monitor
    continuity_findings = (
        scan_tasks(
            monitored_tasks,
            timeout_seconds=monitor.silent_timeout_seconds,
            resend_interval_seconds=monitor.resend_interval_seconds,
        )
        if monitor.enabled
        else []
    )
    overdue_findings = [finding for finding in continuity_findings if finding.silence_seconds > monitor.silent_timeout_seconds]
    auto_resumable = sorted(watchdog_blocked, key=lambda item: item.updated_at, reverse=True)
    auto_resumable_ids = {task.task_id for task in auto_resumable}
    manual_review = sorted(
        [finding for finding in overdue_findings if finding.task_id not in auto_resumable_ids],
        key=lambda item: (-item.silence_seconds, item.task_id),
    )
    not_recommended = sorted(
        blocked_without_watchdog,
        key=lambda item: item.updated_at,
        reverse=True,
    )
    session_summary: dict[str, dict[str, object]] = {}

    def ensure_session(summary_session_key: str) -> dict[str, object]:
        bucket = session_summary.get(summary_session_key)
        if bucket is None:
            bucket = {
                "session_key": summary_session_key,
                "auto_resumable_count": 0,
                "manual_review_count": 0,
                "not_recommended_count": 0,
                "planning_anomaly_count": 0,
                "overdue_followup_count": 0,
                "task_labels": [],
                "user_facing_status_counts": {},
                "user_facing_status_code_counts": {},
            }
            session_summary[summary_session_key] = bucket
        return bucket

    for task in auto_resumable:
        bucket = ensure_session(task.session_key)
        bucket["auto_resumable_count"] = int(bucket["auto_resumable_count"]) + 1
        bucket["task_labels"].append(task.task_label)
    for finding in manual_review:
        task = main_tasks_by_id.get(finding.task_id)
        bucket = ensure_session(finding.session_key)
        bucket["manual_review_count"] = int(bucket["manual_review_count"]) + 1
        if task:
            bucket["task_labels"].append(task.task_label)
    for task in not_recommended:
        bucket = ensure_session(task.session_key)
        bucket["not_recommended_count"] = int(bucket["not_recommended_count"]) + 1
        bucket["task_labels"].append(task.task_label)
    for task in main_tasks:
        status_entry = inflight_statuses.get(task.task_id)
        planning = status_entry.get("planning") if isinstance(status_entry, dict) and isinstance(status_entry.get("planning"), dict) else {}
        if planning.get("anomaly") or planning.get("overdue_followup"):
            bucket = ensure_session(task.session_key)
            bucket["task_labels"].append(task.task_label)

    for task in main_tasks:
        bucket = session_summary.get(task.session_key)
        if bucket is None:
            continue
        status_entry = inflight_statuses.get(task.task_id)
        if status_entry:
            projection = _task_user_facing_projection(status_entry)
            label_counts = bucket["user_facing_status_counts"]
            if isinstance(label_counts, dict):
                label = projection["label"]
                label_counts[label] = int(label_counts.get(label, 0)) + 1
            code_counts = bucket["user_facing_status_code_counts"]
            if isinstance(code_counts, dict):
                code = projection["code"]
                code_counts[code] = int(code_counts.get(code, 0)) + 1
            planning = status_entry.get("planning") if isinstance(status_entry.get("planning"), dict) else {}
            if planning.get("anomaly"):
                bucket["planning_anomaly_count"] = int(bucket["planning_anomaly_count"]) + 1
            if planning.get("overdue_followup"):
                bucket["overdue_followup_count"] = int(bucket["overdue_followup_count"]) + 1

    suggested_next_commands = [
        "python3 scripts/runtime/main_ops.py lanes --json",
        *(
            [
                f"python3 scripts/runtime/main_ops.py continuity --session-key '{normalized_session_key}'"
            ]
            if normalized_session_key
            else []
        ),
    ]
    auto_resume_command_parts = [
        "python3 scripts/runtime/main_ops.py continuity --resume-watchdog-blocked",
        *([f"--session-key '{normalized_session_key}'"] if normalized_session_key else []),
        *(["--respect-execution-advice"] if str(execution_strategy["execution_recommendation"]) == "serial" else []),
    ]
    auto_resume_if_safe_command = " ".join(
        [
            "python3 scripts/runtime/main_ops.py continuity --auto-resume-if-safe",
            *([f"--session-key '{normalized_session_key}'"] if normalized_session_key else []),
        ]
    )
    auto_resume_ready = len(auto_resumable) > 0
    auto_resume_blockers: list[str] = []
    if manual_review:
        auto_resume_blockers.append("manual-review-present")
    if not_recommended:
        auto_resume_blockers.append("not-recommended-present")
    auto_resume_safe_to_apply = auto_resume_ready and not auto_resume_blockers
    auto_resume_mode = (
        "respect-execution-advice"
        if auto_resume_ready and str(execution_strategy["execution_recommendation"]) == "serial"
        else "direct"
        if auto_resume_ready
        else "none"
    )
    auto_resume_apply_command = " ".join(auto_resume_command_parts) if auto_resume_ready else None
    auto_resume_preview_command = (
        " ".join([*auto_resume_command_parts, "--dry-run"])
        if auto_resume_ready
        else None
    )
    execution_plan = _build_continuity_execution_plan(
        session_filter=normalized_session_key or "all",
        execution_recommendation=str(execution_strategy["execution_recommendation"]),
        auto_resumable_task_count=len(auto_resumable),
        suggested_next_commands=suggested_next_commands,
    )
    by_session = [
        {
            "session_key": session_entry["session_key"],
            "auto_resumable_count": session_entry["auto_resumable_count"],
            "manual_review_count": session_entry["manual_review_count"],
            "not_recommended_count": session_entry["not_recommended_count"],
            "planning_anomaly_count": session_entry["planning_anomaly_count"],
            "overdue_followup_count": session_entry["overdue_followup_count"],
            "task_labels": sorted({str(label) for label in session_entry["task_labels"] if str(label).strip()}),
            "user_facing_status_counts": dict(
                sorted(
                    (session_entry.get("user_facing_status_counts") or {}).items(),
                    key=lambda item: (-int(item[1]), str(item[0])),
                )
            ),
            "user_facing_status_code_counts": dict(
                sorted(
                    (session_entry.get("user_facing_status_code_counts") or {}).items(),
                    key=lambda item: (-int(item[1]), str(item[0])),
                )
            ),
        }
        for session_entry in sorted(
            session_summary.values(),
            key=lambda item: (
                -(
                    int(item["auto_resumable_count"])
                    + int(item["manual_review_count"])
                    + int(item["not_recommended_count"])
                    + int(item["planning_anomaly_count"])
                    + int(item["overdue_followup_count"])
                ),
                str(item["session_key"]),
            ),
        )
    ]
    top_risk_session = None
    if by_session:
        top_session = by_session[0]
        top_risk_session = {
            "session_key": top_session["session_key"],
            "auto_resumable_count": top_session["auto_resumable_count"],
            "manual_review_count": top_session["manual_review_count"],
            "not_recommended_count": top_session["not_recommended_count"],
            "planning_anomaly_count": top_session["planning_anomaly_count"],
            "overdue_followup_count": top_session["overdue_followup_count"],
            "task_labels": top_session["task_labels"],
            "user_facing_status_counts": top_session["user_facing_status_counts"],
            "user_facing_status_code_counts": top_session["user_facing_status_code_counts"],
            "next_command": (
                f"python3 scripts/runtime/main_ops.py continuity --session-key '{top_session['session_key']}'"
            ),
        }
    primary_action = {
        "kind": "none",
        "summary": "No immediate continuity action is needed.",
        "command": None,
        "session_key": None,
    }
    if auto_resume_safe_to_apply and auto_resume_apply_command:
        primary_action = {
            "kind": "apply-auto-resume",
            "summary": "Apply the watchdog auto-resume plan now.",
            "command": auto_resume_if_safe_command,
            "session_key": normalized_session_key or (top_risk_session["session_key"] if top_risk_session else None),
        }
    elif auto_resume_ready and auto_resume_preview_command:
        primary_action = {
            "kind": "preview-auto-resume",
            "summary": "Preview watchdog auto-resume candidates first.",
            "command": auto_resume_preview_command,
            "session_key": normalized_session_key or (top_risk_session["session_key"] if top_risk_session else None),
        }
    elif top_risk_session:
        primary_action = {
            "kind": "followup-session",
            "summary": f"Inspect continuity for session {top_risk_session['session_key']} first.",
            "command": top_risk_session["next_command"],
            "session_key": top_risk_session["session_key"],
        }
    runbook = {
        "status": "warn" if top_risk_session else "ok",
        "primary_action": primary_action,
        "steps": [
            primary_action["summary"],
            *(
                ["If the dry-run looks right, apply the auto-resume plan next."]
                if primary_action["kind"] == "preview-auto-resume" and auto_resume_apply_command
                else []
            ),
            *(
                [f"Auto-resume blockers are present: {', '.join(auto_resume_blockers)}."]
                if auto_resume_blockers
                else []
            ),
            "Review the suggested commands in order if the first action does not resolve the highest-risk session.",
        ],
        "commands": [
            *([primary_action["command"]] if primary_action["command"] else []),
            *(
                [auto_resume_apply_command]
                if primary_action["kind"] == "preview-auto-resume"
                and auto_resume_apply_command
                and auto_resume_apply_command != primary_action["command"]
                else []
            ),
            *[command for command in suggested_next_commands if command != primary_action["command"]],
        ],
    }

    if auto_resume_safe_to_apply:
        continuity_text = "检测到可直接执行的 continuity auto-resume 计划。"
    elif auto_resume_ready:
        continuity_text = "检测到 continuity 风险，建议先预览 auto-resume 候选。"
    elif top_risk_session:
        continuity_text = f"检测到 continuity 风险，建议先跟进 session {top_risk_session['session_key']}。"
    else:
        continuity_text = "当前没有需要立即处理的 continuity 风险。"

    planning_anomaly_task_count = sum(int(entry["planning_anomaly_count"]) for entry in by_session)
    overdue_planned_followup_count = sum(int(entry["overdue_followup_count"]) for entry in by_session)

    return {
        "session_filter": normalized_session_key or "all",
        "silence_monitor_enabled": monitor.enabled,
        "silent_timeout_seconds": monitor.silent_timeout_seconds,
        "resend_interval_seconds": monitor.resend_interval_seconds,
        "execution_recommendation": execution_strategy["execution_recommendation"],
        "execution_reason": execution_strategy["execution_reason"],
        "active_monitored_task_count": len(monitored_tasks),
        "overdue_monitored_task_count": len(overdue_findings),
        "watchdog_blocked_task_count": len(watchdog_blocked),
        "auto_resumable_task_count": len(auto_resumable),
        "manual_review_task_count": len(manual_review),
        "not_recommended_auto_resume_count": len(not_recommended),
        "planning_anomaly_task_count": planning_anomaly_task_count,
        "overdue_planned_followup_count": overdue_planned_followup_count,
        "auto_resumable": [
            {
                "task_id": task.task_id,
                "session_key": task.session_key,
                "task_label": task.task_label,
                "watchdog_escalation": str(task.meta.get("watchdog_escalation") or ""),
                "updated_at": task.updated_at,
            }
            for task in auto_resumable
        ],
        "manual_review": [
            {
                "task_id": finding.task_id,
                "session_key": finding.session_key,
                "status": finding.status,
                "task_label": main_tasks_by_id.get(finding.task_id).task_label if main_tasks_by_id.get(finding.task_id) else "",
                "silence_seconds": finding.silence_seconds,
                "should_notify": finding.should_notify,
                "reason": finding.reason,
            }
            for finding in manual_review
        ],
        "not_recommended": [
            {
                "task_id": task.task_id,
                "session_key": task.session_key,
                "task_label": task.task_label,
                "block_reason": task.block_reason,
                "updated_at": task.updated_at,
            }
            for task in not_recommended
        ],
        "by_session": by_session,
        "top_risk_session": top_risk_session,
        "focus_session_key": top_risk_session["session_key"] if top_risk_session else None,
        "auto_resume_ready": auto_resume_ready,
        "auto_resume_safe_to_apply": auto_resume_safe_to_apply,
        "auto_resume_blockers": auto_resume_blockers,
        "auto_resume_mode": auto_resume_mode,
        "auto_resume_preview_command": auto_resume_preview_command,
        "auto_resume_apply_command": auto_resume_apply_command,
        "primary_action_kind": primary_action["kind"],
        "primary_action_command": primary_action["command"],
        "runbook_status": runbook["status"],
        "requires_action": bool(top_risk_session),
        "primary_action": primary_action,
        "runbook": runbook,
        "suggested_next_commands": suggested_next_commands,
        "execution_plan": execution_plan,
        "control_plane_message": {
            "schema": "openclaw.task-system.control-plane.v1",
            "kind": "continuity-summary",
            "event_name": "continuity-summary",
            "priority": "p1-task-management",
            "text": continuity_text,
            "session_key": normalized_session_key or (top_risk_session["session_key"] if top_risk_session else None),
            "metadata": {
                "auto_resume_ready": auto_resume_ready,
                "auto_resume_safe_to_apply": auto_resume_safe_to_apply,
                "primary_action_kind": primary_action["kind"],
                "primary_action_command": primary_action["command"],
                "top_risk_session_key": top_risk_session["session_key"] if top_risk_session else None,
                "top_risk_session_user_status_code_counts": (
                    top_risk_session["user_facing_status_code_counts"] if top_risk_session else {}
                ),
                "top_risk_session_user_status_counts": (
                    top_risk_session["user_facing_status_counts"] if top_risk_session else {}
                ),
            },
        },
    }


def resume_watchdog_blocked_main_tasks(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
    session_key: Optional[str] = None,
    limit: Optional[int] = None,
    note: Optional[str] = None,
    respect_execution_advice: bool = False,
    dry_run: bool = False,
) -> dict[str, object]:
    resolved_paths = _resolve_paths(config_path, paths=paths)
    store = TaskStore(paths=resolved_paths)
    normalized_session_key = str(session_key or "").strip() or None
    watchdog_blocked = [
        task
        for task in store.find_inflight_tasks(agent_id="main")
        if task.status == "blocked"
        and str(task.meta.get("watchdog_escalation") or "").strip()
        and (normalized_session_key is None or task.session_key == normalized_session_key)
    ]
    candidate_tasks = list(watchdog_blocked)
    pre_resume_tasks = [
        task
        for task in store.find_inflight_tasks(agent_id="main")
        if task.status in {"received", "queued", "running", "paused"}
        and (normalized_session_key is None or task.session_key == normalized_session_key)
    ]
    pre_resume_strategy = _summarize_agent_execution_strategy("main", pre_resume_tasks)
    skipped: list[dict[str, object]] = []
    if respect_execution_advice and pre_resume_strategy["execution_recommendation"] == "serial":
        running_sessions = {
            str(task.session_key)
            for task in pre_resume_tasks
            if str(task.status) == STATUS_RUNNING
        }
        if running_sessions:
            candidate_tasks = [task for task in candidate_tasks if task.session_key in running_sessions]
            for task in watchdog_blocked:
                if task in candidate_tasks:
                    continue
                skipped.append(
                    {
                        "task_id": task.task_id,
                        "session_key": task.session_key,
                        "task_label": task.task_label,
                        "reason": "blocked-by-serial-execution-advice",
                    }
                )
    selected = sorted(
        candidate_tasks,
        key=lambda item: (
            str(item.updated_at or item.created_at or ""),
            str(item.task_id),
        ),
    )
    if limit is not None:
        selected = selected[: max(0, int(limit))]
    resume_note = note or "继续推进并同步真实进展"
    resumed: list[dict[str, object]] = []
    post_resume_status_counts: dict[str, int] = {}
    resumed_session_keys: set[str] = set()
    for task in selected:
        if dry_run:
            target_status = STATUS_QUEUED if pre_resume_strategy["execution_recommendation"] == "serial" else STATUS_RUNNING
            updated = task
            resumed_session_keys.add(task.session_key)
            post_resume_status_counts[target_status] = post_resume_status_counts.get(target_status, 0) + 1
            resumed.append(
                {
                    "task_id": task.task_id,
                    "status": target_status,
                    "session_key": task.session_key,
                    "task_label": task.task_label,
                    "watchdog_escalation": str(task.meta.get("watchdog_escalation") or ""),
                    "dry_run": True,
                }
            )
            continue
        updated = resume_main_task(task.task_id, progress_note=resume_note, paths=resolved_paths)
        resumed_session_keys.add(updated.session_key)
        post_resume_status_counts[updated.status] = post_resume_status_counts.get(updated.status, 0) + 1
        resumed.append(
            {
                "task_id": updated.task_id,
                "status": updated.status,
                "session_key": updated.session_key,
                "task_label": updated.task_label,
                "watchdog_escalation": str(task.meta.get("watchdog_escalation") or ""),
            }
        )
    if dry_run:
        post_resume_tasks = pre_resume_tasks
        post_resume_strategy = pre_resume_strategy
    else:
        post_resume_tasks = [
            task
            for task in store.find_inflight_tasks(agent_id="main")
            if task.status in {"received", "queued", "running", "paused"}
            and (normalized_session_key is None or task.session_key == normalized_session_key)
        ]
        post_resume_strategy = _summarize_agent_execution_strategy("main", post_resume_tasks)
    post_resume_session_summaries: list[dict[str, object]] = []
    for resumed_session_key in sorted(resumed_session_keys):
        session_tasks = [task for task in post_resume_tasks if task.session_key == resumed_session_key]
        if not session_tasks:
            post_resume_session_summaries.append(
                {
                    "session_key": resumed_session_key,
                    "followup_state": "settled",
                    "followup_state_reason": "no-active-tasks-after-resume",
                    "followup_priority": None,
                    "active_task_count": 0,
                    "status_counts": {},
                    "next_command": f"python3 scripts/runtime/main_ops.py continuity --session-key '{resumed_session_key}'",
                }
            )
            continue
        status_counts: dict[str, int] = {}
        for task in session_tasks:
            status_counts[str(task.status)] = status_counts.get(str(task.status), 0) + 1
        post_resume_session_summaries.append(
            {
                "session_key": resumed_session_key,
                "followup_state": "needs-followup",
                "followup_state_reason": "active-tasks-remain-after-resume",
                "followup_priority": None,
                "active_task_count": len(session_tasks),
                "status_counts": status_counts,
                "task_labels": sorted({str(task.task_label) for task in session_tasks if str(task.task_label).strip()}),
                "next_command": f"python3 scripts/runtime/main_ops.py continuity --session-key '{resumed_session_key}'",
            }
        )
    prioritized_followups = sorted(
        [
            entry
            for entry in post_resume_session_summaries
            if entry.get("followup_state") == "needs-followup"
        ],
        key=lambda entry: (
            -int((entry.get("status_counts") or {}).get("running", 0)),
            -int((entry.get("status_counts") or {}).get("queued", 0)),
            -int((entry.get("status_counts") or {}).get("paused", 0)),
            -int(entry.get("active_task_count", 0)),
            str(entry.get("session_key") or ""),
        ),
    )
    for index, entry in enumerate(prioritized_followups, start=1):
        entry["followup_priority"] = index
    top_followup_session = None
    if prioritized_followups:
        top_entry = prioritized_followups[0]
        top_followup_session = {
            "session_key": top_entry["session_key"],
            "followup_priority": top_entry["followup_priority"],
            "active_task_count": top_entry["active_task_count"],
            "status_counts": top_entry["status_counts"],
            "next_command": top_entry["next_command"],
        }
    next_followup_summary = None
    if top_followup_session:
        next_followup_summary = get_main_continuity_summary(
            config_path=config_path,
            paths=resolved_paths,
            session_key=top_followup_session["session_key"],
        )
        next_followup_summary["focus_session_key"] = top_followup_session["session_key"]
    settled_session_count = len(
        [entry for entry in post_resume_session_summaries if entry.get("followup_state") == "settled"]
    )
    needs_followup_session_count = len(
        [entry for entry in post_resume_session_summaries if entry.get("followup_state") == "needs-followup"]
    )
    closure_state = "no-resume-targets"
    closure_state_reason = "no-watchdog-blocked-main-tasks-were-resumed"
    closure_hint = "No continuity resume action is pending right now."
    closure_hint_command = None
    if resumed_session_keys:
        if needs_followup_session_count == 0:
            closure_state = "settled"
            closure_state_reason = "all-resumed-sessions-are-settled"
            closure_hint = "All resumed sessions are settled; a quick lanes check is enough."
            closure_hint_command = "python3 scripts/runtime/main_ops.py lanes --json"
        else:
            closure_state = "needs-followup"
            closure_state_reason = "resumed-sessions-still-have-active-tasks"
            if top_followup_session:
                closure_hint = f"Follow up session {top_followup_session['session_key']} next."
                closure_hint_command = str(top_followup_session["next_command"])
    closure_complete = closure_state in {"settled", "no-resume-targets"}
    post_resume_runbook = {
        "status": closure_state,
        "primary_action": {
            "kind": (
                "followup-session"
                if closure_state == "needs-followup" and top_followup_session
                else "review-lanes"
                if closure_state == "settled"
                else "none"
            ),
            "summary": closure_hint,
            "command": closure_hint_command,
            "session_key": top_followup_session["session_key"] if top_followup_session else None,
        },
        "steps": [
            closure_hint,
            "Review the suggested commands in order if the resumed sessions are not fully settled yet.",
        ],
        "commands": [
            *( [closure_hint_command] if closure_hint_command else [] ),
            *[
                command
                for command in [
                    "python3 scripts/runtime/main_ops.py lanes --json",
                    *[
                        f"python3 scripts/runtime/main_ops.py continuity --session-key '{resumed_session_key}'"
                        for resumed_session_key in sorted(resumed_session_keys)
                    ],
                ]
                if command != closure_hint_command
            ],
        ],
    }
    return {
        "action": "resume-watchdog-blocked-main-tasks",
        "session_filter": normalized_session_key or "all",
        "candidate_count": len(watchdog_blocked),
        "eligible_count": len(candidate_tasks),
        "resumed_count": len(resumed),
        "limit": limit,
        "note": resume_note,
        "respect_execution_advice": respect_execution_advice,
        "dry_run": dry_run,
        "pre_resume_execution_recommendation": pre_resume_strategy["execution_recommendation"],
        "closure_state": closure_state,
        "closure_state_reason": closure_state_reason,
        "closure_complete": closure_complete,
        "closure_hint": closure_hint,
        "closure_hint_command": closure_hint_command,
        "focus_session_key": top_followup_session["session_key"] if top_followup_session else None,
        "primary_action_kind": post_resume_runbook["primary_action"]["kind"],
        "primary_action_command": post_resume_runbook["primary_action"]["command"],
        "runbook_status": post_resume_runbook["status"],
        "requires_action": closure_state == "needs-followup",
        "next_followup_summary": next_followup_summary,
        "primary_action": post_resume_runbook["primary_action"],
        "runbook": post_resume_runbook,
        "post_resume_summary": {
            "resumed_session_count": len(resumed_session_keys),
            "status_counts": post_resume_status_counts,
            "execution_recommendation": post_resume_strategy["execution_recommendation"],
            "execution_reason": post_resume_strategy["execution_reason"],
            "closure_state": closure_state,
            "closure_state_reason": closure_state_reason,
            "closure_complete": closure_complete,
            "closure_hint": closure_hint,
            "closure_hint_command": closure_hint_command,
            "primary_action": {
                "kind": (
                    "followup-session"
                    if closure_state == "needs-followup" and top_followup_session
                    else "review-lanes"
                    if closure_state == "settled"
                    else "none"
                ),
                "summary": closure_hint,
                "command": closure_hint_command,
                "session_key": top_followup_session["session_key"] if top_followup_session else None,
            },
            "runbook": post_resume_runbook,
            "sessions": post_resume_session_summaries,
            "settled_session_count": settled_session_count,
            "needs_followup_session_count": needs_followup_session_count,
            "followup_priorities": [
                {
                    "session_key": entry["session_key"],
                    "followup_priority": entry["followup_priority"],
                    "active_task_count": entry["active_task_count"],
                    "status_counts": entry["status_counts"],
                    "next_command": entry["next_command"],
                }
                for entry in prioritized_followups
            ],
            "top_followup_session": top_followup_session,
            "next_followup_summary": next_followup_summary,
        },
        "skipped": skipped,
        "suggested_next_commands": [
            "python3 scripts/runtime/main_ops.py lanes --json",
            *[
                f"python3 scripts/runtime/main_ops.py continuity --session-key '{resumed_session_key}'"
                for resumed_session_key in sorted(resumed_session_keys)
            ],
        ],
        "resumed": resumed,
    }


def auto_resume_watchdog_blocked_main_tasks_if_safe(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
    session_key: Optional[str] = None,
    limit: Optional[int] = None,
    note: Optional[str] = None,
    dry_run: bool = False,
) -> dict[str, object]:
    continuity = get_main_continuity_summary(
        config_path=config_path,
        paths=paths,
        session_key=session_key,
    )
    safe_to_apply = bool(continuity.get("auto_resume_safe_to_apply"))
    ready = bool(continuity.get("auto_resume_ready"))
    blockers = [
        str(item)
        for item in continuity.get("auto_resume_blockers", [])
        if str(item).strip()
    ]
    result: dict[str, object] = {
        "action": "auto-resume-watchdog-blocked-main-tasks-if-safe",
        "session_filter": str(continuity.get("session_filter") or "all"),
        "safe_to_apply": safe_to_apply,
        "auto_resume_ready": ready,
        "auto_resume_mode": str(continuity.get("auto_resume_mode") or "none"),
        "auto_resume_blockers": blockers,
        "dry_run": dry_run,
        "would_apply": safe_to_apply and ready,
        "continuity": continuity,
        "focus_session_key": continuity.get("focus_session_key"),
        "primary_action_kind": continuity.get("primary_action_kind"),
        "primary_action_command": continuity.get("primary_action_command"),
        "runbook_status": continuity.get("runbook_status"),
        "requires_action": bool(continuity.get("requires_action")),
        "primary_action": continuity.get("primary_action"),
        "runbook": continuity.get("runbook"),
        "suggested_next_commands": list(continuity.get("suggested_next_commands", [])),
    }
    if not ready:
        result["status"] = "noop"
        result["reason"] = "no-auto-resumable-tasks"
        result["closure_complete"] = True
        result["closure_state"] = "no-resume-targets"
        result["closure_state_reason"] = "no-auto-resumable-tasks"
        result["closure_hint"] = "No auto-resume action is pending right now."
        result["closure_hint_command"] = None
        result["next_followup_summary"] = None
        return result
    if not safe_to_apply:
        result["status"] = "skipped"
        result["reason"] = "auto-resume-blocked"
        result["closure_complete"] = False
        result["closure_state"] = "blocked"
        result["closure_state_reason"] = "auto-resume-blockers-present"
        result["closure_hint"] = str(
            (result.get("primary_action") or {}).get("summary")
            or "Review continuity blockers before auto-resume."
        )
        result["closure_hint_command"] = result.get("primary_action_command")
        result["next_followup_summary"] = None
        return result

    respect_execution_advice = str(continuity.get("auto_resume_mode") or "") == "respect-execution-advice"
    resume_result = resume_watchdog_blocked_main_tasks(
        config_path=config_path,
        paths=paths,
        session_key=session_key,
        limit=limit,
        note=note,
        respect_execution_advice=respect_execution_advice,
        dry_run=dry_run,
    )
    result["status"] = "applied" if not dry_run else "previewed"
    result["respect_execution_advice"] = respect_execution_advice
    result["resume_result"] = resume_result
    result["closure_complete"] = bool(resume_result.get("closure_complete"))
    result["closure_state"] = resume_result.get("closure_state")
    result["closure_state_reason"] = resume_result.get("closure_state_reason")
    result["closure_hint"] = resume_result.get("closure_hint")
    result["closure_hint_command"] = resume_result.get("closure_hint_command")
    result["primary_action_kind"] = str(resume_result.get("primary_action_kind") or "none")
    result["primary_action_command"] = resume_result.get("primary_action_command")
    result["focus_session_key"] = resume_result.get("focus_session_key")
    result["runbook_status"] = resume_result.get("runbook_status")
    result["requires_action"] = bool(resume_result.get("requires_action"))
    result["primary_action"] = resume_result.get("primary_action")
    result["runbook"] = resume_result.get("runbook")
    result["suggested_next_commands"] = list(resume_result.get("suggested_next_commands", []))
    result["next_followup_summary"] = resume_result.get("next_followup_summary")
    return result


def render_auto_resume_if_safe_result(result: dict[str, object]) -> str:
    lines = [
        "# Auto Resume",
        "",
        f"- session_filter: {result.get('session_filter')}",
        f"- status: {result.get('status', 'unknown')}",
        f"- safe_to_apply: {result.get('safe_to_apply')}",
        f"- auto_resume_ready: {result.get('auto_resume_ready')}",
        f"- auto_resume_mode: {result.get('auto_resume_mode')}",
        f"- dry_run: {result.get('dry_run')}",
    ]
    blockers = result.get("auto_resume_blockers", [])
    if isinstance(blockers, list) and blockers:
        lines.append(f"- auto_resume_blockers: {', '.join(str(item) for item in blockers)}")
    reason = result.get("reason")
    if reason:
        lines.append(f"- reason: {reason}")
    if "closure_complete" in result:
        lines.append(f"- closure_complete: {result.get('closure_complete')}")
    if "closure_state" in result:
        lines.append(f"- closure_state: {result.get('closure_state')}")
    if "closure_state_reason" in result:
        lines.append(f"- closure_state_reason: {result.get('closure_state_reason')}")
    if "closure_hint" in result:
        lines.append(f"- closure_hint: {result.get('closure_hint')}")
    if "closure_hint_command" in result:
        lines.append(f"- closure_hint_command: {result.get('closure_hint_command') or 'none'}")
    if result.get("focus_session_key"):
        lines.append(f"- focus_session_key: {result.get('focus_session_key')}")
    if result.get("primary_action_kind"):
        lines.append(f"- primary_action_kind: {result.get('primary_action_kind')}")
    if result.get("primary_action_command"):
        lines.append(f"- next_command: {result.get('primary_action_command')}")

    next_followup_summary = result.get("next_followup_summary")
    if isinstance(next_followup_summary, dict):
        lines.extend(["", "## Next Follow-up", ""])
        lines.append(f"- session_filter: {next_followup_summary.get('session_filter')}")
        lines.append(f"- focus_session_key: {next_followup_summary.get('focus_session_key')}")
        if next_followup_summary.get("primary_action_kind"):
            lines.append(f"- primary_action_kind: {next_followup_summary.get('primary_action_kind')}")
        if next_followup_summary.get("primary_action_command"):
            lines.append(f"- next_command: {next_followup_summary.get('primary_action_command')}")
        if next_followup_summary.get("auto_resume_ready") is not None:
            lines.append(f"- auto_resume_ready: {next_followup_summary.get('auto_resume_ready')}")

    suggested_next_commands = result.get("suggested_next_commands", [])
    if isinstance(suggested_next_commands, list) and suggested_next_commands:
        lines.extend(["", "## Suggested Commands", ""])
        for command in suggested_next_commands:
            lines.append(f"- {command}")

    runbook = result.get("runbook")
    if isinstance(runbook, dict):
        lines.extend(["", "## Runbook", ""])
        for step in runbook.get("steps", []):
            lines.append(f"- {step}")
        commands = runbook.get("commands", [])
        if isinstance(commands, list) and commands:
            lines.append("- commands:")
            for command in commands:
                lines.append(f"  {command}")
    return "\n".join(lines) + "\n"


def render_resume_watchdog_blocked_result(result: dict[str, object]) -> str:
    post_resume_summary = result.get("post_resume_summary", {})
    sessions = post_resume_summary.get("sessions", []) if isinstance(post_resume_summary, dict) else []
    lines = [
        "# Continuity Resume",
        "",
        f"- session_filter: {result.get('session_filter')}",
        f"- candidate_count: {result.get('candidate_count')}",
        f"- eligible_count: {result.get('eligible_count')}",
        f"- resumed_count: {result.get('resumed_count')}",
        f"- dry_run: {result.get('dry_run')}",
        f"- respect_execution_advice: {result.get('respect_execution_advice')}",
    ]
    if isinstance(post_resume_summary, dict):
        lines.extend(
            [
                f"- settled_session_count: {post_resume_summary.get('settled_session_count', 0)}",
                f"- needs_followup_session_count: {post_resume_summary.get('needs_followup_session_count', 0)}",
                f"- execution_recommendation: {post_resume_summary.get('execution_recommendation', 'unknown')}",
                f"- closure_state: {post_resume_summary.get('closure_state', 'unknown')}",
                f"- closure_state_reason: {post_resume_summary.get('closure_state_reason', 'unknown')}",
                f"- closure_hint: {post_resume_summary.get('closure_hint', 'unknown')}",
                f"- closure_hint_command: {post_resume_summary.get('closure_hint_command') or 'none'}",
            ]
        )

    needs_followup = [
        entry for entry in sessions if isinstance(entry, dict) and entry.get("followup_state") == "needs-followup"
    ]
    settled = [entry for entry in sessions if isinstance(entry, dict) and entry.get("followup_state") == "settled"]

    if needs_followup:
        lines.extend(["", "## Follow-up Priorities", ""])
        for entry in needs_followup:
            lines.append(
                f"- P{entry.get('followup_priority') or '?'} | {entry.get('session_key')} | status_counts={json.dumps(entry.get('status_counts', {}), ensure_ascii=False, sort_keys=True)} | reason={entry.get('followup_state_reason', 'unknown')}"
            )
            if entry.get("next_command"):
                lines.append(f"  next: {entry['next_command']}")

        lines.extend(["", "## Needs Follow-up", ""])
        for entry in needs_followup:
            lines.append(
                f"- {entry.get('session_key')} | active_task_count={entry.get('active_task_count', 0)} | status_counts={json.dumps(entry.get('status_counts', {}), ensure_ascii=False, sort_keys=True)} | reason={entry.get('followup_state_reason', 'unknown')}"
            )
            if entry.get("task_labels"):
                lines.append(f"  labels: {', '.join(list(entry['task_labels'])[:3])}")
            if entry.get("next_command"):
                lines.append(f"  next: {entry['next_command']}")

    if settled:
        lines.extend(["", "## Settled", ""])
        for entry in settled:
            lines.append(
                f"- {entry.get('session_key')} | active_task_count={entry.get('active_task_count', 0)} | reason={entry.get('followup_state_reason', 'unknown')}"
            )
            if entry.get("next_command"):
                lines.append(f"  next: {entry['next_command']}")

    skipped = result.get("skipped", [])
    if isinstance(skipped, list) and skipped:
        lines.extend(["", "## Skipped", ""])
        for entry in skipped:
            if not isinstance(entry, dict):
                continue
            lines.append(
                f"- {entry.get('task_id')} | session_key={entry.get('session_key')} | reason={entry.get('reason')}"
            )

    suggested_next_commands = result.get("suggested_next_commands", [])
    if isinstance(suggested_next_commands, list) and suggested_next_commands:
        lines.extend(["", "## Suggested Commands", ""])
        for command in suggested_next_commands:
            lines.append(f"- {command}")

    if isinstance(post_resume_summary, dict):
        runbook = post_resume_summary.get("runbook")
        if not isinstance(runbook, dict):
            closure_hint = post_resume_summary.get("closure_hint")
            closure_hint_command = post_resume_summary.get("closure_hint_command")
            runbook = {
                "status": post_resume_summary.get("closure_state", "unknown"),
                "primary_action": post_resume_summary.get("primary_action", {}),
                "steps": [
                    closure_hint or "Review resumed session state.",
                    "Review the suggested commands in order if the resumed sessions are not fully settled yet.",
                ],
                "commands": [
                    *( [closure_hint_command] if isinstance(closure_hint_command, str) and closure_hint_command.strip() else [] ),
                    *[
                        command
                        for command in result.get("suggested_next_commands", [])
                        if command != closure_hint_command
                    ],
                ],
            }
        if isinstance(runbook, dict):
            lines.extend(["", "## Runbook", ""])
            for step in runbook.get("steps", []):
                lines.append(f"- {step}")
            commands = runbook.get("commands", [])
            if isinstance(commands, list) and commands:
                lines.append("- commands:")
                for command in commands:
                    lines.append(f"  {command}")

    return "\n".join(lines) + "\n"


def render_taskmonitor_status(
    session_key: str,
    *,
    config_path: Optional[Path] = None,
) -> str:
    normalized = str(session_key or "").strip()
    if not normalized:
        raise ValueError("session_key is required")
    enabled = get_taskmonitor_enabled(normalized, config_path=config_path)
    overrides = list_taskmonitor_overrides(config_path=config_path)
    lines = [
        "# TaskMonitor",
        "",
        f"- session_key: {normalized}",
        f"- enabled: {enabled}",
        f"- explicitly_overridden: {normalized in overrides}",
        f"- override_count: {len(overrides)}",
    ]
    return "\n".join(lines) + "\n"


def get_taskmonitor_status(
    session_key: str,
    *,
    config_path: Optional[Path] = None,
) -> dict[str, object]:
    normalized = str(session_key or "").strip()
    if not normalized:
        raise ValueError("session_key is required")
    overrides = list_taskmonitor_overrides(config_path=config_path)
    return {
        "session_key": normalized,
        "enabled": get_taskmonitor_enabled(normalized, config_path=config_path),
        "explicitly_overridden": normalized in overrides,
        "override_count": len(overrides),
    }


def set_taskmonitor_state(
    session_key: str,
    enabled: bool,
    *,
    config_path: Optional[Path] = None,
) -> dict[str, object]:
    normalized = str(session_key or "").strip()
    if not normalized:
        raise ValueError("session_key is required")
    result = set_taskmonitor_enabled(normalized, enabled, config_path=config_path)
    result["override_count"] = len(list_taskmonitor_overrides(config_path=config_path))
    return result


def render_taskmonitor_overrides(
    *,
    config_path: Optional[Path] = None,
) -> str:
    overrides = list_taskmonitor_overrides(config_path=config_path)
    lines = ["# TaskMonitor Overrides", ""]
    if not overrides:
        lines.append("- none")
        return "\n".join(lines) + "\n"
    for session_key, enabled in overrides.items():
        lines.append(f"- {session_key} | enabled={enabled}")
    return "\n".join(lines) + "\n"


def get_taskmonitor_overrides(
    *,
    config_path: Optional[Path] = None,
) -> dict[str, object]:
    overrides = list_taskmonitor_overrides(config_path=config_path)
    return {
        "override_count": len(overrides),
        "overrides": [
            {
                "session_key": session_key,
                "enabled": enabled,
            }
            for session_key, enabled in overrides.items()
        ],
    }


def get_main_producer_contract_summary(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
    session_key: Optional[str] = None,
    channel: Optional[str] = None,
) -> dict[str, object]:
    normalized_session_key = str(session_key or "").strip() or None
    normalized_channel = str(channel or "").strip().lower() or None
    resolved_paths = _resolve_paths(config_path, paths=paths)
    observed_channels = _observed_channels_for_main(config_path=config_path, paths=resolved_paths)
    return build_producer_contract_summary(
        channel=normalized_channel or infer_channel_from_session_key(normalized_session_key),
        session_key=normalized_session_key,
        observed_channels=observed_channels,
    )


def get_main_channel_acceptance_summary(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
    session_key: Optional[str] = None,
    channel: Optional[str] = None,
) -> dict[str, object]:
    normalized_session_key = str(session_key or "").strip() or None
    normalized_channel = str(channel or "").strip().lower() or None
    resolved_paths = _resolve_paths(config_path, paths=paths)
    observed_channels = _observed_channels_for_main(config_path=config_path, paths=resolved_paths)
    return build_channel_acceptance_summary(
        channel=normalized_channel or infer_channel_from_session_key(normalized_session_key),
        session_key=normalized_session_key,
        observed_channels=observed_channels,
    )


def _filter_queue_topology_by_session(
    summary: dict[str, object],
    *,
    session_key: str,
) -> dict[str, object]:
    queues = []
    for queue in summary.get("queues", []):
        sessions = queue.get("sessions", [])
        if any(str(entry.get("session_key") or "") == session_key for entry in sessions):
            queues.append(queue)
    return {
        "queue_statuses": list(summary.get("queue_statuses", [])),
        "queue_count": len(queues),
        "queues": queues,
    }


def _filter_lanes_by_session(
    summary: dict[str, object],
    *,
    session_key: str,
) -> dict[str, object]:
    agents = []
    for agent in summary.get("agents", []):
        shared_sessions = [str(item) for item in agent.get("shared_sessions", [])]
        task_buckets = [
            agent.get("running_tasks", []),
            agent.get("queued_head", []),
            agent.get("paused_tasks", []),
            agent.get("due_paused_tasks", []),
        ]
        matches_task_bucket = any(
            str(task.get("session_key") or "") == session_key
            for bucket in task_buckets
            for task in bucket
            if isinstance(task, dict)
        )
        if session_key in shared_sessions or matches_task_bucket:
            agents.append(agent)
    return {
        "queue_statuses": list(summary.get("queue_statuses", [])),
        "agent_count": len(agents),
        "agents": agents,
    }


def render_main_dashboard(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
    session_key: Optional[str] = None,
    compact: bool = False,
    only_issues: bool = False,
) -> str:
    summary = get_main_dashboard_summary(
        config_path=config_path,
        paths=paths,
        session_key=session_key,
        compact=compact,
        only_issues=only_issues,
    )
    if only_issues:
        issue_summary = summary["issue_summary"]
        lines = [
            "# Main Ops Dashboard",
            "",
            f"- scope: {summary['session_filter']}",
            f"- status: {summary['status']}",
        ]
        if not issue_summary["has_issues"]:
            lines.append("- No issues detected.")
            return "\n".join(lines) + "\n"
        lines.extend(
            [
                f"- main_active_task_count: {summary['health']['main_active_task_count']}",
                f"- main_blocked_task_count: {summary['health']['main_blocked_task_count']}",
                f"- continuity_risk: auto={summary['continuity']['auto_resumable_task_count']} manual={summary['continuity']['manual_review_task_count']}",
                f"- planning_promise_without_task_count: {summary['health']['planning_promise_without_task_count']}",
                f"- planning_overdue_followup_count: {summary['health']['planning_overdue_followup_count']}",
                f"- planning_health_status: {summary['health']['planning_health_status']}",
                f"- planning_health_timeout_count: {summary['health']['planning_health_timeout_count']}",
                f"- plugin_install_drift_status: {summary['plugin_install_drift']['status']}",
                f"- plugin_install_drift_missing_count: {summary['plugin_install_drift']['missing_in_installed_count']}",
                f"- plugin_install_drift_extra_count: {summary['plugin_install_drift']['extra_in_installed_count']}",
                f"- producer_focus_channel: {summary['producer_contract']['focus_channel'] or 'mixed'}",
                f"- producer_mode: {summary['producer_contract']['producer_mode'] or 'mixed'}",
                f"- channel_acceptance_phase_status: {summary['channel_acceptance']['phase_status']}",
                f"- auto_resume_ready: {summary['auto_resume_ready']}",
                f"- auto_resume_safe_to_apply: {summary['auto_resume_safe_to_apply']}",
                f"- auto_resume_command: {summary['auto_resume_command'] or 'none'}",
                f"- top_followup_session: {summary['top_followup_session']['session_key'] if summary['top_followup_session'] else 'none'}",
                f"- action_hint: {summary['action_hint']}",
            ]
        )
        if summary["action_hint_command"]:
            lines.append(f"- action_hint_command: {summary['action_hint_command']}")
        runbook = issue_summary.get("runbook")
        if isinstance(runbook, dict):
            lines.extend(["", "## Runbook", ""])
            for step in runbook.get("steps", []):
                lines.append(f"- {step}")
            commands = runbook.get("commands", [])
            if isinstance(commands, list) and commands:
                lines.append("- commands:")
                for command in commands:
                    lines.append(f"  {command}")
        return "\n".join(lines) + "\n"
    if compact:
        compact_summary = summary["compact_summary"]
        lines = [
            "# Main Ops Dashboard",
            "",
            f"- scope: {compact_summary['scope']}",
            f"- status: {compact_summary['status']}",
            f"- main_active: {compact_summary['main_active_task_count']}",
            f"- blocked: {compact_summary['main_blocked_task_count']}",
            f"- queues: {compact_summary['queue_count']}",
            f"- lanes: {compact_summary['lane_agent_count']}",
            f"- continuity_risk: auto={compact_summary['continuity_auto_resumable_task_count']} manual={compact_summary['continuity_manual_review_task_count']}",
            f"- planning_promise_without_task: {compact_summary['planning_promise_without_task_count']}",
            f"- planning_overdue_followup: {compact_summary['planning_overdue_followup_count']}",
            f"- planning_health: {compact_summary['planning_health_summary']}",
            f"- plugin_install_drift: {compact_summary['plugin_install_drift_summary']}",
            f"- producer: {compact_summary['producer_summary']}",
            f"- channel_acceptance: {compact_summary['channel_acceptance_summary']}",
            f"- auto_resume: {compact_summary['auto_resume_summary']}",
            f"- top_followup_session: {compact_summary['top_followup_session_summary']}",
            f"- action_hint: {compact_summary['action_hint']}",
            f"- action_hint_command: {compact_summary['action_hint_command_summary']}",
            f"- taskmonitor: {compact_summary['taskmonitor_summary']}",
        ]
        return "\n".join(lines) + "\n"
    lines = [
        "# Main Ops Dashboard",
        "",
        f"- generated_at: {summary['generated_at']}",
        f"- session_filter: {summary['session_filter']}",
        f"- status: {summary['status']}",
        f"- main_active_task_count: {summary['health']['main_active_task_count']}",
        f"- main_blocked_task_count: {summary['health']['main_blocked_task_count']}",
        f"- queue_count: {summary['queues']['queue_count']}",
        f"- lane_agent_count: {summary['lanes']['agent_count']}",
        f"- continuity_auto_resumable_task_count: {summary['continuity']['auto_resumable_task_count']}",
        f"- continuity_manual_review_task_count: {summary['continuity']['manual_review_task_count']}",
        f"- planning_promise_without_task_count: {summary['health']['planning_promise_without_task_count']}",
        f"- planning_overdue_followup_count: {summary['health']['planning_overdue_followup_count']}",
        f"- planning_health_status: {summary['health']['planning_health_status']}",
        f"- planning_health_timeout_count: {summary['health']['planning_health_timeout_count']}",
        f"- plugin_install_drift_status: {summary['plugin_install_drift']['status']}",
        f"- plugin_install_drift_missing_count: {summary['plugin_install_drift']['missing_in_installed_count']}",
        f"- plugin_install_drift_extra_count: {summary['plugin_install_drift']['extra_in_installed_count']}",
        f"- producer_focus_channel: {summary['producer_contract']['focus_channel'] or 'mixed'}",
        f"- producer_mode: {summary['producer_contract']['producer_mode'] or 'mixed'}",
        f"- channel_acceptance_phase_status: {summary['channel_acceptance']['phase_status']}",
        f"- auto_resume_ready: {summary['auto_resume_ready']}",
        f"- auto_resume_safe_to_apply: {summary['auto_resume_safe_to_apply']}",
        f"- auto_resume_command: {summary['auto_resume_command'] or 'none'}",
        f"- top_followup_session: {summary['top_followup_session']['session_key'] if summary['top_followup_session'] else 'none'}",
        f"- action_hint: {summary['action_hint']}",
        f"- action_hint_command: {summary['action_hint_command'] or 'none'}",
        f"- taskmonitor_override_count: {summary['taskmonitor']['override_count']}",
        "",
        "## Commands",
        "",
    ]
    for command in summary["suggested_next_commands"]:
        lines.append(f"- {command}")
    runbook = summary.get("runbook")
    if isinstance(runbook, dict):
        lines.extend(["", "## Runbook", ""])
        for step in runbook.get("steps", []):
            lines.append(f"- {step}")
        commands = runbook.get("commands", [])
        if isinstance(commands, list) and commands:
            lines.append("- commands:")
            for command in commands:
                lines.append(f"  {command}")
    return "\n".join(lines) + "\n"


def get_main_dashboard_summary(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
    session_key: Optional[str] = None,
    compact: bool = False,
    only_issues: bool = False,
) -> dict[str, object]:
    resolved_paths = _resolve_paths(config_path, paths=paths)
    normalized_session_key = str(session_key or "").strip() or None
    install_drift = get_main_plugin_install_drift_summary()
    producer_contract = get_main_producer_contract_summary(
        config_path=config_path,
        paths=resolved_paths,
        session_key=normalized_session_key,
    )
    channel_acceptance = get_main_channel_acceptance_summary(
        config_path=config_path,
        paths=resolved_paths,
        session_key=normalized_session_key,
    )
    health = get_main_health_summary(config_path=config_path, paths=resolved_paths)
    queues = get_queue_topology_summary(config_path=config_path, paths=resolved_paths)
    lanes = get_queue_lanes_summary(config_path=config_path, paths=resolved_paths)
    continuity = get_main_continuity_summary(
        config_path=config_path,
        paths=resolved_paths,
        session_key=normalized_session_key,
    )
    taskmonitor: dict[str, object]
    if normalized_session_key:
        queues = _filter_queue_topology_by_session(queues, session_key=normalized_session_key)
        lanes = _filter_lanes_by_session(lanes, session_key=normalized_session_key)
        taskmonitor = {
            "mode": "session",
            **get_taskmonitor_status(normalized_session_key, config_path=config_path),
        }
    else:
        taskmonitor = {
            "mode": "global",
            **get_taskmonitor_overrides(config_path=config_path),
        }
    top_followup_session = None
    if continuity["by_session"]:
        top_session = continuity["by_session"][0]
        top_followup_session = {
            "session_key": top_session["session_key"],
            "auto_resumable_count": top_session["auto_resumable_count"],
            "manual_review_count": top_session["manual_review_count"],
            "not_recommended_count": top_session["not_recommended_count"],
            "task_labels": top_session["task_labels"],
            "user_facing_status_counts": top_session.get("user_facing_status_counts", {}),
            "user_facing_status_code_counts": top_session.get("user_facing_status_code_counts", {}),
            "next_command": (
                f"python3 scripts/runtime/main_ops.py continuity --session-key '{top_session['session_key']}'"
            ),
        }
    status = "ok"
    if (
        health["status"] != "ok"
        or continuity["auto_resumable_task_count"] > 0
        or continuity["manual_review_task_count"] > 0
        or bool(install_drift.get("requires_action"))
    ):
        status = "warn"
    if health["planning_promise_without_task_count"] > 0:
        status = "error"
    elif health["planning_health_status"] == "warn" and status == "ok":
        status = "warn"
    action_hint = "No immediate action needed."
    action_hint_command = None
    continuity_primary_action = continuity.get("primary_action", {})
    if (
        continuity.get("requires_action")
        and isinstance(continuity_primary_action, dict)
        and str(continuity_primary_action.get("command") or "").strip()
    ):
        action_hint = str(continuity_primary_action.get("summary") or action_hint)
        action_hint_command = str(continuity_primary_action.get("command") or "")
    elif (
        health["planning_promise_without_task_count"] > 0
        and isinstance(health.get("planning_primary_recovery_action"), dict)
        and str((health["planning_primary_recovery_action"] or {}).get("command") or "").strip()
    ):
        action_hint = str(health["planning_primary_recovery_action"].get("summary") or action_hint)
        action_hint_command = str(health["planning_primary_recovery_action"].get("command") or "")
    elif (
        health["planning_health_status"] == "warn"
        and isinstance(health.get("planning_primary_recovery_action"), dict)
        and str((health["planning_primary_recovery_action"] or {}).get("kind") or "") == "inspect-planner-timeout"
        and str((health["planning_primary_recovery_action"] or {}).get("command") or "").strip()
    ):
        action_hint = str(health["planning_primary_recovery_action"].get("summary") or action_hint)
        action_hint_command = str(health["planning_primary_recovery_action"].get("command") or "")
    elif (
        health["planning_health_status"] == "warn"
        and isinstance(health.get("planning_primary_recovery_action"), dict)
        and str((health["planning_primary_recovery_action"] or {}).get("kind") or "") in {"inspect-overdue-followup", "inspect-pending-plan"}
        and str((health["planning_primary_recovery_action"] or {}).get("command") or "").strip()
    ):
        action_hint = str(health["planning_primary_recovery_action"].get("summary") or action_hint)
        action_hint_command = str(health["planning_primary_recovery_action"].get("command") or "")
    elif health["main_active_task_count"] > 0:
        action_hint = "Review current lanes before changing queue behavior."
        action_hint_command = "python3 scripts/runtime/main_ops.py lanes --json"
    elif health["planning_health_status"] == "warn":
        action_hint = "Inspect planning health before relying on planner-dependent behavior."
        action_hint_command = "python3 scripts/runtime/main_ops.py planning --json"
    elif bool(install_drift.get("requires_action")) and str(install_drift.get("primary_action_command") or "").strip():
        action_hint = "Inspect installed runtime drift before relying on local plugin runtime behavior."
        action_hint_command = str(install_drift["primary_action_command"])
    elif normalized_session_key and not bool(taskmonitor.get("enabled", True)):
        action_hint = f"Taskmonitor is disabled for {normalized_session_key}; re-enable if you want watchdog coverage."
        action_hint_command = (
            f"python3 scripts/runtime/main_ops.py taskmonitor --session-key '{normalized_session_key}' --action on"
        )
    compact_summary = {
        "scope": normalized_session_key or "all",
        "status": status,
        "main_active_task_count": health["main_active_task_count"],
        "main_blocked_task_count": health["main_blocked_task_count"],
        "queue_count": queues["queue_count"],
        "lane_agent_count": lanes["agent_count"],
        "continuity_auto_resumable_task_count": continuity["auto_resumable_task_count"],
        "continuity_manual_review_task_count": continuity["manual_review_task_count"],
        "planning_promise_without_task_count": health["planning_promise_without_task_count"],
        "planning_overdue_followup_count": health["planning_overdue_followup_count"],
        "planning_health_summary": (
            f"{health['planning_health_status']} timeouts={health['planning_health_timeout_count']}"
        ),
        "plugin_install_drift_summary": (
            f"{install_drift['status']} missing={install_drift['missing_in_installed_count']} extra={install_drift['extra_in_installed_count']}"
        ),
        "producer_summary": (
            f"{producer_contract['focus_channel']}:{producer_contract['producer_mode']}"
            if producer_contract.get("focus_channel")
            else "mixed"
        ),
        "channel_acceptance_summary": (
            f"{channel_acceptance['focus_channel']}:{channel_acceptance['focus_rollout_status']}"
            if channel_acceptance.get("focus_channel")
            else channel_acceptance.get("phase_status", "unknown")
        ),
        "auto_resume_summary": (
            "safe"
            if continuity.get("auto_resume_safe_to_apply")
            else "blocked"
            if continuity.get("auto_resume_ready")
            else "none"
        ),
        "top_followup_session_summary": (
            (
                f"{top_followup_session['session_key']} | user_statuses="
                f"{', '.join(f'{label}:{count}' for label, count in (top_followup_session.get('user_facing_status_counts') or {}).items()) or 'none'}"
            )
            if top_followup_session
            else "none"
        ),
        "action_hint": action_hint,
        "action_hint_command_summary": action_hint_command or "none",
        "taskmonitor_summary": (
            f"session-enabled={taskmonitor['enabled']}"
            if normalized_session_key
            else f"override_count={taskmonitor['override_count']}"
        ),
    }
    suggested_next_commands = (
        [
            "python3 scripts/runtime/main_ops.py health",
            "python3 scripts/runtime/main_ops.py producer --json",
            "python3 scripts/runtime/main_ops.py queues --json",
            "python3 scripts/runtime/main_ops.py lanes --json",
            "python3 scripts/runtime/main_ops.py continuity --json",
            *(
                [str(install_drift["primary_action_command"])]
                if bool(install_drift.get("requires_action")) and str(install_drift.get("primary_action_command") or "").strip()
                else []
            ),
            "python3 scripts/runtime/main_ops.py taskmonitor --action list --json",
        ]
        if normalized_session_key is None
        else [
            f"python3 scripts/runtime/main_ops.py producer --session-key '{normalized_session_key}' --json",
            f"python3 scripts/runtime/main_ops.py continuity --session-key '{normalized_session_key}'",
            "python3 scripts/runtime/main_ops.py lanes --json",
            f"python3 scripts/runtime/main_ops.py taskmonitor --session-key '{normalized_session_key}' --action status --json",
        ]
    )
    if action_hint_command:
        suggested_next_commands = [action_hint_command, *[cmd for cmd in suggested_next_commands if cmd != action_hint_command]]
    issue_summary = {
        "has_issues": status != "ok",
        "main_active_task_count": health["main_active_task_count"],
        "main_blocked_task_count": health["main_blocked_task_count"],
        "continuity_auto_resumable_task_count": continuity["auto_resumable_task_count"],
        "continuity_manual_review_task_count": continuity["manual_review_task_count"],
        "planning_promise_without_task_count": health["planning_promise_without_task_count"],
        "planning_overdue_followup_count": health["planning_overdue_followup_count"],
        "planning_health_status": health["planning_health_status"],
        "planning_health_timeout_count": health["planning_health_timeout_count"],
        "plugin_install_drift_status": install_drift.get("status"),
        "plugin_install_drift_missing_count": int(install_drift.get("missing_in_installed_count", 0) or 0),
        "plugin_install_drift_extra_count": int(install_drift.get("extra_in_installed_count", 0) or 0),
        "producer_focus_channel": producer_contract.get("focus_channel"),
        "producer_mode": producer_contract.get("producer_mode"),
        "channel_acceptance_phase_status": channel_acceptance.get("phase_status"),
        "auto_resume_ready": bool(continuity.get("auto_resume_ready")),
        "auto_resume_safe_to_apply": bool(continuity.get("auto_resume_safe_to_apply")),
        "auto_resume_blockers": list(continuity.get("auto_resume_blockers", [])),
        "auto_resume_command": continuity.get("primary_action_command")
        if str(continuity.get("primary_action_kind") or "").strip() in {"apply-auto-resume", "preview-auto-resume"}
        else None,
        "top_followup_session": top_followup_session["session_key"] if top_followup_session else None,
        "action_hint": action_hint if status != "ok" else None,
        "action_hint_command": action_hint_command if status != "ok" else None,
    }
    if (
        continuity.get("requires_action")
        and isinstance(continuity_primary_action, dict)
        and str(continuity_primary_action.get("command") or "").strip()
    ):
        primary_action = {
            "kind": str(continuity_primary_action.get("kind") or "none"),
            "summary": action_hint,
            "command": action_hint_command,
            "session_key": continuity_primary_action.get("session_key"),
        }
    else:
        primary_action = {
            "kind": (
                "followup-session"
                if top_followup_session and action_hint_command
                else "review-lanes"
                if action_hint_command and "lanes --json" in action_hint_command
                else "review-continuity"
                if action_hint_command and "continuity" in action_hint_command
                else "enable-taskmonitor"
                if action_hint_command and "--action on" in action_hint_command
                else "none"
            ),
            "summary": action_hint,
            "command": action_hint_command,
            "session_key": top_followup_session["session_key"] if top_followup_session else normalized_session_key,
        }
    runbook = {
        "status": status,
        "primary_action": primary_action,
        "steps": [
            primary_action["summary"],
            "Review the suggested commands in order if the first action does not fully resolve the current state.",
        ],
        "commands": suggested_next_commands,
    }
    issue_summary["primary_action"] = (
        primary_action
        if status != "ok"
        else {
            "kind": "none",
            "summary": "No immediate action needed.",
            "command": None,
            "session_key": None,
        }
    )
    issue_summary["runbook"] = (
        runbook
        if status != "ok"
        else {
            "status": "ok",
            "primary_action": issue_summary["primary_action"],
            "steps": ["No immediate action needed."],
            "commands": [],
        }
    )
    issue_summary["primary_action_kind"] = issue_summary["primary_action"]["kind"]
    issue_summary["primary_action_command"] = issue_summary["primary_action"]["command"]
    issue_summary["runbook_status"] = issue_summary["runbook"]["status"]
    issue_summary["requires_action"] = bool(issue_summary["has_issues"])
    return {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "session_filter": normalized_session_key or "all",
        "status": status,
        "compact": compact,
        "only_issues": only_issues,
        "compact_summary": compact_summary,
        "issue_summary": issue_summary,
        "plugin_install_drift": install_drift,
        "health": health,
        "queues": queues,
        "lanes": lanes,
        "continuity": continuity,
        "producer_contract": producer_contract,
        "channel_acceptance": channel_acceptance,
        "top_followup_session": top_followup_session,
        "focus_session_key": top_followup_session["session_key"] if top_followup_session else None,
        "auto_resume_ready": bool(continuity.get("auto_resume_ready")),
        "auto_resume_safe_to_apply": bool(continuity.get("auto_resume_safe_to_apply")),
        "auto_resume_blockers": list(continuity.get("auto_resume_blockers", [])),
        "auto_resume_command": continuity.get("primary_action_command")
        if str(continuity.get("primary_action_kind") or "").strip() in {"apply-auto-resume", "preview-auto-resume"}
        else None,
        "action_hint": action_hint,
        "action_hint_command": action_hint_command,
        "primary_action_kind": primary_action["kind"],
        "primary_action_command": primary_action["command"],
        "runbook_status": runbook["status"],
        "requires_action": status != "ok",
        "primary_action": primary_action,
        "runbook": runbook,
        "taskmonitor": taskmonitor,
        "suggested_next_commands": suggested_next_commands,
    }


def render_queue_lanes(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
) -> str:
    statuses = list_inflight_statuses(config_path=config_path, paths=paths)
    queue_statuses = {"received", "queued", "running", "paused"}
    relevant = [status for status in statuses if str(status["status"]) in queue_statuses]
    now_dt = datetime.now(timezone.utc).astimezone()
    lines = ["# Queue Lanes", ""]
    if not relevant:
        lines.append("- none")
        return "\n".join(lines) + "\n"

    agent_ids = sorted({str(status["agent_id"]) for status in relevant})
    for agent_id in agent_ids:
        agent_tasks = [status for status in relevant if str(status["agent_id"]) == agent_id]
        running_tasks = [status for status in agent_tasks if str(status["status"]) == STATUS_RUNNING]
        queued_tasks = [status for status in agent_tasks if str(status["status"]) in {STATUS_QUEUED, "received"}]
        paused_tasks = [status for status in agent_tasks if str(status["status"]) == "paused"]
        due_paused_tasks = []
        for task in paused_tasks:
            continuation_due_at = _parse_iso8601(
                str(
                    (
                        task.get("meta", {})
                        if isinstance(task.get("meta"), dict)
                        else {}
                    ).get("continuation_due_at")
                    or ""
                )
            )
            if continuation_due_at and continuation_due_at <= now_dt:
                due_paused_tasks.append(task)
        session_keys = sorted({str(status["session_key"]) for status in agent_tasks})
        lane_kind = "shared" if len(session_keys) > 1 else "single-session"
        running_sessions = sorted({str(status["session_key"]) for status in running_tasks})
        shared_with_running_lane = len(running_sessions) > 0
        sharing_reason = (
            f"agent {agent_id} currently has {len(session_keys)} active sessions in the same lane"
            if lane_kind == "shared"
            else f"agent {agent_id} currently has only one active session in the lane"
        )
        execution_recommendation = (
            "serial"
            if lane_kind == "shared" and shared_with_running_lane
            else "serial-per-session"
            if lane_kind == "shared"
            else "parallel-safe"
        )
        lines.extend(
            [
                f"## Agent: {agent_id}",
                "",
                f"- lane_kind: {lane_kind}",
                f"- sharing_reason: {sharing_reason}",
                f"- shared_with_running_lane: {shared_with_running_lane}",
                f"- execution_recommendation: {execution_recommendation}",
                f"- active_task_count: {len(agent_tasks)}",
                f"- running_task_count: {len(running_tasks)}",
                f"- queued_task_count: {len(queued_tasks)}",
                f"- paused_task_count: {len(paused_tasks)}",
                f"- due_paused_task_count: {len(due_paused_tasks)}",
                f"- session_lane_count: {len(session_keys)}",
                f"- running_lane_count: {len(running_sessions)}",
            ]
        )
        if len(session_keys) > 1:
            lines.append("- shared_sessions:")
            for session_key in session_keys:
                lines.append(f"  {session_key}")
        if running_tasks:
            lines.append("- running_tasks:")
            for task in sorted(
                running_tasks,
                key=lambda item: (
                    str(item.get("started_at") or item.get("created_at") or ""),
                    str(item["task_id"]),
                ),
            ):
                lines.append(
                    f"  status={_task_user_facing_status(task)} | {task['task_id']} | {task['session_key']} | {task['task_label']}"
                )
        if queued_tasks:
            lines.append("- queued_head:")
            for task in sorted(
                queued_tasks,
                key=lambda item: (
                    int(item["queue"]["position"] or 999999),
                    str(item.get("created_at") or ""),
                    str(item["task_id"]),
                ),
            )[:5]:
                lines.append(
                    f"  pos={task['queue']['position']} | status={_task_user_facing_status(task)} | {task['task_id']} | {task['session_key']} | {task['task_label']}"
                )
        if paused_tasks:
            lines.append("- paused_tasks:")
            for task in sorted(
                paused_tasks,
                key=lambda item: (
                    str(item.get("updated_at") or item.get("created_at") or ""),
                    str(item["task_id"]),
                ),
            )[:5]:
                lines.append(
                    f"  status={_task_user_facing_status(task)} | {task['task_id']} | {task['session_key']} | {task['task_label']}"
                )
        if due_paused_tasks:
            lines.append("- due_paused_tasks:")
            for task in sorted(
                due_paused_tasks,
                key=lambda item: (
                    str(
                        (
                            item.get("meta", {})
                            if isinstance(item.get("meta"), dict)
                            else {}
                        ).get("continuation_due_at")
                        or ""
                    ),
                    str(item["task_id"]),
                ),
            )[:5]:
                lines.append(
                    f"  status={_task_user_facing_status(task)} | {task['task_id']} | {task['session_key']} | {task['task_label']}"
                )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def get_queue_lanes_summary(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
) -> dict[str, object]:
    statuses = list_inflight_statuses(config_path=config_path, paths=paths)
    queue_statuses = {"received", "queued", "running", "paused"}
    relevant = [status for status in statuses if str(status["status"]) in queue_statuses]
    now_dt = datetime.now(timezone.utc).astimezone()
    agents: list[dict[str, object]] = []
    for agent_id in sorted({str(status["agent_id"]) for status in relevant}):
        agent_tasks = [status for status in relevant if str(status["agent_id"]) == agent_id]
        running_tasks = [status for status in agent_tasks if str(status["status"]) == STATUS_RUNNING]
        queued_tasks = [status for status in agent_tasks if str(status["status"]) in {STATUS_QUEUED, "received"}]
        paused_tasks = [status for status in agent_tasks if str(status["status"]) == "paused"]
        due_paused_tasks = []
        for task in paused_tasks:
            continuation_due_at = _parse_iso8601(
                str(((task.get("meta", {}) if isinstance(task.get("meta"), dict) else {}).get("continuation_due_at")) or "")
            )
            if continuation_due_at and continuation_due_at <= now_dt:
                due_paused_tasks.append(task)
        session_keys = sorted({str(status["session_key"]) for status in agent_tasks})
        lane_kind = "shared" if len(session_keys) > 1 else "single-session"
        running_sessions = sorted({str(status["session_key"]) for status in running_tasks})
        shared_with_running_lane = len(running_sessions) > 0
        sharing_reason = (
            f"agent {agent_id} currently has {len(session_keys)} active sessions in the same lane"
            if lane_kind == "shared"
            else f"agent {agent_id} currently has only one active session in the lane"
        )
        execution_recommendation = (
            "serial"
            if lane_kind == "shared" and shared_with_running_lane
            else "serial-per-session"
            if lane_kind == "shared"
            else "parallel-safe"
        )
        agents.append(
            {
                "agent_id": agent_id,
                "lane_kind": lane_kind,
                "sharing_reason": sharing_reason,
                "shared_with_running_lane": shared_with_running_lane,
                "execution_recommendation": execution_recommendation,
                "active_task_count": len(agent_tasks),
                "running_task_count": len(running_tasks),
                "queued_task_count": len(queued_tasks),
                "paused_task_count": len(paused_tasks),
                "due_paused_task_count": len(due_paused_tasks),
                "session_lane_count": len(session_keys),
                "running_lane_count": len(running_sessions),
                "shared_sessions": session_keys if len(session_keys) > 1 else [],
                "running_tasks": [
                    {
                        "task_id": str(task["task_id"]),
                        "session_key": str(task["session_key"]),
                        "task_label": str(task["task_label"]),
                        "user_facing_status_code": _task_user_facing_status_code(task),
                        "user_facing_status": _task_user_facing_status(task),
                    }
                    for task in sorted(
                        running_tasks,
                        key=lambda item: (
                            str(item.get("started_at") or item.get("created_at") or ""),
                            str(item["task_id"]),
                        ),
                    )
                ],
                "queued_head": [
                    {
                        "position": int(task["queue"]["position"] or 999999),
                        "task_id": str(task["task_id"]),
                        "session_key": str(task["session_key"]),
                        "task_label": str(task["task_label"]),
                        "user_facing_status_code": _task_user_facing_status_code(task),
                        "user_facing_status": _task_user_facing_status(task),
                    }
                    for task in sorted(
                        queued_tasks,
                        key=lambda item: (
                            int(item["queue"]["position"] or 999999),
                            str(item.get("created_at") or ""),
                            str(item["task_id"]),
                        ),
                    )[:5]
                ],
                "paused_tasks": [
                    {
                        "task_id": str(task["task_id"]),
                        "session_key": str(task["session_key"]),
                        "task_label": str(task["task_label"]),
                        "user_facing_status_code": _task_user_facing_status_code(task),
                        "user_facing_status": _task_user_facing_status(task),
                    }
                    for task in sorted(
                        paused_tasks,
                        key=lambda item: (
                            str(item.get("updated_at") or item.get("created_at") or ""),
                            str(item["task_id"]),
                        ),
                    )[:5]
                ],
                "due_paused_tasks": [
                    {
                        "task_id": str(task["task_id"]),
                        "session_key": str(task["session_key"]),
                        "task_label": str(task["task_label"]),
                        "user_facing_status_code": _task_user_facing_status_code(task),
                        "user_facing_status": _task_user_facing_status(task),
                    }
                    for task in sorted(
                        due_paused_tasks,
                        key=lambda item: (
                            str(((item.get("meta", {}) if isinstance(item.get("meta"), dict) else {}).get("continuation_due_at")) or ""),
                            str(item["task_id"]),
                        ),
                    )[:5]
                ],
            }
        )
    return {
        "queue_statuses": sorted(queue_statuses),
        "agent_count": len(agents),
        "agents": agents,
    }


def render_queue_topology(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
) -> str:
    statuses = list_inflight_statuses(config_path=config_path, paths=paths)
    queue_statuses = {"received", "queued", "running", "paused"}
    relevant = [status for status in statuses if str(status["status"]) in queue_statuses]
    lines = ["# Queue Topology", ""]
    if not relevant:
        lines.append("- none")
        return "\n".join(lines) + "\n"

    agent_ids = sorted({str(status["agent_id"]) for status in relevant})
    lines.append(f"- queue_count: {len(agent_ids)}")
    lines.append("")
    for agent_id in agent_ids:
        agent_tasks = [status for status in relevant if str(status["agent_id"]) == agent_id]
        session_keys = sorted({str(status["session_key"]) for status in agent_tasks})
        session_counts: list[tuple[str, int]] = []
        for session_key in session_keys:
            session_counts.append(
                (
                    session_key,
                    len([status for status in agent_tasks if str(status["session_key"]) == session_key]),
                )
            )
        queue_kind = "shared" if len(session_keys) > 1 else "single-session"
        shared_sessions = session_keys if len(session_keys) > 1 else []
        running_count = len([status for status in agent_tasks if str(status["status"]) == STATUS_RUNNING])
        queued_count = len([status for status in agent_tasks if str(status["status"]) in {STATUS_QUEUED, "received"}])
        paused_count = len([status for status in agent_tasks if str(status["status"]) == "paused"])
        shared_with_running_lane = running_count > 0 and len(session_keys) > 1
        sharing_reason = (
            f"agent {agent_id} queue is shared because {len(session_keys)} sessions currently map to the same agent queue"
            if queue_kind == "shared"
            else f"agent {agent_id} queue is currently dedicated to one session"
        )
        execution_recommendation = (
            "serial"
            if queue_kind == "shared" and shared_with_running_lane
            else "serial-per-session"
            if queue_kind == "shared"
            else "parallel-safe"
        )
        lines.extend(
            [
                f"## Queue: {agent_id}",
                "",
                f"- queue_kind: {queue_kind}",
                f"- sharing_reason: {sharing_reason}",
                f"- shared_with_running_lane: {shared_with_running_lane}",
                f"- execution_recommendation: {execution_recommendation}",
                f"- session_count: {len(session_keys)}",
                f"- active_task_count: {len(agent_tasks)}",
                f"- running_task_count: {running_count}",
                f"- queued_task_count: {queued_count}",
                f"- paused_task_count: {paused_count}",
            ]
        )
        if shared_sessions:
            lines.append("- shared_sessions:")
            for session_key in shared_sessions:
                lines.append(f"  {session_key}")
        if session_counts:
            lines.append("- sessions:")
            for session_key, count in session_counts:
                session_tasks = [
                    status for status in agent_tasks if str(status["session_key"]) == session_key
                ]
                lines.append(
                    f"  {session_key} | task_count={count} | user_statuses={_render_user_facing_status_counts(session_tasks)}"
                )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def get_queue_topology_summary(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
) -> dict[str, object]:
    statuses = list_inflight_statuses(config_path=config_path, paths=paths)
    queue_statuses = {"received", "queued", "running", "paused"}
    relevant = [status for status in statuses if str(status["status"]) in queue_statuses]
    queues: list[dict[str, object]] = []
    for agent_id in sorted({str(status["agent_id"]) for status in relevant}):
        agent_tasks = [status for status in relevant if str(status["agent_id"]) == agent_id]
        session_keys = sorted({str(status["session_key"]) for status in agent_tasks})
        queue_kind = "shared" if len(session_keys) > 1 else "single-session"
        shared_sessions = session_keys if len(session_keys) > 1 else []
        running_count = len([status for status in agent_tasks if str(status["status"]) == STATUS_RUNNING])
        queued_count = len([status for status in agent_tasks if str(status["status"]) in {STATUS_QUEUED, "received"}])
        paused_count = len([status for status in agent_tasks if str(status["status"]) == "paused"])
        shared_with_running_lane = running_count > 0 and len(session_keys) > 1
        sharing_reason = (
            f"agent {agent_id} queue is shared because {len(session_keys)} sessions currently map to the same agent queue"
            if queue_kind == "shared"
            else f"agent {agent_id} queue is currently dedicated to one session"
        )
        execution_recommendation = (
            "serial"
            if queue_kind == "shared" and shared_with_running_lane
            else "serial-per-session"
            if queue_kind == "shared"
            else "parallel-safe"
        )
        queues.append(
            {
                "agent_id": agent_id,
                "queue_kind": queue_kind,
                "sharing_reason": sharing_reason,
                "shared_with_running_lane": shared_with_running_lane,
                "execution_recommendation": execution_recommendation,
                "shared_sessions": shared_sessions,
                "session_count": len(session_keys),
                "active_task_count": len(agent_tasks),
                "running_task_count": running_count,
                "queued_task_count": queued_count,
                "paused_task_count": paused_count,
                "sessions": [
                    {
                        "session_key": session_key,
                        "task_count": len(
                            [status for status in agent_tasks if str(status["session_key"]) == session_key]
                        ),
                        "user_facing_status_counts": _summarize_user_facing_statuses(
                            [
                                status
                                for status in agent_tasks
                                if str(status["session_key"]) == session_key
                            ]
                        ),
                        "user_facing_status_code_counts": _summarize_user_facing_status_codes(
                            [
                                status
                                for status in agent_tasks
                                if str(status["session_key"]) == session_key
                            ]
                        ),
                    }
                    for session_key in session_keys
                ],
            }
        )
    return {
        "queue_statuses": sorted(queue_statuses),
        "queue_count": len(queues),
        "queues": queues,
    }


def _parse_iso8601(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _task_user_facing_status(task: dict[str, object]) -> str:
    return _task_user_facing_projection(task)["label"]


def _task_user_facing_projection(task: dict[str, object]) -> dict[str, str]:
    code = str(task.get("user_facing_status_code") or "").strip()
    label = str(task.get("user_facing_status") or "").strip()
    family = str(task.get("user_facing_status_family") or "").strip()
    if code and label:
        return {"code": code, "label": label, "family": family or "unknown"}
    return project_user_facing_status(task)


def _task_user_facing_status_code(task: dict[str, object]) -> str:
    return _task_user_facing_projection(task)["code"]


def _summarize_user_facing_statuses(tasks: list[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for task in tasks:
        label = _task_user_facing_status(task)
        counts[label] = counts.get(label, 0) + 1
    return counts


def _summarize_user_facing_status_codes(tasks: list[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for task in tasks:
        code = _task_user_facing_status_code(task)
        counts[code] = counts.get(code, 0) + 1
    return counts


def _render_user_facing_status_counts(tasks: list[dict[str, object]]) -> str:
    counts = _summarize_user_facing_statuses(tasks)
    if not counts:
        return "none"
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return ", ".join(f"{label}:{count}" for label, count in ordered)


def _blocked_age_minutes(task: dict[str, object], *, now: Optional[datetime] = None) -> Optional[int]:
    anchor = _parse_iso8601(str(task.get("updated_at") or task.get("started_at") or task.get("created_at") or ""))
    if anchor is None:
        return None
    current = now or datetime.now(timezone.utc).astimezone(anchor.tzinfo)
    return max(0, int((current - anchor).total_seconds() // 60))


def sweep_main_tasks(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
    fail_stale_blocked_after_minutes: Optional[int] = None,
    reason: str = "automatic stale blocked cleanup",
) -> dict[str, object]:
    resolved_paths = _resolve_paths(config_path, paths=paths)
    blocked_tasks = [task for task in list_main_tasks(config_path=config_path, paths=resolved_paths) if task["status"] == "blocked"]
    actions: list[dict[str, object]] = []
    for task in blocked_tasks:
        blocked_age = _blocked_age_minutes(task)
        should_fail = (
            fail_stale_blocked_after_minutes is not None
            and blocked_age is not None
            and blocked_age >= fail_stale_blocked_after_minutes
        )
        if should_fail:
            updated = fail_main_task(str(task["task_id"]), reason, paths=resolved_paths)
            actions.append(
                {
                    "task_id": updated.task_id,
                    "action": "failed",
                    "blocked_age_minutes": blocked_age,
                    "reason": reason,
                }
            )
        else:
            actions.append(
                {
                    "task_id": str(task["task_id"]),
                    "action": "noop",
                    "blocked_age_minutes": blocked_age,
                }
            )
    return {
        "blocked_main_task_count": len(blocked_tasks),
        "actions": actions,
    }


def resolve_main_failures(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
    task_ids: Optional[list[str]] = None,
    include_non_retryable: bool = False,
    include_persistent_retryable: bool = False,
    min_retry_count: int = 1,
    apply_changes: bool = False,
    reason: str = "manual failed instruction resolution",
) -> dict[str, object]:
    resolved_paths = _resolve_paths(config_path, paths=paths)
    findings = resolve_failed_instructions(
        paths=resolved_paths,
        task_ids=task_ids,
        include_non_retryable=include_non_retryable,
        include_persistent_retryable=include_persistent_retryable,
        min_retry_count=min_retry_count,
        apply_changes=apply_changes,
        reason=reason,
    )
    return {
        "apply_changes": apply_changes,
        "resolved_count": len(findings),
        "findings": findings,
    }


def render_delivery_diagnose(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
) -> str:
    report = build_health_report(config_path=config_path, paths=paths)
    config = load_task_system_config(config_path=config_path)
    failed_summary = report["failed_instruction_summary"]
    retryable_items = [item for item in failed_summary["items"] if item["retryable"]]

    lines = [
        "# Delivery Diagnose",
        "",
        f"- openclaw_bin: {config.delivery.openclaw_bin}",
        f"- retryable_failed_instruction_count: {failed_summary['retryable']}",
        f"- persistent_retryable_failed_instruction_count: {failed_summary['persistent_retryable']}",
    ]

    if not retryable_items:
        lines.extend(
            [
                "",
                "## Status",
                "",
                "- No retryable delivery failure needs host diagnosis.",
            ]
        )
        return "\n".join(lines) + "\n"

    probe = retryable_items[0]
    probe_target = probe.get("chat_id") or "<chat-id>"
    probe_channel = probe.get("channel") or "telegram"

    lines.extend(
        [
            "",
            "## Probe Target",
            "",
            f"- task_id: {probe.get('task_id')}",
            f"- channel: {probe_channel}",
            f"- chat_id: {probe_target}",
            f"- retry_count: {probe.get('retry_count')}",
        ]
    )
    if probe.get("last_error_summary"):
        lines.append(f"- last_error: {probe['last_error_summary']}")

    probe_command = (
        f"{config.delivery.openclaw_bin} message send --channel {probe_channel} "
        f"--target {probe_target} --message \"task system network probe\""
    )
    lines.extend(
        [
            "",
            "## Suggested Checks",
            "",
            f"- Run host probe command: `{probe_command}`",
            "- If the probe fails with the same network message, investigate the host network path or Telegram connectivity before retrying task-system delivery.",
            "- If the probe succeeds, rerun `python3 scripts/runtime/main_ops.py repair --execute-retries --execution-context host`.",
        ]
    )
    return "\n".join(lines) + "\n"


def acknowledge_delivery_outage(
    *,
    channel: str,
    chat_id: str,
    reason: str,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
) -> dict[str, object]:
    resolved_paths = _resolve_paths(config_path, paths=paths)
    return acknowledge_outage(channel=channel, chat_id=chat_id, reason=reason, paths=resolved_paths)


def clear_delivery_outage(
    *,
    channel: str,
    chat_id: str,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
) -> dict[str, object]:
    resolved_paths = _resolve_paths(config_path, paths=paths)
    removed = clear_outage(channel=channel, chat_id=chat_id, paths=resolved_paths)
    return {
        "channel": channel,
        "chat_id": chat_id,
        "removed": removed,
    }


def get_main_triage_summary(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
) -> dict[str, object]:
    report = build_health_report(config_path=config_path, paths=paths)
    install_drift = get_main_plugin_install_drift_summary()
    overview = report["overview"]
    producer_contract = get_main_producer_contract_summary(config_path=config_path, paths=paths)
    channel_acceptance = get_main_channel_acceptance_summary(config_path=config_path, paths=paths)
    blocked_main = [
        task for task in overview["active_tasks"] if task["agent_id"] == "main" and task["status"] == "blocked"
    ]
    continuity = get_main_continuity_summary(config_path=config_path, paths=paths)
    failed_summary = report["failed_instruction_summary"]
    next_actions: list[str] = []
    primary_action = {
        "kind": "none",
        "summary": "No blocked main task requires manual action.",
        "command": None,
        "session_key": None,
    }
    focus_session_key = None
    planning_summary = report["overview"].get("planning") if isinstance(report["overview"].get("planning"), dict) else {}
    planning_health = planning_summary.get("health") if isinstance(planning_summary.get("health"), dict) else {}
    planning_anomaly_task = next(
        (
            item
            for item in overview["active_tasks"]
            if item["agent_id"] == "main"
            and isinstance(item.get("planning"), dict)
            and bool(item["planning"].get("promise_without_task"))
        ),
        None,
    )

    if blocked_main:
        task = blocked_main[0]
        blocked_age = _blocked_age_minutes(task)
        if int(planning_summary.get("promise_without_task_count", 0) or 0):
            anomaly_task = planning_anomaly_task or task
            inspect_command = f"python3 scripts/runtime/main_ops.py show {anomaly_task['task_id']}"
            primary_action = {
                "kind": "inspect-planning-anomaly",
                "summary": "Inspect the planning anomaly before resuming blocked work.",
                "command": inspect_command,
                "session_key": anomaly_task.get("session_key"),
            }
            next_actions.append(f"Inspect planning anomaly first: `{inspect_command}`")
        elif bool(continuity.get("auto_resume_safe_to_apply")) and str(continuity.get("primary_action_command") or "").strip():
            primary_action = {
                "kind": "apply-auto-resume",
                "summary": "Apply guarded auto-resume first.",
                "command": str(continuity["primary_action_command"]),
                "session_key": continuity.get("focus_session_key"),
            }
            next_actions.append(f"Apply guarded auto-resume first: `{continuity['primary_action_command']}`")
        elif bool(continuity.get("auto_resume_ready")) and str(continuity.get("auto_resume_preview_command") or "").strip():
            primary_action = {
                "kind": "preview-auto-resume",
                "summary": "Preview guarded auto-resume first.",
                "command": str(continuity["auto_resume_preview_command"]),
                "session_key": continuity.get("focus_session_key"),
            }
            next_actions.append(f"Preview guarded auto-resume first: `{continuity['auto_resume_preview_command']}`")
        else:
            resume_command = (
                f"python3 scripts/runtime/main_ops.py resume {task['task_id']} --note \"继续推进并同步真实进展\""
            )
            primary_action = {
                "kind": "resume-task",
                "summary": "Resume blocked main task.",
                "command": resume_command,
                "session_key": task.get("session_key"),
            }
            next_actions.append(f"Resume blocked main task: `{resume_command}`")
        focus_session_key = primary_action.get("session_key") or task.get("session_key")
        next_actions.append(
            f"Or fail it explicitly: `python3 scripts/runtime/main_ops.py fail {task['task_id']} --reason \"manual close after triage\"`"
        )
        if blocked_age is not None:
            next_actions.append(f"Current blocked age: {blocked_age} minute(s)")
            if blocked_age >= 60:
                next_actions.append(
                    "Optional stale cleanup: "
                    "`python3 scripts/runtime/main_ops.py sweep --fail-stale-blocked-after-minutes 60 --reason \"stale blocked main task\"`"
                )
    elif int(planning_summary.get("promise_without_task_count", 0) or 0) and planning_anomaly_task is not None:
        planning_recovery = (
            (planning_anomaly_task.get("planning") or {}).get("recovery_action")
            if isinstance(planning_anomaly_task.get("planning"), dict)
            else None
        )
        inspect_command = str(
            (planning_recovery or {}).get("command")
            or f"python3 scripts/runtime/main_ops.py show {planning_anomaly_task['task_id']}"
        )
        primary_action = {
            "kind": str((planning_recovery or {}).get("kind") or "inspect-planning-anomaly"),
            "summary": str(
                (planning_recovery or {}).get("summary")
                or "Inspect the planning anomaly before taking other actions."
            ),
            "command": inspect_command,
            "session_key": (planning_recovery or {}).get("session_key") or planning_anomaly_task.get("session_key"),
        }
        focus_session_key = planning_anomaly_task.get("session_key")
        next_actions.append(f"{primary_action['summary']} `{inspect_command}`")
    elif (
        str(planning_health.get("status") or "") == "warn"
        and isinstance(planning_summary.get("primary_recovery_action"), dict)
        and str((planning_summary.get("primary_recovery_action") or {}).get("kind") or "") == "inspect-planner-timeout"
        and str((planning_summary.get("primary_recovery_action") or {}).get("command") or "").strip()
    ):
        recovery_action = planning_summary["primary_recovery_action"]
        primary_action = {
            "kind": str(recovery_action.get("kind") or "inspect-planner-timeout"),
            "summary": str(recovery_action.get("summary") or "Inspect the planner timeout before relying on planning health."),
            "command": str(recovery_action.get("command") or "python3 scripts/runtime/main_ops.py planning --json"),
            "session_key": recovery_action.get("session_key"),
        }
        focus_session_key = recovery_action.get("session_key")
        next_actions.append(f"{primary_action['summary']} `{primary_action['command']}`")
    elif (
        isinstance(planning_summary.get("primary_recovery_action"), dict)
        and str((planning_summary.get("primary_recovery_action") or {}).get("kind") or "") in {"inspect-overdue-followup", "inspect-pending-plan"}
        and str((planning_summary.get("primary_recovery_action") or {}).get("command") or "").strip()
    ):
        recovery_action = planning_summary["primary_recovery_action"]
        primary_action = {
            "kind": str(recovery_action.get("kind") or "inspect-planning-health"),
            "summary": str(recovery_action.get("summary") or "Inspect the planning recovery path before relying on planner-dependent behavior."),
            "command": str(recovery_action.get("command") or "python3 scripts/runtime/main_ops.py planning --json"),
            "session_key": recovery_action.get("session_key"),
        }
        focus_session_key = recovery_action.get("session_key")
        next_actions.append(f"{primary_action['summary']} `{primary_action['command']}`")
    elif str(planning_health.get("status") or "") == "warn":
        primary_action = {
            "kind": "inspect-planning-health",
            "summary": "Inspect planning health before relying on planner-dependent behavior.",
            "command": "python3 scripts/runtime/main_ops.py planning --json",
            "session_key": None,
        }
        next_actions.append("Inspect planning health first: `python3 scripts/runtime/main_ops.py planning --json`")
    elif bool(install_drift.get("requires_action")) and str(install_drift.get("primary_action_command") or "").strip():
        primary_action = {
            "kind": str(install_drift.get("primary_action_kind") or "inspect-installed-runtime"),
            "summary": "Inspect installed runtime drift before relying on local plugin runtime behavior.",
            "command": str(install_drift["primary_action_command"]),
            "session_key": None,
        }
        next_actions.append(f"Inspect installed runtime drift first: `{install_drift['primary_action_command']}`")
    else:
        next_actions.append("No blocked main task requires manual action.")

    persistent_retryable_items = [
        item for item in failed_summary["items"] if item["retryable"] and item["retry_count"] > 0
    ]

    if failed_summary["retryable"] and not persistent_retryable_items:
        next_actions.append(
            "Retry retryable failed instructions on host: "
            "`python3 scripts/runtime/main_ops.py repair --execute-retries --execution-context host`"
        )
    elif persistent_retryable_items:
        next_actions.append(
            "Persistent retryable failures detected. Investigate host network/connectivity before running more retries."
        )
    else:
        next_actions.append("No retryable failed instructions are waiting.")

    if failed_summary["non_retryable"]:
        next_actions.append(
            "Review non-retryable failures in `data/failed-instructions/` and correct target/auth/config before retrying."
        )
    else:
        next_actions.append("No non-retryable failed instructions are waiting.")

    retryable_items = [item for item in failed_summary["items"] if item["retryable"]]
    non_retryable_items = [item for item in failed_summary["items"] if item["retryable"] is False]
    suggested_next_commands: list[str] = []
    if primary_action.get("command"):
        suggested_next_commands.append(str(primary_action["command"]))
    if bool(failed_summary["retryable"]) and not persistent_retryable_items:
        suggested_next_commands.append(
            "python3 scripts/runtime/main_ops.py repair --execute-retries --execution-context host"
        )
    if bool(install_drift.get("requires_action")) and str(install_drift.get("primary_action_command") or "").strip():
        suggested_next_commands.append(str(install_drift["primary_action_command"]))
    if focus_session_key:
        suggested_next_commands.append(
            f"python3 scripts/runtime/main_ops.py continuity --session-key '{focus_session_key}'"
        )
    suggested_next_commands.append(
        "python3 scripts/runtime/main_ops.py dashboard --only-issues"
    )
    deduped_commands: list[str] = []
    for command in suggested_next_commands:
        if command and command not in deduped_commands:
            deduped_commands.append(command)
    triage_status = (
        "warn"
        if (
            blocked_main
            or failed_summary["retryable"]
            or failed_summary["non_retryable"]
            or failed_summary["unknown"]
            or str(planning_health.get("status") or "") == "warn"
            or bool(install_drift.get("requires_action"))
        )
        else "ok"
    )
    runbook = {
        "status": triage_status,
        "primary_action": primary_action,
        "steps": [
            primary_action["summary"],
            "Review the suggested commands in order if the first action does not fully resolve triage findings.",
        ],
        "commands": deduped_commands,
    }
    return {
        "status": report["status"],
        "triage_status": triage_status,
        "blocked_main_task_count": len(blocked_main),
        "planning_promise_without_task_count": int(report["overview"].get("planning", {}).get("promise_without_task_count", 0) or 0),
        "planning_overdue_followup_count": int(report["overview"].get("planning", {}).get("overdue_followup_count", 0) or 0),
        "planning_health_status": str(planning_health.get("status") or "unknown"),
        "planning_health_timeout_count": int(planning_health.get("timeout_count", 0) or 0),
        "planning_health_sample_task_count": int(planning_health.get("sample_task_count", 0) or 0),
        "retryable_failed_instruction_count": failed_summary["retryable"],
        "persistent_retryable_failed_instruction_count": failed_summary["persistent_retryable"],
        "non_retryable_failed_instruction_count": failed_summary["non_retryable"],
        "unknown_failed_instruction_count": failed_summary["unknown"],
        "focus_session_key": focus_session_key,
        "plugin_install_drift": install_drift,
        "plugin_install_drift_status": install_drift.get("status"),
        "plugin_install_drift_missing_count": int(install_drift.get("missing_in_installed_count", 0) or 0),
        "plugin_install_drift_extra_count": int(install_drift.get("extra_in_installed_count", 0) or 0),
        "producer_contract": producer_contract,
        "channel_acceptance": channel_acceptance,
        "producer_focus_channel": producer_contract.get("focus_channel"),
        "producer_mode": producer_contract.get("producer_mode"),
        "channel_acceptance_phase_status": channel_acceptance.get("phase_status"),
        "auto_resume_ready": bool(continuity.get("auto_resume_ready")),
        "auto_resume_safe_to_apply": bool(continuity.get("auto_resume_safe_to_apply")),
        "auto_resume_blockers": list(continuity.get("auto_resume_blockers", [])),
        "auto_resume_command": continuity.get("primary_action_command")
        if str(continuity.get("primary_action_kind") or "").strip() in {"apply-auto-resume", "preview-auto-resume"}
        else None,
        "primary_action_kind": primary_action["kind"],
        "primary_action_summary": primary_action["summary"],
        "primary_action_command": primary_action["command"],
        "runbook_status": runbook["status"],
        "requires_action": triage_status != "ok",
        "primary_action": primary_action,
        "runbook": runbook,
        "next_actions": next_actions,
        "suggested_next_commands": deduped_commands,
        "retryable_items": retryable_items,
        "non_retryable_items": non_retryable_items,
    }


def render_main_triage(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
) -> str:
    summary = get_main_triage_summary(config_path=config_path, paths=paths)
    lines = [
        "# Main Ops Triage",
        "",
        f"- status: {summary['status']}",
        f"- triage_status: {summary['triage_status']}",
        f"- blocked_main_task_count: {summary['blocked_main_task_count']}",
        f"- planning_promise_without_task_count: {summary['planning_promise_without_task_count']}",
        f"- planning_overdue_followup_count: {summary['planning_overdue_followup_count']}",
        f"- planning_health_status: {summary['planning_health_status']}",
        f"- planning_health_timeout_count: {summary['planning_health_timeout_count']}",
        f"- planning_health_sample_task_count: {summary['planning_health_sample_task_count']}",
        f"- retryable_failed_instruction_count: {summary['retryable_failed_instruction_count']}",
        f"- persistent_retryable_failed_instruction_count: {summary['persistent_retryable_failed_instruction_count']}",
        f"- non_retryable_failed_instruction_count: {summary['non_retryable_failed_instruction_count']}",
        f"- unknown_failed_instruction_count: {summary['unknown_failed_instruction_count']}",
        f"- focus_session_key: {summary.get('focus_session_key') or 'none'}",
        f"- plugin_install_drift_status: {summary.get('plugin_install_drift_status') or 'unknown'}",
        f"- plugin_install_drift_missing_count: {summary.get('plugin_install_drift_missing_count')}",
        f"- plugin_install_drift_extra_count: {summary.get('plugin_install_drift_extra_count')}",
        f"- producer_focus_channel: {summary.get('producer_focus_channel') or 'mixed'}",
        f"- producer_mode: {summary.get('producer_mode') or 'mixed'}",
        f"- channel_acceptance_phase_status: {summary.get('channel_acceptance_phase_status') or 'unknown'}",
        f"- auto_resume_ready: {summary.get('auto_resume_ready')}",
        f"- auto_resume_safe_to_apply: {summary.get('auto_resume_safe_to_apply')}",
        f"- auto_resume_command: {summary.get('auto_resume_command') or 'none'}",
        f"- primary_action_kind: {summary.get('primary_action_kind')}",
        f"- primary_action_command: {summary.get('primary_action_command') or 'none'}",
        "",
        "## Next Actions",
        "",
    ]
    for action in summary.get("next_actions", []):
        lines.append(f"- {action}")

    retryable_items = summary.get("retryable_items", [])
    if isinstance(retryable_items, list) and retryable_items:
        lines.append("")
        lines.append("## Retryable Failed Instructions")
        lines.append("")
        for item in retryable_items:
            lines.append(
                f"- {item['name']} | classification={item['failure_classification']} | retry_count={item['retry_count']}"
            )
            if item.get("last_error_summary"):
                lines.append(f"  last_error: {item['last_error_summary']}")

    non_retryable_items = summary.get("non_retryable_items", [])
    if isinstance(non_retryable_items, list) and non_retryable_items:
        lines.append("")
        lines.append("## Non-Retryable Failed Instructions")
        lines.append("")
        for item in non_retryable_items:
            lines.append(
                f"- {item['name']} | classification={item['failure_classification']} | chat_id={item['chat_id']}"
            )
            if item.get("last_error_summary"):
                lines.append(f"  last_error: {item['last_error_summary']}")

    runbook = summary.get("runbook")
    if isinstance(runbook, dict):
        lines.extend(["", "## Runbook", ""])
        for step in runbook.get("steps", []):
            lines.append(f"- {step}")
        commands = runbook.get("commands", [])
        if isinstance(commands, list) and commands:
            lines.append("- commands:")
            for command in commands:
                lines.append(f"  {command}")

    return "\n".join(lines) + "\n"


def render_main_producer_contract(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
    session_key: Optional[str] = None,
    channel: Optional[str] = None,
) -> str:
    summary = get_main_producer_contract_summary(
        config_path=config_path,
        paths=paths,
        session_key=session_key,
        channel=channel,
    )
    return render_producer_contract_summary(summary)


def render_main_channel_acceptance(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
    session_key: Optional[str] = None,
    channel: Optional[str] = None,
) -> str:
    summary = get_main_channel_acceptance_summary(
        config_path=config_path,
        paths=paths,
        session_key=session_key,
        channel=channel,
    )
    return render_channel_acceptance_summary(summary)


def repair_system(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
    execute_retries: bool = False,
    openclaw_bin: Optional[str] = None,
    execution_context: str = "local",
) -> dict[str, object]:
    resolved_paths = _resolve_paths(config_path, paths=paths)
    health_before = build_health_report(config_path=config_path, paths=resolved_paths)
    stale_cleanup = reconcile_delivery_artifacts(paths=resolved_paths, apply_changes=True)
    annotated_failures = annotate_failed_instruction_metadata(
        paths=resolved_paths,
        openclaw_bin=openclaw_bin or load_task_system_config(config_path=config_path).delivery.openclaw_bin,
    )
    retry_results: list[dict[str, object]] = []
    if execute_retries:
        retry_results = retry_failed_instructions(
            paths=resolved_paths,
            openclaw_bin=openclaw_bin or load_task_system_config(config_path=config_path).delivery.openclaw_bin,
            execution_context=execution_context,
        )
    health_after = build_health_report(config_path=config_path, paths=resolved_paths)
    return {
        "health_before": health_before,
        "stale_cleanup": stale_cleanup,
        "annotated_failures": annotated_failures,
        "retry_results": retry_results,
        "health_after": health_after,
    }


def _cancel_host_session(
    *,
    session_key: str,
    openclaw_bin: str,
) -> dict[str, object]:
    command = [openclaw_bin, "tasks", "cancel", session_key]
    result = subprocess.run(command, capture_output=True, text=True)
    return {
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "ok": result.returncode == 0,
    }


def stop_main_queue(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
    openclaw_bin: Optional[str] = None,
    reason: str = "user requested stop",
) -> dict[str, object]:
    resolved_paths = _resolve_paths(config_path, paths=paths)
    config = load_task_system_config(config_path=config_path)
    store = TaskStore(paths=resolved_paths)
    running_tasks = store.find_running_tasks(agent_id="main")
    queued_tasks = store.find_queued_tasks(agent_id="main")

    selected = running_tasks[0] if running_tasks else (queued_tasks[0] if queued_tasks else None)
    if selected is None:
        return {
            "action": "noop",
            "reason": "no-main-task-to-stop",
            "remaining_running_count": 0,
            "remaining_queued_count": 0,
            "remaining_active_count": 0,
            "suggestion": "当前没有可停止的 main 任务。",
        }

    host_cancel = None
    if selected.status == STATUS_RUNNING:
        host_cancel = _cancel_host_session(
            session_key=selected.session_key,
            openclaw_bin=openclaw_bin or config.delivery.openclaw_bin,
        )
        if not host_cancel["ok"]:
            return {
                "action": "host-cancel-failed",
                "task_id": selected.task_id,
                "status": selected.status,
                "host_cancel": host_cancel,
            }

    cancelled = store.cancel_task(selected.task_id, reason, archive=True)
    remaining_running = store.find_running_tasks(agent_id="main")
    remaining_queued = store.find_queued_tasks(agent_id="main")
    return {
        "action": "stopped-current" if selected.status == STATUS_RUNNING else "stopped-queued-head",
        "task_id": cancelled.task_id,
        "stopped_status": selected.status,
        "host_cancel": host_cancel,
        "remaining_running_count": len(remaining_running),
        "remaining_queued_count": len(remaining_queued),
        "remaining_active_count": len(remaining_running) + len(remaining_queued),
        "next_running_task_id": remaining_running[0].task_id if remaining_running else None,
        "suggestion": (
            f"已停止 1 个任务；当前前面还有 {len(remaining_running) + len(remaining_queued)} 个号。"
            " 如果希望停止全部，请回复“停止全部”。"
        ),
    }


def stop_all_main_queue(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
    openclaw_bin: Optional[str] = None,
    reason: str = "user requested stop all",
) -> dict[str, object]:
    resolved_paths = _resolve_paths(config_path, paths=paths)
    config = load_task_system_config(config_path=config_path)
    store = TaskStore(paths=resolved_paths)

    queued_tasks = store.find_queued_tasks(agent_id="main")
    running_tasks = store.find_running_tasks(agent_id="main")
    cancelled_tasks: list[dict[str, object]] = []
    host_cancels: list[dict[str, object]] = []

    for task in queued_tasks:
        cancelled = store.cancel_task(task.task_id, reason, archive=True)
        cancelled_tasks.append(
            {
                "task_id": cancelled.task_id,
                "status": STATUS_QUEUED,
            }
        )

    for task in running_tasks:
        host_cancel = _cancel_host_session(
            session_key=task.session_key,
            openclaw_bin=openclaw_bin or config.delivery.openclaw_bin,
        )
        host_cancels.append({"task_id": task.task_id, **host_cancel})
        if host_cancel["ok"]:
            cancelled = store.cancel_task(task.task_id, reason, archive=True)
            cancelled_tasks.append(
                {
                    "task_id": cancelled.task_id,
                    "status": STATUS_RUNNING,
                }
            )

    remaining_running = store.find_running_tasks(agent_id="main")
    remaining_queued = store.find_queued_tasks(agent_id="main")
    return {
        "action": "stopped-all",
        "cancelled_count": len(cancelled_tasks),
        "cancelled_tasks": cancelled_tasks,
        "host_cancels": host_cancels,
        "remaining_running_count": len(remaining_running),
        "remaining_queued_count": len(remaining_queued),
        "remaining_active_count": len(remaining_running) + len(remaining_queued),
        "suggestion": "已停止当前执行任务，并清空剩余队列。",
    }


def cancel_main_queue_task(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
    task_id: Optional[str] = None,
    queue_position: Optional[int] = None,
    reason: str = "user requested queued task cancel",
) -> dict[str, object]:
    resolved_paths = _resolve_paths(config_path, paths=paths)
    store = TaskStore(paths=resolved_paths)
    queued_tasks = store.find_queued_tasks(agent_id="main")

    if task_id:
        try:
            selected = store.load_task(task_id, allow_archive=False)
        except FileNotFoundError:
            return {
                "action": "noop",
                "reason": "task-not-found",
                "task_id": task_id,
            }
        if selected.agent_id != "main":
            return {
                "action": "noop",
                "reason": "not-main-task",
                "task_id": task_id,
                "status": selected.status,
            }
        if selected.status != STATUS_QUEUED:
            return {
                "action": "noop",
                "reason": "task-not-queued",
                "task_id": task_id,
                "status": selected.status,
            }
        selected_position = next(
            (index for index, task in enumerate(queued_tasks, start=1) if task.task_id == selected.task_id),
            None,
        )
    else:
        if queue_position is None:
            return {
                "action": "noop",
                "reason": "missing-selector",
            }
        if queue_position < 1 or queue_position > len(queued_tasks):
            return {
                "action": "noop",
                "reason": "queue-position-out-of-range",
                "queue_position": queue_position,
                "queued_count": len(queued_tasks),
            }
        selected = queued_tasks[queue_position - 1]
        selected_position = queue_position

    cancelled = store.cancel_task(selected.task_id, reason, archive=True)
    remaining_queued = store.find_queued_tasks(agent_id="main")
    return {
        "action": "cancelled-queued-task",
        "task_id": cancelled.task_id,
        "cancelled_status": STATUS_QUEUED,
        "queue_position": selected_position,
        "remaining_queued_count": len(remaining_queued),
        "remaining_active_count": len(store.find_running_tasks(agent_id="main")) + len(remaining_queued),
        "suggestion": (
            f"已取消排队中的第 {selected_position} 个任务；当前剩余 {len(remaining_queued)} 个排队任务。"
            if selected_position is not None
            else "已取消指定排队任务。"
        ),
    }


def purge_task_records(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
    agent_id: Optional[str] = None,
    session_key: Optional[str] = None,
    chat_id: Optional[str] = None,
    include_archive: bool = True,
) -> dict[str, object]:
    resolved_paths = _resolve_paths(config_path, paths=paths)
    roots = [resolved_paths.inflight_dir]
    if include_archive:
        roots.append(resolved_paths.archive_dir)

    deleted: list[dict[str, object]] = []
    scanned_count = 0
    for root in roots:
        root.mkdir(parents=True, exist_ok=True)
        for path in sorted(root.glob("*.json")):
            scanned_count += 1
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if agent_id and str(payload.get("agent_id") or "") != agent_id:
                continue
            if session_key and str(payload.get("session_key") or "") != session_key:
                continue
            if chat_id and str(payload.get("chat_id") or "") != chat_id:
                continue
            path.unlink(missing_ok=True)
            deleted.append(
                {
                    "task_id": str(payload.get("task_id") or path.stem),
                    "status": str(payload.get("status") or ""),
                    "agent_id": str(payload.get("agent_id") or ""),
                    "session_key": str(payload.get("session_key") or ""),
                    "chat_id": str(payload.get("chat_id") or ""),
                    "location": root.name,
                }
            )

    return {
        "action": "purged-task-records",
        "deleted_count": len(deleted),
        "scanned_count": scanned_count,
        "filters": {
            "agent_id": agent_id,
            "session_key": session_key,
            "chat_id": chat_id,
            "include_archive": include_archive,
        },
        "deleted": deleted,
    }


def main() -> None:
    parser = ArgumentParser(description="Operate and inspect main-agent tasks.")
    parser.add_argument("--config", help="Optional task system config path.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List active main tasks.")
    show_parser = subparsers.add_parser("show", help="Show one main task.")
    show_parser.add_argument("task_id")

    resume_parser = subparsers.add_parser("resume", help="Resume a blocked main task.")
    resume_parser.add_argument("task_id")
    resume_parser.add_argument("--note", default=None)

    block_parser = subparsers.add_parser("block", help="Mark a main task blocked.")
    block_parser.add_argument("task_id")
    block_parser.add_argument("--reason", required=True)

    fail_parser = subparsers.add_parser("fail", help="Mark a main task failed.")
    fail_parser.add_argument("task_id")
    fail_parser.add_argument("--reason", required=True)

    complete_parser = subparsers.add_parser("complete", help="Mark a main task completed.")
    complete_parser.add_argument("task_id")
    complete_parser.add_argument("--summary", default=None)
    stop_parser = subparsers.add_parser("stop", help="Stop the current running main task or the head of the queue.")
    stop_parser.add_argument("--reason", default="user requested stop")
    stop_parser.add_argument("--openclaw-bin", default=None)
    stop_all_parser = subparsers.add_parser("stop-all", help="Stop the running main task and clear the remaining queue.")
    stop_all_parser.add_argument("--reason", default="user requested stop all")
    stop_all_parser.add_argument("--openclaw-bin", default=None)
    cancel_parser = subparsers.add_parser("cancel", help="Cancel a queued main task by task id or queue position.")
    cancel_parser.add_argument("--task-id", default=None)
    cancel_parser.add_argument("--queue-position", type=int, default=None)
    cancel_parser.add_argument("--reason", default="user requested queued task cancel")
    purge_parser = subparsers.add_parser("purge", help="Delete matching task records for test cleanup.")
    purge_parser.add_argument("--agent-id", default=None)
    purge_parser.add_argument("--session-key", default=None)
    purge_parser.add_argument("--chat-id", default=None)
    purge_parser.add_argument("--inflight-only", action="store_true", help="Only delete inflight records.")
    taskmonitor_parser = subparsers.add_parser("taskmonitor", help="Inspect or change taskmonitor state for a session.")
    taskmonitor_parser.add_argument("--session-key", default=None)
    taskmonitor_parser.add_argument("--action", choices=["status", "on", "off", "list"], default="status")
    taskmonitor_parser.add_argument("--json", action="store_true", help="Emit structured JSON instead of markdown.")
    dashboard_parser = subparsers.add_parser("dashboard", help="Show a unified main-ops dashboard summary.")
    dashboard_parser.add_argument("--session-key", default=None, help="Focus the dashboard on one session.")
    dashboard_parser.add_argument("--compact", action="store_true", help="Emit a shorter day-to-day dashboard view.")
    dashboard_parser.add_argument("--only-issues", action="store_true", help="Only show non-OK findings in the dashboard view.")
    dashboard_parser.add_argument("--json", action="store_true", help="Emit structured JSON instead of markdown.")
    planning_parser = subparsers.add_parser("planning", help="Show planning-tool path state and anomalies for main.")
    planning_parser.add_argument("--session-key", default=None, help="Focus the planning summary on one session.")
    planning_parser.add_argument("--json", action="store_true", help="Emit structured JSON instead of markdown.")
    plugin_install_drift_parser = subparsers.add_parser(
        "plugin-install-drift",
        help="Show installed-runtime drift against the installable plugin payload.",
    )
    plugin_install_drift_parser.add_argument("--json", action="store_true", help="Emit structured JSON instead of markdown.")
    producer_parser = subparsers.add_parser("producer", help="Show the channel-neutral producer contract summary.")
    producer_parser.add_argument("--session-key", default=None, help="Focus the producer contract on one session.")
    producer_parser.add_argument("--channel", default=None, help="Override the focus channel.")
    producer_parser.add_argument("--json", action="store_true", help="Emit structured JSON instead of markdown.")
    channel_acceptance_parser = subparsers.add_parser(
        "channel-acceptance",
        help="Show the per-channel rollout and acceptance summary.",
    )
    channel_acceptance_parser.add_argument("--session-key", default=None, help="Focus the channel acceptance summary on one session.")
    channel_acceptance_parser.add_argument("--channel", default=None, help="Override the focus channel.")
    channel_acceptance_parser.add_argument("--json", action="store_true", help="Emit structured JSON instead of markdown.")

    subparsers.add_parser("overview", help="Show task system overview.")
    lanes_parser = subparsers.add_parser("lanes", help="Show current queue/lane summary across agents.")
    lanes_parser.add_argument("--json", action="store_true", help="Emit structured JSON instead of markdown.")
    queues_parser = subparsers.add_parser("queues", help="Show current queue topology across agents and sessions.")
    queues_parser.add_argument("--json", action="store_true", help="Emit structured JSON instead of markdown.")
    continuity_parser = subparsers.add_parser("continuity", help="Show main-agent continuity/watchdog risk summary.")
    continuity_parser.add_argument(
        "--session-key",
        default=None,
        help="Only inspect continuity risk for one main session.",
    )
    continuity_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit structured JSON instead of markdown.",
    )
    continuity_parser.add_argument(
        "--resume-watchdog-blocked",
        action="store_true",
        help="Resume watchdog-blocked main tasks instead of only showing the summary.",
    )
    continuity_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of watchdog-blocked tasks to resume.",
    )
    continuity_parser.add_argument(
        "--note",
        default="继续推进并同步真实进展",
        help="Progress note recorded when resuming watchdog-blocked tasks.",
    )
    continuity_parser.add_argument(
        "--respect-execution-advice",
        action="store_true",
        help="Only resume tasks allowed by the current execution recommendation.",
    )
    continuity_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be resumed without changing task state.",
    )
    continuity_parser.add_argument(
        "--auto-resume-if-safe",
        action="store_true",
        help="Apply watchdog auto-resume only when continuity says it is safe to do so.",
    )
    subparsers.add_parser("health", help="Show main-oriented health summary.")
    triage_parser = subparsers.add_parser("triage", help="Show prioritized next actions for main-agent operations.")
    triage_parser.add_argument("--json", action="store_true", help="Emit structured JSON instead of markdown.")
    subparsers.add_parser("diagnose-delivery", help="Show host-side delivery diagnosis steps for retryable failures.")
    ack_parser = subparsers.add_parser("ack-delivery-outage", help="Acknowledge a known external delivery outage.")
    ack_parser.add_argument("--channel", required=True)
    ack_parser.add_argument("--chat-id", required=True)
    ack_parser.add_argument("--reason", required=True)
    clear_parser = subparsers.add_parser("clear-delivery-outage", help="Clear an acknowledged external delivery outage.")
    clear_parser.add_argument("--channel", required=True)
    clear_parser.add_argument("--chat-id", required=True)
    repair_parser = subparsers.add_parser("repair", help="Clean stale delivery state and optionally retry failed sends.")
    repair_parser.add_argument("--execute-retries", action="store_true", help="Retry retryable failed instructions.")
    repair_parser.add_argument("--openclaw-bin", default=None, help="Override openclaw binary for retry execution.")
    repair_parser.add_argument(
        "--execution-context",
        default="local",
        help="Execution context label to write into retry dispatch results.",
    )
    sweep_parser = subparsers.add_parser("sweep", help="Inspect or fail stale blocked main tasks.")
    sweep_parser.add_argument(
        "--fail-stale-blocked-after-minutes",
        type=int,
        default=None,
        help="If set, blocked main tasks older than this threshold will be failed.",
    )
    sweep_parser.add_argument(
        "--reason",
        default="automatic stale blocked cleanup",
        help="Reason recorded when failing stale blocked tasks.",
    )
    resolve_parser = subparsers.add_parser("resolve-failures", help="Inspect or resolve failed instructions.")
    resolve_parser.add_argument("--task-id", action="append", default=None, help="Specific failed task id to resolve.")
    resolve_parser.add_argument("--non-retryable", action="store_true", help="Select non-retryable failed instructions.")
    resolve_parser.add_argument(
        "--persistent-retryable",
        action="store_true",
        help="Select retryable failed instructions that already retried at least once.",
    )
    resolve_parser.add_argument(
        "--min-retry-count",
        type=int,
        default=1,
        help="Minimum retry count used with --persistent-retryable.",
    )
    resolve_parser.add_argument("--apply", action="store_true", help="Actually move selected failures out of active failed-instructions.")
    resolve_parser.add_argument(
        "--reason",
        default="manual failed instruction resolution",
        help="Reason recorded when applying failed instruction resolution.",
    )

    args = parser.parse_args()
    config_path = Path(args.config).expanduser() if args.config else None
    paths = _resolve_paths(config_path, paths=None)

    if args.command == "list":
        print(render_main_list(config_path=config_path), end="")
        return
    if args.command == "show":
        print(render_status_markdown(args.task_id, paths=paths), end="")
        return
    if args.command == "resume":
        task = resume_main_task(args.task_id, progress_note=args.note, paths=paths)
        print(json.dumps(task.to_dict(), ensure_ascii=False, indent=2))
        return
    if args.command == "block":
        task = block_main_task(args.task_id, args.reason, paths=paths)
        print(json.dumps(task.to_dict(), ensure_ascii=False, indent=2))
        return
    if args.command == "fail":
        task = fail_main_task(args.task_id, args.reason, paths=paths)
        print(json.dumps(task.to_dict(), ensure_ascii=False, indent=2))
        return
    if args.command == "complete":
        task = finish_main_task(args.task_id, result_summary=args.summary, paths=paths)
        print(json.dumps(task.to_dict(), ensure_ascii=False, indent=2))
        return
    if args.command == "stop":
        result = stop_main_queue(
            config_path=config_path,
            paths=paths,
            openclaw_bin=args.openclaw_bin,
            reason=args.reason,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.command == "stop-all":
        result = stop_all_main_queue(
            config_path=config_path,
            paths=paths,
            openclaw_bin=args.openclaw_bin,
            reason=args.reason,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.command == "cancel":
        result = cancel_main_queue_task(
            config_path=config_path,
            paths=paths,
            task_id=args.task_id,
            queue_position=args.queue_position,
            reason=args.reason,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.command == "purge":
        result = purge_task_records(
            config_path=config_path,
            paths=paths,
            agent_id=args.agent_id,
            session_key=args.session_key,
            chat_id=args.chat_id,
            include_archive=not args.inflight_only,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.command == "taskmonitor":
        if args.action == "list":
            if args.json:
                print(json.dumps(get_taskmonitor_overrides(config_path=config_path), ensure_ascii=False, indent=2))
                return
            print(render_taskmonitor_overrides(config_path=config_path), end="")
            return
        if not args.session_key:
            raise SystemExit("--session-key is required unless --action=list")
        if args.action == "status":
            if args.json:
                print(json.dumps(get_taskmonitor_status(args.session_key, config_path=config_path), ensure_ascii=False, indent=2))
                return
            print(render_taskmonitor_status(args.session_key, config_path=config_path), end="")
            return
        result = set_taskmonitor_state(
            args.session_key,
            enabled=args.action == "on",
            config_path=config_path,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.command == "dashboard":
        if args.json:
            print(
                json.dumps(
                    get_main_dashboard_summary(
                        config_path=config_path,
                        paths=paths,
                        session_key=args.session_key,
                        compact=args.compact,
                        only_issues=args.only_issues,
                    ),
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return
        print(
            render_main_dashboard(
                config_path=config_path,
                paths=paths,
                session_key=args.session_key,
                compact=args.compact,
                only_issues=args.only_issues,
            ),
            end="",
        )
        return
    if args.command == "planning":
        if args.json:
            print(
                json.dumps(
                    get_main_planning_summary(
                        config_path=config_path,
                        paths=paths,
                        session_key=args.session_key,
                    ),
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return
        print(
            render_main_planning(
                config_path=config_path,
                paths=paths,
                session_key=args.session_key,
            ),
            end="",
        )
        return
    if args.command == "plugin-install-drift":
        if args.json:
            print(json.dumps(get_main_plugin_install_drift_summary(), ensure_ascii=False, indent=2))
            return
        print(render_main_plugin_install_drift(), end="")
        return
    if args.command == "producer":
        if args.json:
            print(
                json.dumps(
                    get_main_producer_contract_summary(
                        config_path=config_path,
                        paths=paths,
                        session_key=args.session_key,
                        channel=args.channel,
                    ),
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return
        print(
            render_main_producer_contract(
                config_path=config_path,
                paths=paths,
                session_key=args.session_key,
                channel=args.channel,
            ),
            end="",
        )
        return
    if args.command == "channel-acceptance":
        if args.json:
            print(
                json.dumps(
                    get_main_channel_acceptance_summary(
                        config_path=config_path,
                        paths=paths,
                        session_key=args.session_key,
                        channel=args.channel,
                    ),
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return
        print(
            render_main_channel_acceptance(
                config_path=config_path,
                paths=paths,
                session_key=args.session_key,
                channel=args.channel,
            ),
            end="",
        )
        return
    if args.command == "overview":
        print(render_overview_markdown(config_path=config_path), end="")
        return
    if args.command == "lanes":
        if args.json:
            print(json.dumps(get_queue_lanes_summary(config_path=config_path, paths=paths), ensure_ascii=False, indent=2))
            return
        print(render_queue_lanes(config_path=config_path, paths=paths), end="")
        return
    if args.command == "queues":
        if args.json:
            print(json.dumps(get_queue_topology_summary(config_path=config_path, paths=paths), ensure_ascii=False, indent=2))
            return
        print(render_queue_topology(config_path=config_path, paths=paths), end="")
        return
    if args.command == "continuity":
        if args.auto_resume_if_safe:
            result = auto_resume_watchdog_blocked_main_tasks_if_safe(
                config_path=config_path,
                paths=paths,
                session_key=args.session_key,
                limit=args.limit,
                note=args.note,
                dry_run=args.dry_run,
            )
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return
            print(render_auto_resume_if_safe_result(result), end="")
            return
        if args.resume_watchdog_blocked:
            result = resume_watchdog_blocked_main_tasks(
                config_path=config_path,
                paths=paths,
                session_key=args.session_key,
                limit=args.limit,
                note=args.note,
                respect_execution_advice=args.respect_execution_advice,
                dry_run=args.dry_run,
            )
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return
            print(render_resume_watchdog_blocked_result(result), end="")
            return
        if args.json:
            print(
                json.dumps(
                    get_main_continuity_summary(
                        config_path=config_path,
                        paths=paths,
                        session_key=args.session_key,
                    ),
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return
        print(
            render_main_continuity(
                config_path=config_path,
                paths=paths,
                session_key=args.session_key,
            ),
            end="",
        )
        return
    if args.command == "health":
        print(render_main_health(config_path=config_path), end="")
        return
    if args.command == "triage":
        if getattr(args, "json", False):
            print(json.dumps(get_main_triage_summary(config_path=config_path, paths=paths), ensure_ascii=False, indent=2))
            return
        print(render_main_triage(config_path=config_path, paths=paths), end="")
        return
    if args.command == "diagnose-delivery":
        print(render_delivery_diagnose(config_path=config_path, paths=paths), end="")
        return
    if args.command == "ack-delivery-outage":
        print(
            json.dumps(
                acknowledge_delivery_outage(
                    channel=args.channel,
                    chat_id=args.chat_id,
                    reason=args.reason,
                    config_path=config_path,
                    paths=paths,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    if args.command == "clear-delivery-outage":
        print(
            json.dumps(
                clear_delivery_outage(
                    channel=args.channel,
                    chat_id=args.chat_id,
                    config_path=config_path,
                    paths=paths,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    if args.command == "repair":
        result = repair_system(
            config_path=config_path,
            paths=paths,
            execute_retries=args.execute_retries,
            openclaw_bin=args.openclaw_bin,
            execution_context=args.execution_context,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.command == "sweep":
        result = sweep_main_tasks(
            config_path=config_path,
            paths=paths,
            fail_stale_blocked_after_minutes=args.fail_stale_blocked_after_minutes,
            reason=args.reason,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.command == "resolve-failures":
        result = resolve_main_failures(
            config_path=config_path,
            paths=paths,
            task_ids=args.task_id,
            include_non_retryable=args.non_retryable,
            include_persistent_retryable=args.persistent_retryable,
            min_retry_count=args.min_retry_count,
            apply_changes=args.apply,
            reason=args.reason,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return


if __name__ == "__main__":
    main()
