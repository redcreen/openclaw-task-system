#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from argparse import ArgumentParser
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from delivery_reconcile import reconcile_delivery_artifacts
from delivery_outage import acknowledge_outage, clear_outage
from health_report import build_health_report
from instruction_executor import (
    annotate_failed_instruction_metadata,
    resolve_failed_instructions,
    retry_failed_instructions,
)
from main_task_adapter import block_main_task, fail_main_task, finish_main_task, resume_main_task
from silence_monitor import scan_tasks
from task_config import load_task_system_config
from task_status import list_inflight_statuses, render_overview_markdown, render_status_markdown
from task_state import STATUS_QUEUED, STATUS_RUNNING, TaskPaths, TaskStore, default_paths
from taskmonitor_state import get_taskmonitor_enabled, list_taskmonitor_overrides, set_taskmonitor_enabled


def _resolve_paths(config_path: Optional[Path], *, paths: Optional[TaskPaths] = None) -> TaskPaths:
    if paths is not None:
        return paths
    config = load_task_system_config(config_path=config_path)
    return config.build_paths() or default_paths()


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
            f"- {task['task_id']} | {task['status']} | delivery={task['delivery']['state']} | {task['task_label']}"
        )
    return "\n".join(lines) + "\n"


def render_main_health(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
) -> str:
    report = build_health_report(config_path=config_path, paths=paths)
    overview = report["overview"]
    blocked_main = [
        task for task in overview["active_tasks"] if task["agent_id"] == "main" and task["status"] == "blocked"
    ]
    lines = [
        "# Main Ops Health",
        "",
        f"- status: {report['status']}",
        f"- main_active_task_count: {len([task for task in overview['active_tasks'] if task['agent_id'] == 'main'])}",
        f"- main_blocked_task_count: {len(blocked_main)}",
        f"- failed_instruction_count: {overview['failed_instruction_count']}",
        f"- active_stale_delivery_task_count: {overview['active_stale_delivery_task_count']}",
    ]
    if blocked_main:
        lines.append("")
        lines.append("## Blocked Main Tasks")
        lines.append("")
        for task in blocked_main:
            lines.append(f"- {task['task_id']} | {task['task_label']}")
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
                "task_labels": [],
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
                f"  resume: python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py resume {task.task_id} --note \"继续推进并同步真实进展\""
            )
            lines.append(
                f"  next: python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --session-key '{task.session_key}'"
            )
            lines.append(
                f"  lanes: python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py lanes --json"
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
                f"  inspect: python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py show {task.task_id}"
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
                f"- {session_key} | auto_resumable={bucket['auto_resumable_count']} | manual_review={bucket['manual_review_count']} | not_recommended={bucket['not_recommended_count']}"
            )
            if unique_labels:
                lines.append(f"  labels: {', '.join(unique_labels[:3])}")

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
                "task_labels": [],
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
        "by_session": [
            {
                "session_key": session_entry["session_key"],
                "auto_resumable_count": session_entry["auto_resumable_count"],
                "manual_review_count": session_entry["manual_review_count"],
                "not_recommended_count": session_entry["not_recommended_count"],
                "task_labels": sorted({str(label) for label in session_entry["task_labels"] if str(label).strip()}),
            }
            for session_entry in sorted(
                session_summary.values(),
                key=lambda item: (
                    -(
                        int(item["auto_resumable_count"])
                        + int(item["manual_review_count"])
                        + int(item["not_recommended_count"])
                    ),
                    str(item["session_key"]),
                ),
            )
        ],
        "suggested_next_commands": [
            "python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py lanes --json",
            *(
                [
                    f"python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --session-key '{normalized_session_key}'"
                ]
                if normalized_session_key
                else []
            ),
        ],
    }


def resume_watchdog_blocked_main_tasks(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
    session_key: Optional[str] = None,
    limit: Optional[int] = None,
    note: Optional[str] = None,
    respect_execution_advice: bool = False,
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
    post_resume_tasks = [
        task
        for task in store.find_inflight_tasks(agent_id="main")
        if task.status in {"received", "queued", "running", "paused"}
        and (normalized_session_key is None or task.session_key == normalized_session_key)
    ]
    post_resume_strategy = _summarize_agent_execution_strategy("main", post_resume_tasks)
    return {
        "action": "resume-watchdog-blocked-main-tasks",
        "session_filter": normalized_session_key or "all",
        "candidate_count": len(watchdog_blocked),
        "eligible_count": len(candidate_tasks),
        "resumed_count": len(resumed),
        "limit": limit,
        "note": resume_note,
        "respect_execution_advice": respect_execution_advice,
        "pre_resume_execution_recommendation": pre_resume_strategy["execution_recommendation"],
        "post_resume_summary": {
            "resumed_session_count": len(resumed_session_keys),
            "status_counts": post_resume_status_counts,
            "execution_recommendation": post_resume_strategy["execution_recommendation"],
            "execution_reason": post_resume_strategy["execution_reason"],
        },
        "skipped": skipped,
        "suggested_next_commands": [
            "python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py lanes --json",
            *[
                f"python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --session-key '{resumed_session_key}'"
                for resumed_session_key in sorted(resumed_session_keys)
            ],
        ],
        "resumed": resumed,
    }


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
                    f"  {task['task_id']} | {task['session_key']} | {task['task_label']}"
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
                    f"  pos={task['queue']['position']} | {task['task_id']} | {task['session_key']} | {task['task_label']}"
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
                    f"  {task['task_id']} | {task['session_key']} | {task['task_label']}"
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
                    f"  {task['task_id']} | {task['session_key']} | {task['task_label']}"
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
                lines.append(f"  {session_key} | task_count={count}")
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
            "- If the probe succeeds, rerun `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py repair --execute-retries --execution-context host`.",
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


def render_main_triage(
    *,
    config_path: Optional[Path] = None,
    paths: Optional[TaskPaths] = None,
) -> str:
    report = build_health_report(config_path=config_path, paths=paths)
    overview = report["overview"]
    blocked_main = [
        task for task in overview["active_tasks"] if task["agent_id"] == "main" and task["status"] == "blocked"
    ]
    failed_summary = report["failed_instruction_summary"]

    lines = [
        "# Main Ops Triage",
        "",
        f"- status: {report['status']}",
        f"- blocked_main_task_count: {len(blocked_main)}",
        f"- retryable_failed_instruction_count: {failed_summary['retryable']}",
        f"- persistent_retryable_failed_instruction_count: {failed_summary['persistent_retryable']}",
        f"- non_retryable_failed_instruction_count: {failed_summary['non_retryable']}",
        f"- unknown_failed_instruction_count: {failed_summary['unknown']}",
        "",
        "## Next Actions",
        "",
    ]

    if blocked_main:
        task = blocked_main[0]
        blocked_age = _blocked_age_minutes(task)
        lines.append(
            f"- Resume blocked main task: `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py resume {task['task_id']} --note \"继续推进并同步真实进展\"`"
        )
        lines.append(
            f"- Or fail it explicitly: `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py fail {task['task_id']} --reason \"manual close after triage\"`"
        )
        if blocked_age is not None:
            lines.append(f"- Current blocked age: {blocked_age} minute(s)")
            if blocked_age >= 60:
                lines.append(
                    f"- Optional stale cleanup: `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py sweep --fail-stale-blocked-after-minutes 60 --reason \"stale blocked main task\"`"
                )
    else:
        lines.append("- No blocked main task requires manual action.")

    persistent_retryable_items = [
        item for item in failed_summary["items"] if item["retryable"] and item["retry_count"] > 0
    ]

    if failed_summary["retryable"] and not persistent_retryable_items:
        lines.append(
            "- Retry retryable failed instructions on host: `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py repair --execute-retries --execution-context host`"
        )
    elif persistent_retryable_items:
        lines.append(
            "- Persistent retryable failures detected. Investigate host network/connectivity before running more retries."
        )
    else:
        lines.append("- No retryable failed instructions are waiting.")

    if failed_summary["non_retryable"]:
        lines.append("- Review non-retryable failures in `data/failed-instructions/` and correct target/auth/config before retrying.")
    else:
        lines.append("- No non-retryable failed instructions are waiting.")

    retryable_items = [item for item in failed_summary["items"] if item["retryable"]]
    non_retryable_items = [item for item in failed_summary["items"] if item["retryable"] is False]

    if retryable_items:
        lines.append("")
        lines.append("## Retryable Failed Instructions")
        lines.append("")
        for item in retryable_items:
            lines.append(
                f"- {item['name']} | classification={item['failure_classification']} | retry_count={item['retry_count']}"
            )
            if item.get("last_error_summary"):
                lines.append(f"  last_error: {item['last_error_summary']}")

    if non_retryable_items:
        lines.append("")
        lines.append("## Non-Retryable Failed Instructions")
        lines.append("")
        for item in non_retryable_items:
            lines.append(
                f"- {item['name']} | classification={item['failure_classification']} | chat_id={item['chat_id']}"
            )
            if item.get("last_error_summary"):
                lines.append(f"  last_error: {item['last_error_summary']}")

    return "\n".join(lines) + "\n"


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
    subparsers.add_parser("health", help="Show main-oriented health summary.")
    subparsers.add_parser("triage", help="Show prioritized next actions for main-agent operations.")
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
        if args.resume_watchdog_blocked:
            result = resume_watchdog_blocked_main_tasks(
                config_path=config_path,
                paths=paths,
                session_key=args.session_key,
                limit=args.limit,
                note=args.note,
                respect_execution_advice=args.respect_execution_advice,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
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
