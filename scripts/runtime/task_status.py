#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from task_config import TaskSystemConfig, load_task_system_config
from task_state import ACTIVE_STATUSES, OBSERVED_STATUSES, STATUS_QUEUED, STATUS_RECEIVED, STATUS_RUNNING, TaskPaths, TaskStore, default_paths
from user_status import project_user_facing_status

FINAL_INSTRUCTION_DIRS = ("processed-instructions", "failed-instructions")
INTERMEDIATE_DELIVERY_DIRS = ("outbox", "sent", "delivery-ready", "send-instructions")
PLANNING_HEALTH_SAMPLE_SIZE = 20


def _artifact_path(paths: TaskPaths, directory: str, task_id: str) -> Path:
    return paths.data_dir / directory / f"{task_id}.json"


def _load_json_if_exists(path: Path) -> Optional[dict[str, object]]:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _resolve_delivery_state(
    *,
    outbox_exists: bool,
    sent_exists: bool,
    delivery_ready_exists: bool,
    send_instruction_exists: bool,
    processed_instruction_exists: bool,
    failed_instruction_exists: bool,
    dispatch_result: Optional[dict[str, object]],
) -> str:
    if processed_instruction_exists:
        action = dispatch_result.get("action") if dispatch_result else None
        if action == "skip":
            return "skipped"
        return "processed"
    if failed_instruction_exists:
        return "failed"
    if send_instruction_exists:
        return "pending-send"
    if delivery_ready_exists:
        return "prepared"
    if sent_exists:
        return "sent"
    if outbox_exists:
        return "queued"
    return "not-requested"


def _stale_intermediate_paths(
    task_id: str,
    *,
    paths: TaskPaths,
    processed_instruction_exists: bool,
    failed_instruction_exists: bool,
) -> list[Path]:
    if not processed_instruction_exists and not failed_instruction_exists:
        return []
    return [
        _artifact_path(paths, directory, task_id)
        for directory in INTERMEDIATE_DELIVERY_DIRS
        if _artifact_path(paths, directory, task_id).exists()
    ]


def build_delivery_summary(task_id: str, *, paths: TaskPaths) -> dict[str, object]:
    outbox_path = _artifact_path(paths, "outbox", task_id)
    sent_path = _artifact_path(paths, "sent", task_id)
    delivery_ready_path = _artifact_path(paths, "delivery-ready", task_id)
    send_instruction_path = _artifact_path(paths, "send-instructions", task_id)
    dispatch_result_path = _artifact_path(paths, "dispatch-results", task_id)
    processed_instruction_path = _artifact_path(paths, "processed-instructions", task_id)
    failed_instruction_path = _artifact_path(paths, "failed-instructions", task_id)
    processed_instruction_exists = processed_instruction_path.exists()
    failed_instruction_exists = failed_instruction_path.exists()

    dispatch_result = _load_json_if_exists(dispatch_result_path)
    delivery_state = _resolve_delivery_state(
        outbox_exists=outbox_path.exists(),
        sent_exists=sent_path.exists(),
        delivery_ready_exists=delivery_ready_path.exists(),
        send_instruction_exists=send_instruction_path.exists(),
        processed_instruction_exists=processed_instruction_exists,
        failed_instruction_exists=failed_instruction_exists,
        dispatch_result=dispatch_result,
    )
    stale_paths = _stale_intermediate_paths(
        task_id,
        paths=paths,
        processed_instruction_exists=processed_instruction_exists,
        failed_instruction_exists=failed_instruction_exists,
    )
    return {
        "state": delivery_state,
        "outbox_exists": outbox_path.exists(),
        "sent_exists": sent_path.exists(),
        "delivery_ready_exists": delivery_ready_path.exists(),
        "send_instruction_exists": send_instruction_path.exists(),
        "processed_instruction_exists": processed_instruction_exists,
        "failed_instruction_exists": failed_instruction_exists,
        "dispatch_result_exists": dispatch_result_path.exists(),
        "stale_intermediate_exists": bool(stale_paths),
        "stale_intermediate_count": len(stale_paths),
        "dispatch_action": dispatch_result.get("action") if dispatch_result else None,
        "dispatch_reason": dispatch_result.get("reason") if dispatch_result else None,
        "dispatch_execution_context": dispatch_result.get("execution_context") if dispatch_result else None,
        "dispatch_requested_execution_context": (
            dispatch_result.get("requested_execution_context") if dispatch_result else None
        ),
        "dispatch_exit_code": dispatch_result.get("exit_code") if dispatch_result else None,
    }


def _resolve_paths(
    paths: Optional[TaskPaths] = None,
    *,
    config: Optional[TaskSystemConfig] = None,
    config_path: Optional[Path] = None,
) -> TaskPaths:
    if paths is not None:
        return paths
    runtime_config = config or load_task_system_config(config_path=config_path)
    return runtime_config.build_paths() or default_paths()


def _build_base_status_summary(task_id: str, *, paths: TaskPaths) -> dict[str, object]:
    store = TaskStore(paths=paths)
    task = store.load_task(task_id)
    return {
        "task_id": task.task_id,
        "task_label": task.task_label,
        "agent_id": task.agent_id,
        "status": task.status,
        "session_key": task.session_key,
        "channel": task.channel,
        "chat_id": task.chat_id,
        "created_at": task.created_at,
        "started_at": task.started_at,
        "updated_at": task.updated_at,
        "last_user_visible_update_at": task.last_user_visible_update_at,
        "last_internal_touch_at": task.last_internal_touch_at,
        "last_monitor_notify_at": task.last_monitor_notify_at,
        "notify_count": task.notify_count,
        "block_reason": task.block_reason,
        "failure_reason": task.failure_reason,
        "monitor_state": task.monitor_state,
        "meta": task.meta,
        "delivery": build_delivery_summary(task_id, paths=paths),
    }


def _parse_iso8601(value: object) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _task_sort_key(task: dict[str, object]) -> tuple[str, str]:
    return (
        str(task.get("updated_at") or task.get("created_at") or ""),
        str(task.get("task_id") or ""),
    )


def _task_record_exists(task_id: Optional[str], *, paths: Optional[TaskPaths]) -> bool:
    normalized_task_id = str(task_id or "").strip()
    if not normalized_task_id or paths is None:
        return False
    inflight_path = paths.inflight_dir / f"{normalized_task_id}.json"
    archived_path = paths.archive_dir / f"{normalized_task_id}.json"
    return inflight_path.exists() or archived_path.exists()


def _build_planning_summary(
    task: dict[str, object],
    *,
    now_dt: Optional[datetime] = None,
    paths: Optional[TaskPaths] = None,
) -> dict[str, object]:
    meta = task.get("meta") if isinstance(task.get("meta"), dict) else {}
    now_dt = now_dt or datetime.now(timezone.utc).astimezone()
    tool_plan = meta.get("tool_followup_plan") if isinstance(meta.get("tool_followup_plan"), dict) else None
    promise_guard = meta.get("planning_promise_guard") if isinstance(meta.get("planning_promise_guard"), dict) else None
    anomaly = str(meta.get("planning_anomaly") or "").strip() or None
    anomaly_at = str(meta.get("planning_anomaly_at") or "").strip() or None
    continuation_kind = str(meta.get("continuation_kind") or "").strip() or None
    continuation_due_at = str(meta.get("continuation_due_at") or "").strip() or None
    continuation_due_dt = _parse_iso8601(continuation_due_at)
    continuation_source = str(meta.get("source") or "").strip() or None

    plan_due_at = str((tool_plan or {}).get("followup_due_at") or "").strip() or None
    plan_due_dt = _parse_iso8601(plan_due_at)
    plan_status = str((tool_plan or {}).get("status") or "").strip() or None
    followup_task_id = str((tool_plan or {}).get("followup_task_id") or "").strip() or None
    followup_task_exists = _task_record_exists(followup_task_id, paths=paths)
    followup_task_missing = bool(
        followup_task_id
        and plan_status in {"scheduled", "fulfilled"}
        and not followup_task_exists
    )
    if followup_task_missing and not anomaly:
        anomaly = "followup-task-missing"
    guard_status = str((promise_guard or {}).get("status") or "").strip() or None

    continuation_is_planned_followup = continuation_source == "tool-followup-plan" or bool(meta.get("plan_id"))
    has_tool_path = bool(tool_plan or promise_guard or anomaly or continuation_is_planned_followup)
    overdue_active_continuation = bool(
        continuation_is_planned_followup
        and continuation_due_dt is not None
        and continuation_due_dt <= now_dt
        and str(task.get("status") or "") in {"paused", "running"}
    )
    promise_without_task = anomaly == "promise-without-task"
    planning_expected = bool((promise_guard or {}).get("expected_by_finalize", False))
    planning_pending = bool(
        has_tool_path
        and not promise_without_task
        and not followup_task_missing
        and (
            plan_status in {"planned", "scheduled"}
            or guard_status in {"armed", "scheduled"}
        )
    )

    return {
        "tool_path_used": has_tool_path,
        "planning_expected": planning_expected,
        "planning_pending": planning_pending,
        "promise_without_task": promise_without_task,
        "anomaly": anomaly,
        "anomaly_at": anomaly_at,
        "has_followup_plan": bool(tool_plan),
        "plan_id": str((tool_plan or {}).get("plan_id") or "").strip() or None,
        "plan_status": plan_status,
        "followup_due_at": plan_due_at or continuation_due_at,
        "followup_task_id": followup_task_id,
        "followup_task_exists": followup_task_exists,
        "followup_task_missing": followup_task_missing,
        "followup_summary": str((tool_plan or {}).get("followup_summary") or "").strip() or None,
        "main_user_content_mode": str((tool_plan or {}).get("main_user_content_mode") or "").strip()
        or str((promise_guard or {}).get("main_user_content_mode") or "").strip()
        or None,
        "promise_guard_armed": bool(promise_guard),
        "promise_guard_status": guard_status,
        "promise_summary": str((promise_guard or {}).get("promise_summary") or "").strip() or None,
        "continuation_kind": continuation_kind,
        "continuation_due_at": continuation_due_at,
        "overdue_followup": overdue_active_continuation,
        "overdue_on_materialize": bool((tool_plan or {}).get("overdue_on_materialize", False)),
    }


def _planning_health_candidate(planning: dict[str, object]) -> bool:
    return bool(
        planning.get("has_followup_plan")
        or planning.get("planning_expected")
        or str(planning.get("plan_status") or "").strip()
        or str(planning.get("promise_guard_status") or "").strip()
        or bool(planning.get("promise_without_task"))
        or bool(planning.get("followup_task_missing"))
        or bool(planning.get("overdue_on_materialize"))
    )


def _planning_timeout_detected(planning: dict[str, object]) -> bool:
    anomaly = str(planning.get("anomaly") or "").strip().lower()
    plan_status = str(planning.get("plan_status") or "").strip().lower()
    guard_status = str(planning.get("promise_guard_status") or "").strip().lower()
    return "timeout" in anomaly or plan_status == "timeout" or guard_status == "timeout"


def _planning_tool_path_completed(planning: dict[str, object]) -> bool:
    if bool(planning.get("followup_task_missing")):
        return False
    plan_status = str(planning.get("plan_status") or "").strip().lower()
    guard_status = str(planning.get("promise_guard_status") or "").strip().lower()
    return (
        plan_status in {"scheduled", "fulfilled", "anomaly"}
        or guard_status in {"scheduled", "fulfilled", "anomaly"}
    )


def _planning_success(planning: dict[str, object]) -> bool:
    if (
        bool(planning.get("promise_without_task"))
        or bool(planning.get("followup_task_missing"))
        or bool(planning.get("overdue_on_materialize"))
        or _planning_timeout_detected(planning)
        or str(planning.get("anomaly") or "").strip()
    ):
        return False
    plan_status = str(planning.get("plan_status") or "").strip().lower()
    guard_status = str(planning.get("promise_guard_status") or "").strip().lower()
    return plan_status in {"scheduled", "fulfilled"} or guard_status in {"scheduled", "fulfilled"}


def _build_planning_recovery_action(task: dict[str, object], planning: dict[str, object]) -> dict[str, object]:
    task_id = str(task.get("task_id") or "")
    session_key = str(task.get("session_key") or "") or None
    inspect_command = f"python3 scripts/runtime/main_ops.py show {task_id}" if task_id else None
    followup_summary = str(planning.get("followup_summary") or planning.get("promise_summary") or "").strip()
    target = followup_summary or "the promised follow-up"
    if bool(planning.get("promise_without_task")):
        return {
            "kind": "inspect-promise-without-task",
            "summary": (
                f"Inspect the source task and either materialize a replacement follow-up for {target} "
                "or clear the stale promise before treating the run as complete."
            ),
            "command": inspect_command,
            "session_key": session_key,
        }
    if bool(planning.get("followup_task_missing")):
        return {
            "kind": "inspect-missing-followup-task",
            "summary": (
                f"Inspect the source task and either recreate or relink the missing follow-up task for {target} "
                "before relying on the scheduled follow-up state."
            ),
            "command": inspect_command,
            "session_key": session_key,
        }
    if bool(planning.get("overdue_on_materialize")):
        return {
            "kind": "inspect-overdue-materialization",
            "summary": (
                f"Inspect the source task and confirm the late-materialized follow-up for {target} is still valid, "
                "or reschedule it explicitly with a fresh due time."
            ),
            "command": inspect_command,
            "session_key": session_key,
        }
    if _planning_timeout_detected(planning):
        return {
            "kind": "inspect-planner-timeout",
            "summary": (
                "Inspect the source task and decide whether to recreate the planner-owned follow-up "
                "or ask for the delayed part again after the planner timeout."
            ),
            "command": inspect_command,
            "session_key": session_key,
        }
    if str(planning.get("anomaly") or "").strip():
        return {
            "kind": "inspect-planning-anomaly",
            "summary": "Inspect the planning anomaly before relying on the follow-up state.",
            "command": inspect_command,
            "session_key": session_key,
        }
    if bool(planning.get("overdue_followup")):
        return {
            "kind": "inspect-overdue-followup",
            "summary": "Inspect the overdue planned follow-up and recover the continuation runner or reschedule it explicitly.",
            "command": inspect_command,
            "session_key": session_key,
        }
    if bool(planning.get("planning_pending")):
        return {
            "kind": "inspect-pending-plan",
            "summary": "Inspect the pending planning path and confirm it materializes before finalize.",
            "command": inspect_command,
            "session_key": session_key,
        }
    return {
        "kind": "none",
        "summary": "No planning recovery action suggested.",
        "command": None,
        "session_key": session_key,
    }


def _planning_recovery_priority(action: dict[str, object]) -> tuple[int, str, str]:
    kind = str(action.get("kind") or "")
    priority = {
        "inspect-promise-without-task": 0,
        "inspect-missing-followup-task": 1,
        "inspect-overdue-materialization": 2,
        "inspect-planner-timeout": 3,
        "inspect-planning-anomaly": 4,
        "inspect-overdue-followup": 5,
        "inspect-pending-plan": 6,
    }.get(kind, 99)
    return (
        priority,
        str(action.get("session_key") or ""),
        str(action.get("command") or ""),
    )


def _planning_main_user_content_mode_priority(item: tuple[str, int]) -> tuple[int, int, str]:
    mode, count = item
    priority = {
        "none": 0,
        "immediate-summary": 1,
        "full-answer": 2,
    }.get(mode, 99)
    return (-count, priority, mode)


def _rate(count: int, total: int) -> Optional[float]:
    if total <= 0:
        return None
    return round(count / total, 4)


def build_planning_health_summary(
    tasks: list[dict[str, object]],
    *,
    sample_size: int = PLANNING_HEALTH_SAMPLE_SIZE,
) -> dict[str, object]:
    candidates: list[dict[str, object]] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        planning = task.get("planning") if isinstance(task.get("planning"), dict) else _build_planning_summary(task)
        if not isinstance(planning, dict) or not bool(planning.get("tool_path_used")):
            continue
        if not _planning_health_candidate(planning):
            continue
        candidates.append(
            {
                "task_id": str(task.get("task_id") or ""),
                "updated_at": str(task.get("updated_at") or task.get("created_at") or ""),
                "planning": planning,
            }
        )
    recent = sorted(candidates, key=lambda item: (item["updated_at"], item["task_id"]), reverse=True)[:sample_size]
    sample_task_count = len(recent)
    success_count = sum(1 for item in recent if _planning_success(item["planning"]))
    timeout_count = sum(1 for item in recent if _planning_timeout_detected(item["planning"]))
    tool_call_completion_count = sum(1 for item in recent if _planning_tool_path_completed(item["planning"]))
    promise_without_task_count = sum(1 for item in recent if bool(item["planning"].get("promise_without_task")))
    followup_task_missing_count = sum(1 for item in recent if bool(item["planning"].get("followup_task_missing")))
    overdue_on_materialize_count = sum(1 for item in recent if bool(item["planning"].get("overdue_on_materialize")))
    if sample_task_count == 0:
        status = "unknown"
        primary_reason = "no-recent-planning-sample"
    elif promise_without_task_count > 0:
        status = "error"
        primary_reason = "promise-without-task-present"
    elif followup_task_missing_count > 0:
        status = "error"
        primary_reason = "followup-task-missing-present"
    elif overdue_on_materialize_count > 0:
        status = "warn"
        primary_reason = "overdue-materialization-observed"
    elif timeout_count > 0:
        status = "warn"
        primary_reason = "planner-timeout-observed"
    elif tool_call_completion_count < sample_task_count:
        status = "warn"
        primary_reason = "tool-path-not-fully-closed"
    else:
        status = "ok"
        primary_reason = "recent-planning-sample-healthy"
    return {
        "status": status,
        "primary_reason": primary_reason,
        "sample_task_count": sample_task_count,
        "sample_size": sample_size,
        "success_count": success_count,
        "timeout_count": timeout_count,
        "tool_call_completion_count": tool_call_completion_count,
        "promise_without_task_count": promise_without_task_count,
        "followup_task_missing_count": followup_task_missing_count,
        "overdue_on_materialize_count": overdue_on_materialize_count,
        "success_rate": _rate(success_count, sample_task_count),
        "timeout_rate": _rate(timeout_count, sample_task_count),
        "tool_call_completion_rate": _rate(tool_call_completion_count, sample_task_count),
        "promise_without_task_rate": _rate(promise_without_task_count, sample_task_count),
        "followup_task_missing_rate": _rate(followup_task_missing_count, sample_task_count),
        "overdue_on_materialize_rate": _rate(overdue_on_materialize_count, sample_task_count),
        "sample_task_ids": [item["task_id"] for item in recent],
    }


def _load_archived_tasks(*, paths: TaskPaths) -> list[dict[str, object]]:
    tasks: list[dict[str, object]] = []
    for archived_path in sorted(paths.archive_dir.glob("*.json")):
        payload = _load_json_if_exists(archived_path)
        if isinstance(payload, dict):
            tasks.append(payload)
    return tasks


def _build_same_session_routing_summary(task: dict[str, object]) -> Optional[dict[str, object]]:
    meta = task.get("meta") if isinstance(task.get("meta"), dict) else {}
    routing = meta.get("same_session_routing") if isinstance(meta.get("same_session_routing"), dict) else None
    if not routing:
        return None
    return dict(routing)


def _queue_sort_key(status: dict[str, object]) -> tuple[int, str, str]:
    state = str(status["status"])
    if state == STATUS_RUNNING:
        priority = 0
    elif state == STATUS_QUEUED:
        priority = 1
    elif state == STATUS_RECEIVED:
        priority = 2
    else:
        priority = 3
    anchor = str(status["started_at"] or status["created_at"] or "")
    return (priority, anchor, str(status["task_id"]))


def build_queue_snapshot(
    *,
    paths: Optional[TaskPaths] = None,
    config: Optional[TaskSystemConfig] = None,
    config_path: Optional[Path] = None,
    agent_id: Optional[str] = None,
) -> dict[str, object]:
    resolved_paths = _resolve_paths(paths, config=config, config_path=config_path)
    store = TaskStore(paths=resolved_paths)
    queue_statuses = ACTIVE_STATUSES | OBSERVED_STATUSES
    statuses = [
        status
        for status in (_build_base_status_summary(path.stem, paths=resolved_paths) for path in store.list_inflight())
        if str(status["status"]) in queue_statuses and (agent_id is None or status["agent_id"] == agent_id)
    ]
    ordered = sorted(statuses, key=_queue_sort_key)
    items: list[dict[str, object]] = []
    running_count = sum(1 for status in ordered if status["status"] == STATUS_RUNNING)
    queued_count = sum(1 for status in ordered if status["status"] in {STATUS_QUEUED, STATUS_RECEIVED})
    for index, status in enumerate(ordered, start=1):
        items.append(
            {
                "task_id": status["task_id"],
                "agent_id": status["agent_id"],
                "session_key": status["session_key"],
                "status": status["status"],
                "position": index,
                "ahead_count": index - 1,
                "is_running": status["status"] == STATUS_RUNNING,
                "task_label": status["task_label"],
            }
        )
    return {
        "active_count": len(ordered),
        "running_count": running_count,
        "queued_count": queued_count,
        "items": items,
    }


def build_status_summary(
    task_id: str,
    *,
    paths: Optional[TaskPaths] = None,
    config: Optional[TaskSystemConfig] = None,
    config_path: Optional[Path] = None,
) -> dict[str, object]:
    resolved_paths = _resolve_paths(paths, config=config, config_path=config_path)
    task = _build_base_status_summary(task_id, paths=resolved_paths)
    queue_snapshot = build_queue_snapshot(paths=resolved_paths)
    queue_entry = next((entry for entry in queue_snapshot["items"] if entry["task_id"] == task["task_id"]), None)
    queue_summary = {
        "task_id": task["task_id"],
        "position": queue_entry["position"] if queue_entry else None,
        "ahead_count": queue_entry["ahead_count"] if queue_entry else 0,
        "is_running": queue_entry["is_running"] if queue_entry else False,
        "active_count": queue_snapshot["active_count"],
        "running_count": queue_snapshot["running_count"],
        "queued_count": queue_snapshot["queued_count"],
    }
    task["queue"] = queue_summary
    projection = project_user_facing_status(task)
    task["user_facing_status_code"] = projection["code"]
    task["user_facing_status"] = projection["label"]
    task["user_facing_status_family"] = projection["family"]
    task["planning"] = _build_planning_summary(task, paths=resolved_paths)
    task["planning"]["recovery_action"] = _build_planning_recovery_action(task, task["planning"])
    task["same_session_routing"] = _build_same_session_routing_summary(task)
    return task


def list_inflight_statuses(
    *,
    paths: Optional[TaskPaths] = None,
    config: Optional[TaskSystemConfig] = None,
    config_path: Optional[Path] = None,
) -> list[dict[str, object]]:
    resolved_paths = _resolve_paths(paths, config=config, config_path=config_path)
    store = TaskStore(paths=resolved_paths)
    return [build_status_summary(path.stem, paths=resolved_paths) for path in store.list_inflight()]


def build_system_overview(
    *,
    paths: Optional[TaskPaths] = None,
    config: Optional[TaskSystemConfig] = None,
    config_path: Optional[Path] = None,
) -> dict[str, object]:
    resolved_paths = _resolve_paths(paths, config=config, config_path=config_path)
    store = TaskStore(paths=resolved_paths)
    inflight_statuses = [build_status_summary(path.stem, paths=resolved_paths) for path in store.list_inflight()]

    inflight_counts = Counter(str(status["status"]) for status in inflight_statuses)
    delivery_counts = Counter(str(status["delivery"]["state"]) for status in inflight_statuses)
    planning_items = [status.get("planning") for status in inflight_statuses if isinstance(status.get("planning"), dict)]
    planning_anomaly_counts = Counter(
        str(item.get("anomaly") or "")
        for item in planning_items
        if str(item.get("anomaly") or "").strip()
    )
    promise_guard_counts = Counter(
        str(item.get("promise_guard_status") or "")
        for item in planning_items
        if str(item.get("promise_guard_status") or "").strip()
    )
    plan_status_counts = Counter(
        str(item.get("plan_status") or "")
        for item in planning_items
        if str(item.get("plan_status") or "").strip()
    )
    main_user_content_mode_counts = Counter(
        str(item.get("main_user_content_mode") or "")
        for item in planning_items
        if str(item.get("main_user_content_mode") or "").strip()
    )
    active_stale_delivery_task_count = sum(
        1 for status in inflight_statuses if status["delivery"]["stale_intermediate_exists"]
    )
    active_stale_delivery_artifact_count = sum(
        int(status["delivery"]["stale_intermediate_count"]) for status in inflight_statuses
    )

    finalized_task_ids: set[str] = set()
    for directory in FINAL_INSTRUCTION_DIRS:
        base = resolved_paths.data_dir / directory
        if not base.exists():
            continue
        for path in base.glob("*.json"):
            finalized_task_ids.add(path.stem)
    stale_delivery_task_count = 0
    stale_delivery_artifact_count = 0
    for task_id in finalized_task_ids:
        has_final_artifact = any(_artifact_path(resolved_paths, directory, task_id).exists() for directory in FINAL_INSTRUCTION_DIRS)
        if not has_final_artifact:
            continue
        stale_count = sum(
            1 for directory in INTERMEDIATE_DELIVERY_DIRS if _artifact_path(resolved_paths, directory, task_id).exists()
        )
        if stale_count > 0:
            stale_delivery_task_count += 1
            stale_delivery_artifact_count += stale_count

    archived_payloads = _load_archived_tasks(paths=resolved_paths)
    archived_counts: Counter[str] = Counter()
    for archived_payload in archived_payloads:
        archived_status = archived_payload.get("status")
        if archived_status:
            archived_counts[str(archived_status)] += 1
    planning_health = build_planning_health_summary([*inflight_statuses, *archived_payloads])
    planning_recovery_actions: list[dict[str, object]] = []
    for item in inflight_statuses:
        if (
            isinstance(item.get("planning"), dict)
            and isinstance(item["planning"].get("recovery_action"), dict)
            and str(item["planning"]["recovery_action"].get("kind") or "") != "none"
        ):
            planning_recovery_actions.append(item["planning"]["recovery_action"])
    for archived_payload in archived_payloads:
        if not isinstance(archived_payload, dict):
            continue
        archived_planning = _build_planning_summary(archived_payload, paths=resolved_paths)
        archived_recovery_action = _build_planning_recovery_action(archived_payload, archived_planning)
        if str(archived_recovery_action.get("kind") or "") != "none":
            planning_recovery_actions.append(archived_recovery_action)
    planning_recovery_actions = sorted(planning_recovery_actions, key=_planning_recovery_priority)
    planning_recovery_counts = Counter(
        str(action.get("kind") or "")
        for action in planning_recovery_actions
        if str(action.get("kind") or "").strip()
    )

    return {
        "active_task_count": len(inflight_statuses),
        "active_status_counts": dict(sorted(inflight_counts.items())),
        "active_delivery_counts": dict(sorted(delivery_counts.items())),
        "active_stale_delivery_task_count": active_stale_delivery_task_count,
        "active_stale_delivery_artifact_count": active_stale_delivery_artifact_count,
        "stale_delivery_task_count": stale_delivery_task_count,
        "stale_delivery_artifact_count": stale_delivery_artifact_count,
        "archived_task_count": sum(archived_counts.values()),
        "archived_status_counts": dict(sorted(archived_counts.items())),
        "outbox_count": len(list((resolved_paths.data_dir / "outbox").glob("*.json"))),
        "sent_count": len(list((resolved_paths.data_dir / "sent").glob("*.json"))),
        "delivery_ready_count": len(list((resolved_paths.data_dir / "delivery-ready").glob("*.json"))),
        "send_instruction_count": len(list((resolved_paths.data_dir / "send-instructions").glob("*.json"))),
        "processed_instruction_count": len(list((resolved_paths.data_dir / "processed-instructions").glob("*.json"))),
        "failed_instruction_count": len(list((resolved_paths.data_dir / "failed-instructions").glob("*.json"))),
        "resolved_failed_instruction_count": len(list((resolved_paths.data_dir / "resolved-failed-instructions").glob("*.json"))),
        "dispatch_result_count": len(list((resolved_paths.data_dir / "dispatch-results").glob("*.json"))),
        "planning": {
            "tool_path_task_count": sum(1 for item in planning_items if bool(item.get("tool_path_used"))),
            "planning_expected_task_count": sum(1 for item in planning_items if bool(item.get("planning_expected"))),
            "planning_pending_task_count": sum(1 for item in planning_items if bool(item.get("planning_pending"))),
            "future_first_task_count": sum(1 for item in planning_items if str(item.get("main_user_content_mode") or "") == "none"),
            "promise_guard_armed_count": sum(1 for item in planning_items if bool(item.get("promise_guard_armed"))),
            "promise_without_task_count": sum(1 for item in planning_items if bool(item.get("promise_without_task"))),
            "followup_task_missing_count": sum(1 for item in planning_items if bool(item.get("followup_task_missing"))),
            "overdue_followup_count": sum(1 for item in planning_items if bool(item.get("overdue_followup"))),
            "overdue_on_materialize_count": sum(1 for item in planning_items if bool(item.get("overdue_on_materialize"))),
            "anomaly_counts": dict(sorted(planning_anomaly_counts.items())),
            "promise_guard_status_counts": dict(sorted(promise_guard_counts.items())),
            "plan_status_counts": dict(sorted(plan_status_counts.items())),
            "main_user_content_mode_counts": dict(sorted(main_user_content_mode_counts.items())),
            "primary_main_user_content_mode": (
                sorted(main_user_content_mode_counts.items(), key=_planning_main_user_content_mode_priority)[0][0]
                if main_user_content_mode_counts
                else None
            ),
            "recovery_action_counts": dict(sorted(planning_recovery_counts.items())),
            "primary_recovery_action": planning_recovery_actions[0] if planning_recovery_actions else None,
            "health": planning_health,
        },
        "active_tasks": inflight_statuses,
    }


def render_status_markdown(
    task_id: str,
    *,
    paths: Optional[TaskPaths] = None,
    config: Optional[TaskSystemConfig] = None,
    config_path: Optional[Path] = None,
) -> str:
    status = build_status_summary(task_id, paths=paths, config=config, config_path=config_path)
    lines = [
        f"# Task Status: {status['task_id']}",
        "",
        f"- label: {status['task_label']}",
        f"- agent: {status['agent_id']}",
        f"- status: {status['status']}",
        f"- user_facing_status_code: {status['user_facing_status_code']}",
        f"- user_facing_status: {status['user_facing_status']}",
        f"- session_key: {status['session_key']}",
        f"- channel: {status['channel']}",
        f"- chat_id: {status['chat_id']}",
        f"- created_at: {status['created_at']}",
        f"- started_at: {status['started_at']}",
        f"- updated_at: {status['updated_at']}",
        f"- last_user_visible_update_at: {status['last_user_visible_update_at']}",
        f"- last_internal_touch_at: {status['last_internal_touch_at']}",
        f"- last_monitor_notify_at: {status['last_monitor_notify_at']}",
        f"- notify_count: {status['notify_count']}",
        f"- queue.position: {status['queue']['position']}",
        f"- queue.ahead_count: {status['queue']['ahead_count']}",
        f"- queue.is_running: {status['queue']['is_running']}",
        f"- queue.active_count: {status['queue']['active_count']}",
        f"- queue.running_count: {status['queue']['running_count']}",
        f"- queue.queued_count: {status['queue']['queued_count']}",
        f"- delivery.state: {status['delivery']['state']}",
        f"- delivery.outbox_exists: {status['delivery']['outbox_exists']}",
        f"- delivery.sent_exists: {status['delivery']['sent_exists']}",
        f"- delivery.delivery_ready_exists: {status['delivery']['delivery_ready_exists']}",
        f"- delivery.send_instruction_exists: {status['delivery']['send_instruction_exists']}",
        f"- delivery.processed_instruction_exists: {status['delivery']['processed_instruction_exists']}",
        f"- delivery.failed_instruction_exists: {status['delivery']['failed_instruction_exists']}",
        f"- delivery.dispatch_result_exists: {status['delivery']['dispatch_result_exists']}",
        f"- delivery.stale_intermediate_exists: {status['delivery']['stale_intermediate_exists']}",
        f"- delivery.stale_intermediate_count: {status['delivery']['stale_intermediate_count']}",
    ]
    if status["delivery"]["dispatch_action"]:
        lines.append(f"- delivery.dispatch_action: {status['delivery']['dispatch_action']}")
    if status["delivery"]["dispatch_reason"]:
        lines.append(f"- delivery.dispatch_reason: {status['delivery']['dispatch_reason']}")
    if status["delivery"]["dispatch_execution_context"]:
        lines.append(
            f"- delivery.dispatch_execution_context: {status['delivery']['dispatch_execution_context']}"
        )
    if status["delivery"]["dispatch_requested_execution_context"]:
        lines.append(
            f"- delivery.dispatch_requested_execution_context: {status['delivery']['dispatch_requested_execution_context']}"
        )
    if status["delivery"]["dispatch_exit_code"] is not None:
        lines.append(f"- delivery.dispatch_exit_code: {status['delivery']['dispatch_exit_code']}")
    if status["block_reason"]:
        lines.append(f"- block_reason: {status['block_reason']}")
    if status["failure_reason"]:
        lines.append(f"- failure_reason: {status['failure_reason']}")
    planning = status.get("planning")
    if isinstance(planning, dict) and planning.get("tool_path_used"):
        lines.append(f"- planning.tool_path_used: {planning['tool_path_used']}")
        lines.append(f"- planning.plan_status: {planning.get('plan_status')}")
        lines.append(f"- planning.followup_due_at: {planning.get('followup_due_at')}")
        lines.append(f"- planning.followup_task_id: {planning.get('followup_task_id')}")
        lines.append(f"- planning.followup_task_missing: {planning.get('followup_task_missing')}")
        lines.append(f"- planning.promise_guard_status: {planning.get('promise_guard_status')}")
        lines.append(f"- planning.overdue_followup: {planning.get('overdue_followup')}")
        lines.append(f"- planning.overdue_on_materialize: {planning.get('overdue_on_materialize')}")
        lines.append(f"- planning.promise_without_task: {planning.get('promise_without_task')}")
        if planning.get("anomaly"):
            lines.append(f"- planning.anomaly: {planning['anomaly']}")
        recovery_action = planning.get("recovery_action") if isinstance(planning.get("recovery_action"), dict) else None
        if isinstance(recovery_action, dict):
            lines.append(f"- planning.recovery_action_kind: {recovery_action.get('kind')}")
            lines.append(f"- planning.recovery_action_command: {recovery_action.get('command')}")
    same_session_routing = status.get("same_session_routing")
    if isinstance(same_session_routing, dict):
        lines.append(f"- same_session_routing.routing_status: {same_session_routing.get('routing_status')}")
        lines.append(f"- same_session_routing.same_session_followup: {same_session_routing.get('same_session_followup')}")
        lines.append(f"- same_session_routing.classification: {same_session_routing.get('classification')}")
        lines.append(
            f"- same_session_routing.execution_decision: {same_session_routing.get('execution_decision')}"
        )
        lines.append(f"- same_session_routing.reason_code: {same_session_routing.get('reason_code')}")
    return "\n".join(lines) + "\n"


def render_inflight_markdown(
    *,
    paths: Optional[TaskPaths] = None,
    config: Optional[TaskSystemConfig] = None,
    config_path: Optional[Path] = None,
) -> str:
    statuses = list_inflight_statuses(paths=paths, config=config, config_path=config_path)
    if not statuses:
        return "# Active Tasks\n\n- none\n"

    lines = ["# Active Tasks", ""]
    for status in statuses:
        lines.append(
            f"- {status['task_id']} | {status['status']} | user_status={status['user_facing_status']} | delivery={status['delivery']['state']} | {status['task_label']}"
        )
    return "\n".join(lines) + "\n"


def render_overview_markdown(
    *,
    paths: Optional[TaskPaths] = None,
    config: Optional[TaskSystemConfig] = None,
    config_path: Optional[Path] = None,
) -> str:
    overview = build_system_overview(paths=paths, config=config, config_path=config_path)
    lines = [
        "# Task System Overview",
        "",
        f"- active_task_count: {overview['active_task_count']}",
        f"- archived_task_count: {overview['archived_task_count']}",
        f"- outbox_count: {overview['outbox_count']}",
        f"- sent_count: {overview['sent_count']}",
        f"- delivery_ready_count: {overview['delivery_ready_count']}",
        f"- send_instruction_count: {overview['send_instruction_count']}",
        f"- processed_instruction_count: {overview['processed_instruction_count']}",
        f"- failed_instruction_count: {overview['failed_instruction_count']}",
        f"- resolved_failed_instruction_count: {overview['resolved_failed_instruction_count']}",
        f"- dispatch_result_count: {overview['dispatch_result_count']}",
        f"- active_stale_delivery_task_count: {overview['active_stale_delivery_task_count']}",
        f"- active_stale_delivery_artifact_count: {overview['active_stale_delivery_artifact_count']}",
        f"- stale_delivery_task_count: {overview['stale_delivery_task_count']}",
        f"- stale_delivery_artifact_count: {overview['stale_delivery_artifact_count']}",
    ]
    if overview["active_status_counts"]:
        lines.append(f"- active_status_counts: {json.dumps(overview['active_status_counts'], ensure_ascii=False)}")
    if overview["active_delivery_counts"]:
        lines.append(f"- active_delivery_counts: {json.dumps(overview['active_delivery_counts'], ensure_ascii=False)}")
    if overview["archived_status_counts"]:
        lines.append(f"- archived_status_counts: {json.dumps(overview['archived_status_counts'], ensure_ascii=False)}")
    planning = overview.get("planning")
    if isinstance(planning, dict):
        lines.append(f"- planning_tool_path_task_count: {planning['tool_path_task_count']}")
        lines.append(f"- planning_expected_task_count: {planning['planning_expected_task_count']}")
        lines.append(f"- planning_pending_task_count: {planning['planning_pending_task_count']}")
        lines.append(f"- planning_future_first_task_count: {planning['future_first_task_count']}")
        lines.append(f"- planning_promise_without_task_count: {planning['promise_without_task_count']}")
        lines.append(f"- planning_followup_task_missing_count: {planning['followup_task_missing_count']}")
        lines.append(f"- planning_overdue_followup_count: {planning['overdue_followup_count']}")
        lines.append(f"- planning_overdue_on_materialize_count: {planning['overdue_on_materialize_count']}")
        lines.append(
            f"- planning_primary_main_user_content_mode: {planning.get('primary_main_user_content_mode') or 'none'}"
        )
        health = planning.get("health") if isinstance(planning.get("health"), dict) else None
        if isinstance(health, dict):
            lines.append(f"- planning_health_status: {health['status']}")
            lines.append(f"- planning_health_primary_reason: {health['primary_reason']}")
            lines.append(f"- planning_health_sample_task_count: {health['sample_task_count']}")
            lines.append(f"- planning_health_success_rate: {health['success_rate']}")
            lines.append(f"- planning_health_timeout_rate: {health['timeout_rate']}")
            lines.append(f"- planning_health_tool_call_completion_rate: {health['tool_call_completion_rate']}")
            lines.append(f"- planning_health_promise_without_task_rate: {health['promise_without_task_rate']}")
            lines.append(f"- planning_health_followup_task_missing_rate: {health['followup_task_missing_rate']}")
            lines.append(f"- planning_health_overdue_on_materialize_rate: {health['overdue_on_materialize_rate']}")
        primary_recovery_action = (
            planning.get("primary_recovery_action")
            if isinstance(planning.get("primary_recovery_action"), dict)
            else None
        )
        if isinstance(primary_recovery_action, dict):
            lines.append(f"- planning_primary_recovery_action_kind: {primary_recovery_action.get('kind')}")
            lines.append(f"- planning_primary_recovery_action_command: {primary_recovery_action.get('command')}")
        if planning.get("recovery_action_counts"):
            lines.append(
                f"- planning_recovery_action_counts: {json.dumps(planning['recovery_action_counts'], ensure_ascii=False)}"
            )
        if planning["anomaly_counts"]:
            lines.append(f"- planning_anomaly_counts: {json.dumps(planning['anomaly_counts'], ensure_ascii=False)}")
        if planning.get("main_user_content_mode_counts"):
            lines.append(
                f"- planning_main_user_content_mode_counts: {json.dumps(planning['main_user_content_mode_counts'], ensure_ascii=False)}"
            )
    if overview["active_tasks"]:
        lines.append("")
        lines.append("## Active Tasks")
        lines.append("")
        for status in overview["active_tasks"]:
            lines.append(
                f"- {status['task_id']} | {status['status']} | user_status={status['user_facing_status']} | pos={status['queue']['position']} | delivery={status['delivery']['state']} | {status['task_label']}"
            )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    usage = (
        "usage: task_status.py <task_id> [--json]\n"
        "   or: task_status.py --list [--json]\n"
        "   or: task_status.py --overview [--json]\n"
        "   or: task_status.py --json"
    )
    if not args or args == ["--help"] or args == ["-h"]:
        print(usage)
        raise SystemExit(0)

    if args[0] == "--json":
        print(json.dumps(list_inflight_statuses(), ensure_ascii=False, indent=2))
        raise SystemExit(0)

    if args[0] == "--list":
        if len(args) > 1 and args[1] == "--json":
            print(json.dumps(list_inflight_statuses(), ensure_ascii=False, indent=2))
        else:
            print(render_inflight_markdown(), end="")
        raise SystemExit(0)

    if args[0] == "--overview":
        if len(args) > 1 and args[1] == "--json":
            print(json.dumps(build_system_overview(), ensure_ascii=False, indent=2))
        else:
            print(render_overview_markdown(), end="")
        raise SystemExit(0)

    task_id = args[0]
    if len(args) > 1 and args[1] == "--json":
        print(json.dumps(build_status_summary(task_id), ensure_ascii=False, indent=2))
    else:
        print(render_status_markdown(task_id), end="")
