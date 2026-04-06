#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from openclaw_bridge import (
    OpenClawInboundContext,
    _estimate_wait_seconds,
    _queue_metrics,
    record_blocked,
    record_completed,
    record_failed,
    record_progress,
    register_inbound_task,
)
from main_ops import auto_resume_watchdog_blocked_main_tasks_if_safe, cancel_main_queue_task, get_main_continuity_summary
from silence_monitor import process_overdue_tasks
from task_config import load_task_system_config
from task_state import TaskStore, now_iso
from task_status import list_inflight_statuses
from taskmonitor_state import get_taskmonitor_enabled, set_taskmonitor_enabled
from main_task_adapter import resume_main_task
from user_status import USER_STATUS_PENDING_START, USER_STATUS_QUEUED, USER_STATUS_RECEIVED, project_user_facing_status


GENERIC_SUCCESS_SUMMARIES = {
    "openai-codex-responses",
    "agent run completed",
    "assistant",
}


def _build_control_plane_message(
    *,
    kind: str,
    event_name: str,
    priority: str,
    text: str,
    task: Optional[Any] = None,
    session_key: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    message: dict[str, Any] = {
        "schema": "openclaw.task-system.control-plane.v1",
        "kind": kind,
        "event_name": event_name,
        "priority": priority,
        "text": text,
    }
    if task is not None:
        message["task_id"] = task.task_id
        message["task_status"] = task.status
        message["session_key"] = task.session_key
    elif session_key:
        message["session_key"] = session_key
    if metadata:
        message["metadata"] = metadata
    return message


def _build_terminal_message_text(task: Any, *, success: bool) -> str:
    summary = str(task.meta.get("result_summary") or "").strip()
    if success:
        return f"当前任务已完成。{summary}" if summary else "当前任务已完成。"
    failure_reason = str(getattr(task, "failure_reason", "") or task.meta.get("failure_reason") or "").strip()
    if failure_reason:
        return f"当前任务已失败：{failure_reason}"
    return "当前任务已失败。"


def _find_inflight_status_entry(
    task_id: str,
    *,
    config_path: Optional[Path] = None,
) -> Optional[dict[str, Any]]:
    for status in list_inflight_statuses(config_path=config_path):
        if str(status.get("task_id") or "") == task_id:
            return status
    return None


def load_payload(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_payload_from_stdin() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    return json.loads(raw)


def load_payload_for_command(command: str, payload_source: str) -> dict[str, Any]:
    if payload_source != "-":
        return load_payload(Path(payload_source).expanduser().resolve())
    try:
        return load_payload_from_stdin()
    except KeyboardInterrupt:
        if command == "claim-due-continuations":
            return {}
        raise


def _build_context(payload: dict[str, Any]) -> OpenClawInboundContext:
    return OpenClawInboundContext(
        agent_id=payload["agent_id"],
        session_key=payload["session_key"],
        channel=payload["channel"],
        account_id=payload.get("account_id"),
        chat_id=payload["chat_id"],
        user_id=payload.get("user_id"),
        user_request=payload["user_request"],
        reply_to_id=payload.get("reply_to_id") or payload.get("replyToId"),
        thread_id=payload.get("thread_id") or payload.get("threadId"),
        estimated_steps=payload.get("estimated_steps"),
        touches_multiple_files=bool(payload.get("touches_multiple_files", False)),
        involves_delegation=bool(payload.get("involves_delegation", False)),
        requires_external_wait=bool(payload.get("requires_external_wait", False)),
        needs_verification=bool(payload.get("needs_verification", False)),
    )


def register_from_payload(
    payload: dict[str, Any],
    *,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    decision = register_inbound_task(
        _build_context(payload),
        config_path=config_path,
        observe_only=bool(payload.get("observe_only", False)),
    )
    serialized = decision.to_payload()
    return {
        "should_register_task": serialized["should_register_task"],
        "task_id": serialized["task_id"],
        "classification_reason": serialized["classification_reason"],
        "confidence": serialized["confidence"],
        "task_status": serialized["task_status"],
        "queue_position": serialized["queue_position"],
        "ahead_count": serialized["ahead_count"],
        "active_count": serialized["active_count"],
        "running_count": serialized["running_count"],
        "queued_count": serialized["queued_count"],
        "estimated_wait_seconds": serialized["estimated_wait_seconds"],
        "continuation_due_at": serialized["continuation_due_at"],
        "register_decision": serialized,
    }


def activate_latest_from_payload(
    payload: dict[str, Any],
    *,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    runtime_config = load_task_system_config(config_path=config_path)
    store = TaskStore(paths=runtime_config.build_paths())
    requested_task_id = str(payload.get("task_id") or "").strip()
    if requested_task_id:
        try:
            requested = store.load_task(requested_task_id, allow_archive=False)
        except FileNotFoundError:
            requested = None
        if requested and requested.agent_id == payload["agent_id"] and requested.session_key == payload["session_key"]:
            if requested.status in {"queued", "running"}:
                return {"updated": True, "task": requested.to_dict(), "reason": "requested-active-task"}
            if requested.status == "received":
                claimed = store.claim_execution_slot(requested.task_id)
                return {"updated": True, "task": claimed.to_dict(), "reason": "promoted-requested-task"}
    active = store.find_latest_active_task(
        agent_id=payload["agent_id"],
        session_key=payload["session_key"],
    )
    observed = store.find_latest_observed_task(
        agent_id=payload["agent_id"],
        session_key=payload["session_key"],
    )
    if observed and (not active or observed.updated_at >= active.updated_at):
        claimed = store.claim_execution_slot(observed.task_id)
        return {"updated": True, "task": claimed.to_dict(), "reason": "promoted-observed-task"}
    if active:
        return {"updated": True, "task": active.to_dict(), "reason": "existing-active-task"}
    if not observed:
        return {"updated": False, "reason": "no-observed-task"}


def _resolve_existing_task(store: TaskStore, task_id: str) -> Any:
    return store.load_task(task_id, allow_archive=False)


def _find_source_task_id_for_plan(store: TaskStore, plan_id: str) -> Optional[str]:
    for task_file in sorted(store.paths.inflight_dir.glob("*.json")):
        try:
            payload = json.loads(task_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
        plan = meta.get("tool_followup_plan") if isinstance(meta.get("tool_followup_plan"), dict) else {}
        if str(plan.get("plan_id") or "").strip() == plan_id:
            return str(payload.get("task_id") or "").strip() or None
    return None


def create_followup_plan_from_payload(
    payload: dict[str, Any],
    *,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    runtime_config = load_task_system_config(config_path=config_path)
    store = TaskStore(paths=runtime_config.build_paths())
    source_task_id = str(payload.get("source_task_id") or "").strip()
    if not source_task_id:
        return {"accepted": False, "reason": "missing-source-task-id"}
    try:
        source_task = _resolve_existing_task(store, source_task_id)
    except FileNotFoundError:
        return {"accepted": False, "reason": "source-task-not-found"}

    followup_kind = str(payload.get("followup_kind") or payload.get("kind") or "delayed-reply").strip()
    followup_due_at = str(payload.get("followup_due_at") or payload.get("due_at") or "").strip()
    followup_message = str(payload.get("followup_message") or payload.get("reply_text") or "").strip()
    reply_to_id = str(payload.get("reply_to_id") or payload.get("replyToId") or "").strip()
    thread_id = str(payload.get("thread_id") or payload.get("threadId") or "").strip()
    if not reply_to_id:
        reply_to_id = str(source_task.meta.get("source_reply_to_id") or "").strip()
    if not thread_id:
        thread_id = str(source_task.meta.get("source_thread_id") or "").strip()
    if not followup_due_at:
        return {"accepted": False, "reason": "missing-followup-due-at"}
    if not followup_message:
        return {"accepted": False, "reason": "missing-followup-message"}
    try:
        datetime.fromisoformat(followup_due_at)
    except ValueError:
        return {"accepted": False, "reason": "invalid-followup-due-at"}

    plan_id = str(payload.get("plan_id") or "").strip() or f"plan_{uuid4().hex}"
    plan = {
        "plan_id": plan_id,
        "source_task_id": source_task.task_id,
        "status": "planned",
        "followup_kind": followup_kind,
        "followup_due_at": followup_due_at,
        "followup_message": followup_message,
        "dependency": str(payload.get("dependency") or "after-source-task-finalized"),
        "original_time_expression": str(payload.get("original_time_expression") or "").strip() or None,
        "reply_to_id": reply_to_id or None,
        "thread_id": thread_id or None,
        "created_at": now_iso(),
    }
    source_task.meta["tool_followup_plan"] = plan
    saved = store.save_task(source_task)
    return {
        "accepted": True,
        "plan_id": plan_id,
        "source_task_id": saved.task_id,
        "runtime_contract": {
            "followup_kind": followup_kind,
            "dependency": plan["dependency"],
            "followup_due_at": followup_due_at,
        },
    }


def attach_promise_guard_from_payload(
    payload: dict[str, Any],
    *,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    runtime_config = load_task_system_config(config_path=config_path)
    store = TaskStore(paths=runtime_config.build_paths())
    source_task_id = str(payload.get("source_task_id") or "").strip()
    if not source_task_id:
        return {"armed": False, "reason": "missing-source-task-id"}
    try:
        source_task = _resolve_existing_task(store, source_task_id)
    except FileNotFoundError:
        return {"armed": False, "reason": "source-task-not-found"}

    guard_id = str(payload.get("guard_id") or "").strip() or f"guard_{uuid4().hex}"
    source_task.meta["planning_promise_guard"] = {
        "guard_id": guard_id,
        "promise_type": str(payload.get("promise_type") or "delayed-followup"),
        "expected_by_finalize": bool(payload.get("expected_by_finalize", True)),
        "status": "armed",
        "armed_at": now_iso(),
    }
    saved = store.save_task(source_task)
    return {
        "armed": True,
        "guard_id": guard_id,
        "source_task_id": saved.task_id,
    }


def schedule_followup_from_plan_from_payload(
    payload: dict[str, Any],
    *,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    runtime_config = load_task_system_config(config_path=config_path)
    store = TaskStore(paths=runtime_config.build_paths())
    plan_id = str(payload.get("plan_id") or "").strip()
    source_task_id = str(payload.get("source_task_id") or "").strip()
    if not source_task_id and plan_id:
        source_task_id = _find_source_task_id_for_plan(store, plan_id) or ""
    if not source_task_id:
        return {"scheduled": False, "reason": "missing-source-task-id"}
    try:
        source_task = _resolve_existing_task(store, source_task_id)
    except FileNotFoundError:
        return {"scheduled": False, "reason": "source-task-not-found"}

    plan = source_task.meta.get("tool_followup_plan")
    if not isinstance(plan, dict):
        return {"scheduled": False, "reason": "missing-followup-plan"}
    if plan_id and str(plan.get("plan_id") or "").strip() != plan_id:
        return {"scheduled": False, "reason": "plan-id-mismatch"}
    existing_followup_task_id = str(plan.get("followup_task_id") or "").strip()
    if existing_followup_task_id:
        try:
            existing = store.load_task(existing_followup_task_id, allow_archive=False)
        except FileNotFoundError:
            existing = None
        if existing is not None:
            return {
                "scheduled": True,
                "task_id": existing.task_id,
                "status": existing.status,
                "due_at": str(existing.meta.get("continuation_due_at") or ""),
                "source_task_id": source_task.task_id,
                "plan_id": str(plan.get("plan_id") or ""),
            }

    followup_due_at = str(plan.get("followup_due_at") or "").strip()
    followup_message = str(plan.get("followup_message") or "").strip()
    if not followup_due_at or not followup_message:
        return {"scheduled": False, "reason": "invalid-followup-plan"}
    try:
        due_dt = datetime.fromisoformat(followup_due_at)
    except ValueError:
        return {"scheduled": False, "reason": "invalid-followup-due-at"}

    followup_task = store.observe_task(
        agent_id=source_task.agent_id,
        session_key=source_task.session_key,
        channel=source_task.channel,
        account_id=source_task.account_id,
        chat_id=source_task.chat_id,
        user_id=source_task.user_id,
        task_label=f"follow-up: {source_task.task_label}"[:80],
        meta={
            "source": "tool-followup-plan",
            "parent_task_id": source_task.task_id,
            "plan_id": str(plan.get("plan_id") or ""),
            "original_user_request": str(source_task.meta.get("original_user_request") or source_task.task_label or ""),
        },
    )
    scheduled = store.schedule_continuation(
        followup_task.task_id,
        continuation_kind=str(plan.get("followup_kind") or "delayed-reply"),
        due_at=followup_due_at,
        payload={
            "reply_text": followup_message,
            "original_user_request": str(source_task.meta.get("original_user_request") or source_task.task_label or ""),
            "parent_task_id": source_task.task_id,
            "plan_id": str(plan.get("plan_id") or ""),
            "reply_to_id": str(plan.get("reply_to_id") or ""),
            "thread_id": str(plan.get("thread_id") or ""),
        },
        reason="scheduled tool-assisted continuation wait",
    )
    plan["status"] = "scheduled"
    plan["followup_task_id"] = scheduled.task_id
    plan["materialized_at"] = now_iso()
    plan["overdue_on_materialize"] = due_dt <= datetime.now(timezone.utc)
    source_task.meta["tool_followup_plan"] = plan
    guard = source_task.meta.get("planning_promise_guard")
    if isinstance(guard, dict):
        guard["followup_task_id"] = scheduled.task_id
        guard["status"] = "scheduled"
        source_task.meta["planning_promise_guard"] = guard
    store.save_task(source_task)
    return {
        "scheduled": True,
        "task_id": scheduled.task_id,
        "status": scheduled.status,
        "due_at": followup_due_at,
        "source_task_id": source_task.task_id,
        "plan_id": str(plan.get("plan_id") or ""),
        "overdue_on_materialize": bool(plan["overdue_on_materialize"]),
    }


def finalize_planned_followup_from_payload(
    payload: dict[str, Any],
    *,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    runtime_config = load_task_system_config(config_path=config_path)
    store = TaskStore(paths=runtime_config.build_paths())
    source_task_id = str(payload.get("source_task_id") or "").strip()
    plan_id = str(payload.get("plan_id") or "").strip()
    if not source_task_id and plan_id:
        source_task_id = _find_source_task_id_for_plan(store, plan_id) or ""
    if not source_task_id:
        return {"ok": False, "reason": "missing-source-task-id", "promise_fulfilled": False}
    try:
        source_task = _resolve_existing_task(store, source_task_id)
    except FileNotFoundError:
        return {"ok": False, "reason": "source-task-not-found", "promise_fulfilled": False}

    plan = source_task.meta.get("tool_followup_plan")
    guard = source_task.meta.get("planning_promise_guard")
    if not isinstance(plan, dict):
        return {"ok": False, "reason": "missing-followup-plan", "promise_fulfilled": False}
    if plan_id and str(plan.get("plan_id") or "").strip() != plan_id:
        return {"ok": False, "reason": "plan-id-mismatch", "promise_fulfilled": False}

    followup_task_id = str(payload.get("followup_task_id") or plan.get("followup_task_id") or "").strip()
    promise_fulfilled = False
    if followup_task_id:
        try:
            store.load_task(followup_task_id, allow_archive=False)
            promise_fulfilled = True
        except FileNotFoundError:
            promise_fulfilled = False

    if isinstance(guard, dict):
        guard["status"] = "fulfilled" if promise_fulfilled else "anomaly"
        guard["checked_at"] = now_iso()
        source_task.meta["planning_promise_guard"] = guard
    if promise_fulfilled:
        plan["status"] = "fulfilled"
        plan["finalized_at"] = now_iso()
    else:
        source_task.meta["planning_anomaly"] = "promise-without-task"
        source_task.meta["planning_anomaly_at"] = now_iso()
        plan["status"] = "anomaly"
    source_task.meta["tool_followup_plan"] = plan
    store.save_task(source_task)
    return {
        "ok": promise_fulfilled,
        "promise_fulfilled": promise_fulfilled,
        "reason": None if promise_fulfilled else "promise-without-task",
        "source_task_id": source_task.task_id,
        "plan_id": str(plan.get("plan_id") or ""),
        "followup_task_id": followup_task_id or None,
        "followup_due_at": str(plan.get("followup_due_at") or ""),
        "original_time_expression": str(plan.get("original_time_expression") or ""),
    }


def watchdog_auto_recover_from_payload(
    payload: dict[str, Any],
    *,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    runtime_config = load_task_system_config(config_path=config_path)
    resolved_paths = runtime_config.build_paths()
    findings = process_overdue_tasks(
        paths=resolved_paths,
        config=runtime_config,
        config_path=config_path,
    )
    startup_recovery = bool(payload.get("startup_recovery", False))
    startup_promoted: list[dict[str, Any]] = []
    if startup_recovery:
        store = TaskStore(paths=resolved_paths)
        for finding in findings:
            if str(finding.get("agent_id") or "") != "main":
                continue
            if str(finding.get("status") or "") != "running":
                continue
            task_id = str(finding.get("task_id") or "").strip()
            if not task_id:
                continue
            try:
                task = store.load_task(task_id, allow_archive=False)
            except FileNotFoundError:
                continue
            if task.status != "running":
                continue
            blocked = store.block_task(
                task.task_id,
                "startup recovery promoted stale running task after restart",
            )
            blocked.monitor_state = "blocked"
            blocked.meta["watchdog_escalation"] = "startup-recovery-stalled-running"
            blocked.meta["watchdog_escalation_at"] = now_iso()
            store.save_task(blocked)
            startup_promoted.append(
                {
                    "task_id": blocked.task_id,
                    "session_key": blocked.session_key,
                    "task_label": blocked.task_label,
                    "channel": blocked.channel,
                    "account_id": blocked.account_id,
                    "chat_id": blocked.chat_id,
                    "previous_status": "running",
                    "watchdog_escalation": "startup-recovery-stalled-running",
                }
            )
    result = auto_resume_watchdog_blocked_main_tasks_if_safe(
        config_path=config_path,
        paths=resolved_paths,
        session_key=str(payload.get("session_key") or "").strip() or None,
        limit=int(payload["limit"]) if payload.get("limit") is not None else None,
        note=str(payload.get("note") or "").strip() or None,
        dry_run=bool(payload.get("dry_run", False)),
    )
    result["startup_recovery"] = startup_recovery
    result["startup_promoted"] = startup_promoted
    result["startup_promoted_count"] = len(startup_promoted)
    result["watchdog_findings"] = findings
    result["watchdog_findings_count"] = len(findings)
    result["watchdog_notified_count"] = sum(1 for finding in findings if bool(finding.get("should_notify")))
    result["watchdog_blocked_count"] = sum(
        1 for finding in findings if str(finding.get("escalation") or "").strip() == "blocked-no-visible-progress"
    )
    primary_action_kind = str(result.get("primary_action_kind") or result.get("primary_action", {}).get("kind") or "none")
    primary_action_command = str(
        result.get("primary_action_command") or result.get("primary_action", {}).get("command") or ""
    ).strip()
    top_risk_session = result.get("top_risk_session") if isinstance(result.get("top_risk_session"), dict) else {}
    top_risk_session_key = str(top_risk_session.get("session_key") or "").strip() or None
    top_risk_status_counts = top_risk_session.get("user_facing_status_counts")
    top_risk_status_code_counts = top_risk_session.get("user_facing_status_code_counts")
    rendered_top_risk_statuses = None
    if isinstance(top_risk_status_counts, dict) and top_risk_status_counts:
        rendered_top_risk_statuses = ", ".join(
            f"{label}:{count}"
            for label, count in sorted(top_risk_status_counts.items(), key=lambda item: (-int(item[1]), str(item[0])))
        )
    if result.get("startup_promoted_count"):
        watchdog_text = f"已执行 watchdog 启动恢复，提升了 {result['startup_promoted_count']} 条任务。"
    elif result.get("watchdog_blocked_count"):
        watchdog_text = f"watchdog 检测到 {result['watchdog_blocked_count']} 条阻塞风险，当前主动作：{primary_action_kind}。"
    elif result.get("watchdog_findings_count"):
        watchdog_text = f"watchdog 检测到 {result['watchdog_findings_count']} 条连续性风险，当前主动作：{primary_action_kind}。"
    else:
        watchdog_text = "watchdog 检查已完成，当前没有新的连续性风险。"
    if top_risk_session_key and rendered_top_risk_statuses:
        watchdog_text = f"{watchdog_text} 当前重点 session：{top_risk_session_key}（{rendered_top_risk_statuses}）。"
    result["control_plane_message"] = _build_control_plane_message(
        kind="watchdog-auto-recover",
        event_name="watchdog-auto-recover",
        priority="p1-task-management",
        text=watchdog_text,
        session_key=str(payload.get("session_key") or "").strip() or None,
        metadata={
            "status": result.get("status"),
            "startup_recovery": startup_recovery,
            "watchdog_findings_count": result.get("watchdog_findings_count"),
            "watchdog_blocked_count": result.get("watchdog_blocked_count"),
            "primary_action_kind": primary_action_kind,
            "primary_action_command": primary_action_command or None,
            "top_risk_session_key": top_risk_session_key,
            "top_risk_session_user_status_code_counts": (
                top_risk_status_code_counts if isinstance(top_risk_status_code_counts, dict) else {}
            ),
            "top_risk_session_user_status_counts": top_risk_status_counts if isinstance(top_risk_status_counts, dict) else {},
        },
    )
    return result
    claimed = store.claim_execution_slot(observed.task_id)
    return {"updated": True, "task": claimed.to_dict(), "reason": "promoted-observed-task"}


def _resolve_target_task(
    store: TaskStore,
    payload: dict[str, Any],
) -> Optional[Any]:
    requested_task_id = str(payload.get("task_id") or "").strip()
    if requested_task_id:
        try:
            requested = store.load_task(requested_task_id, allow_archive=False)
        except FileNotFoundError:
            requested = None
        if requested and requested.agent_id == payload["agent_id"] and requested.session_key == payload["session_key"]:
            return requested
    return store.find_latest_active_task(
        agent_id=payload["agent_id"],
        session_key=payload["session_key"],
    )


def claim_due_continuations_from_payload(
    payload: dict[str, Any],
    *,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    runtime_config = load_task_system_config(config_path=config_path)
    store = TaskStore(paths=runtime_config.build_paths())
    now_dt = datetime.now(timezone.utc).astimezone()
    claimable: list[tuple[datetime, str, Any]] = []
    due_tasks: list[dict[str, Any]] = []
    for path in store.list_inflight():
        task = store.load_task(path.stem, allow_archive=False)
        if task.status != "paused":
            continue
        if str(task.meta.get("continuation_kind") or "") != "delayed-reply":
            continue
        due_at = str(task.meta.get("continuation_due_at") or "").strip()
        if not due_at:
            continue
        try:
            due_dt = datetime.fromisoformat(due_at)
        except ValueError:
            continue
        if due_dt > now_dt:
            continue
        if str(task.meta.get("continuation_state") or "") == "claimed":
            continue
        claimable.append((due_dt, str(task.created_at or ""), task))

    claimable.sort(key=lambda item: (item[0], item[1], item[2].task_id))

    for _, _, task in claimable:
        task.status = "running"
        task.meta["continuation_state"] = "claimed"
        task.meta["continuation_claimed_at"] = now_dt.isoformat()
        task.updated_at = now_dt.isoformat()
        task.last_internal_touch_at = now_dt.isoformat()
        store.save_task(task)
        due_tasks.append(
            {
                "task_id": task.task_id,
                "agent_id": task.agent_id,
                "session_key": task.session_key,
                "channel": task.channel,
                "account_id": task.account_id,
                "chat_id": task.chat_id,
                "reply_text": ((task.meta.get("continuation_payload") or {}).get("reply_text") if isinstance(task.meta.get("continuation_payload"), dict) else None),
                "continuation_payload": task.meta.get("continuation_payload") if isinstance(task.meta.get("continuation_payload"), dict) else None,
            }
        )
    return {
        "claimed_count": len(due_tasks),
        "tasks": due_tasks,
    }


def fulfill_due_continuation_from_payload(
    payload: dict[str, Any],
    *,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    runtime_config = load_task_system_config(config_path=config_path)
    store = TaskStore(paths=runtime_config.build_paths())
    now_dt = datetime.now(timezone.utc).astimezone()
    content = str(payload.get("content") or "").strip()
    if not content:
        return {"updated": False, "reason": "empty-content"}

    session_tasks = store.find_inflight_tasks(
        agent_id=payload["agent_id"],
        session_key=payload["session_key"],
        statuses={"paused", "running"},
    )
    normalized_content = " ".join(content.split()).casefold()
    for task in session_tasks:
        if str(task.meta.get("continuation_kind") or "") != "delayed-reply":
            continue
        due_at = str(task.meta.get("continuation_due_at") or "").strip()
        if not due_at:
            continue
        try:
            due_dt = datetime.fromisoformat(due_at)
        except ValueError:
            continue
        if due_dt > now_dt:
            continue
        continuation_payload = task.meta.get("continuation_payload")
        if not isinstance(continuation_payload, dict):
            continue
        reply_text = str(continuation_payload.get("reply_text") or "").strip()
        if not reply_text:
            continue
        normalized_reply = " ".join(reply_text.split()).casefold()
        if normalized_reply not in normalized_content:
            continue

        completed = store.complete_task(
            task.task_id,
            archive=True,
            meta={
                "result_summary": f"continuation reply fulfilled by agent output: {reply_text}"[:240],
                "continuation_fulfilled_by": "agent-output",
                "continuation_fulfilled_at": now_dt.isoformat(),
            },
        )
        return {
            "updated": True,
            "task": completed.to_dict(),
            "matched_reply_text": reply_text,
        }

    return {"updated": False, "reason": "no-due-continuation-match"}


def mark_continuation_wake_from_payload(
    payload: dict[str, Any],
    *,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    runtime_config = load_task_system_config(config_path=config_path)
    store = TaskStore(paths=runtime_config.build_paths())
    try:
        task = store.load_task(payload["task_id"], allow_archive=False)
    except FileNotFoundError:
        return {"updated": False, "reason": "task-not-found"}
    ts = datetime.now(timezone.utc).astimezone().isoformat()
    meta = dict(task.meta)
    attempts = int(meta.get("continuation_wake_attempt_count") or 0)
    state = str(payload.get("state") or "").strip() or "attempting"
    if state == "attempting":
        attempts += 1
        meta["continuation_wake_attempt_count"] = attempts
        meta["continuation_last_wake_at"] = ts
    meta["continuation_wake_state"] = state
    note = str(payload.get("message") or "").strip()
    if note:
        meta["continuation_wake_message"] = note[:240]
    touched = store.touch_task(
        task.task_id,
        user_visible=False,
        meta=meta,
    )
    return {
        "updated": True,
        "task": touched.to_dict(),
        "attempt_count": int(touched.meta.get("continuation_wake_attempt_count") or 0),
        "wake_state": touched.meta.get("continuation_wake_state"),
    }


def resolve_active_task_from_payload(
    payload: dict[str, Any],
    *,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    runtime_config = load_task_system_config(config_path=config_path)
    store = TaskStore(paths=runtime_config.build_paths())
    task = _resolve_target_task(store, payload)
    return {
        "task_id": task.task_id if task else None,
        "found": task is not None,
        "status": task.status if task else None,
    }


def progress_from_payload(
    payload: dict[str, Any],
    *,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    task = record_progress(
        payload["task_id"],
        progress_note=payload.get("progress_note"),
        status=payload.get("status"),
        config_path=config_path,
    )
    return task.to_dict()


def progress_active_from_payload(
    payload: dict[str, Any],
    *,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    active = resolve_active_task_from_payload(payload, config_path=config_path)
    task_id = active.get("task_id")
    if not task_id:
        return {"updated": False, "reason": "no-active-task"}
    task = record_progress(
        str(task_id),
        progress_note=payload.get("progress_note"),
        status=payload.get("status"),
        config_path=config_path,
    )
    return {"updated": True, "task": task.to_dict()}


def blocked_from_payload(
    payload: dict[str, Any],
    *,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    task = record_blocked(payload["task_id"], payload["reason"], config_path=config_path)
    result = task.to_dict()
    reason = str(task.meta.get("blocked_reason") or payload.get("reason") or "").strip()
    result["control_plane_message"] = _build_control_plane_message(
        kind="task-blocked",
        event_name="task-blocked",
        priority="p1-task-management",
        text=f"当前任务已阻塞：{reason}" if reason else "当前任务已阻塞。",
        task=task,
    )
    return result


def blocked_active_from_payload(
    payload: dict[str, Any],
    *,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    active = resolve_active_task_from_payload(payload, config_path=config_path)
    task_id = active.get("task_id")
    if not task_id:
        return {"updated": False, "reason": "no-active-task"}
    task = record_blocked(str(task_id), payload["reason"], config_path=config_path)
    return {
        "updated": True,
        "task": task.to_dict(),
        "control_plane_message": _build_control_plane_message(
            kind="task-blocked",
            event_name="task-blocked",
            priority="p1-task-management",
            text=f"当前任务已阻塞：{payload['reason']}".strip(),
            task=task,
        ),
    }


def completed_from_payload(
    payload: dict[str, Any],
    *,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    task = record_completed(payload["task_id"], result_summary=payload.get("result_summary"), config_path=config_path)
    result = task.to_dict()
    result["control_plane_message"] = _build_control_plane_message(
        kind="task-completed",
        event_name="task-completed",
        priority="p1-task-management",
        text=_build_terminal_message_text(task, success=True),
        task=task,
    )
    return result


def completed_active_from_payload(
    payload: dict[str, Any],
    *,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    active = resolve_active_task_from_payload(payload, config_path=config_path)
    task_id = active.get("task_id")
    if not task_id:
        return {"updated": False, "reason": "no-active-task"}
    task = record_completed(str(task_id), result_summary=payload.get("result_summary"), config_path=config_path)
    return {
        "updated": True,
        "task": task.to_dict(),
        "control_plane_message": _build_control_plane_message(
            kind="task-completed",
            event_name="task-completed",
            priority="p1-task-management",
            text=_build_terminal_message_text(task, success=True),
            task=task,
        ),
    }


def failed_from_payload(
    payload: dict[str, Any],
    *,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    task = record_failed(payload["task_id"], payload["reason"], config_path=config_path)
    result = task.to_dict()
    result["control_plane_message"] = _build_control_plane_message(
        kind="task-failed",
        event_name="task-failed",
        priority="p1-task-management",
        text=_build_terminal_message_text(task, success=False),
        task=task,
    )
    return result


def failed_active_from_payload(
    payload: dict[str, Any],
    *,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    active = resolve_active_task_from_payload(payload, config_path=config_path)
    task_id = active.get("task_id")
    if not task_id:
        return {"updated": False, "reason": "no-active-task"}
    task = record_failed(str(task_id), payload["reason"], config_path=config_path)
    return {
        "updated": True,
        "task": task.to_dict(),
        "control_plane_message": _build_control_plane_message(
            kind="task-failed",
            event_name="task-failed",
            priority="p1-task-management",
            text=_build_terminal_message_text(task, success=False),
            task=task,
        ),
    }


def finalize_active_from_payload(
    payload: dict[str, Any],
    *,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    runtime_config = load_task_system_config(config_path=config_path)
    store = TaskStore(paths=runtime_config.build_paths())
    active = _resolve_target_task(store, payload)
    if not active:
        return {"updated": False, "reason": "no-active-task"}

    success = bool(payload.get("success", False))
    result_summary = str(payload.get("result_summary") or payload.get("summary") or "").strip()
    if success:
        last_progress_note = str(active.meta.get("last_progress_note") or "").strip()
        has_visible_progress = bool(last_progress_note)
        has_visible_output = bool(payload.get("has_visible_output", False))
        normalized_summary = result_summary.lower()
        word_count = len([part for part in normalized_summary.split() if part])
        generic_summary = (
            normalized_summary in GENERIC_SUCCESS_SUMMARIES
            or result_summary.startswith("{")
            or word_count <= 2
        )
        if not has_visible_progress and not has_visible_output and generic_summary:
            touched = store.touch_task(
                active.task_id,
                user_visible=False,
                meta={
                    "finalize_skipped": True,
                    "finalize_skipped_reason": "success-without-visible-progress",
                    "last_result_summary": result_summary,
                },
            )
            return {"updated": False, "reason": "awaiting-visible-output", "task": touched.to_dict()}
        promise_guard = active.meta.get("planning_promise_guard")
        tool_plan = active.meta.get("tool_followup_plan")
        if isinstance(promise_guard, dict) and bool(promise_guard.get("expected_by_finalize", False)):
            followup_task_id = ""
            if isinstance(tool_plan, dict):
                followup_task_id = str(tool_plan.get("followup_task_id") or "").strip()
            if not followup_task_id:
                promise_guard["status"] = "anomaly"
                promise_guard["checked_at"] = now_iso()
                active.meta["planning_promise_guard"] = promise_guard
                active.meta["planning_anomaly"] = "promise-without-task"
                active.meta["planning_anomaly_at"] = now_iso()
                store.save_task(active)
        post_run_plan = active.meta.get("post_run_continuation_plan")
        scheduled_followup_task_id = None
        if isinstance(post_run_plan, dict):
            followup_kind = str(post_run_plan.get("kind") or "").strip()
            followup_due_at = str(post_run_plan.get("due_at") or "").strip()
            followup_reply_text = str(post_run_plan.get("reply_text") or "").strip()
            followup_wait_seconds = int(post_run_plan.get("wait_seconds") or 0)
            if followup_kind and followup_due_at and followup_reply_text and followup_wait_seconds > 0:
                followup_task = store.observe_task(
                    agent_id=active.agent_id,
                    session_key=active.session_key,
                    channel=active.channel,
                    account_id=active.account_id,
                    chat_id=active.chat_id,
                    user_id=active.user_id,
                    task_label=f"follow-up: {active.task_label}"[:80],
                    meta={
                        "source": "main-post-run-followup",
                        "original_user_request": str(active.meta.get("original_user_request") or active.task_label or ""),
                        "parent_task_id": active.task_id,
                        "lead_request": str(post_run_plan.get("lead_request") or "").strip() or None,
                    },
                )
                scheduled = store.schedule_continuation(
                    followup_task.task_id,
                    continuation_kind=followup_kind,
                    due_at=followup_due_at,
                    payload={
                        "reply_text": followup_reply_text,
                        "wait_seconds": followup_wait_seconds,
                        "original_user_request": str(active.meta.get("original_user_request") or active.task_label or ""),
                        "parent_task_id": active.task_id,
                    },
                    reason="scheduled post-run continuation wait",
                )
                scheduled_followup_task_id = scheduled.task_id
        completed = completed_active_from_payload(
            {
                "agent_id": payload["agent_id"],
                "session_key": payload["session_key"],
                "task_id": active.task_id,
                "result_summary": result_summary or "agent run completed",
            },
            config_path=config_path,
        )
        if scheduled_followup_task_id and completed.get("updated") and isinstance(completed.get("task"), dict):
            task_payload = completed["task"]
            meta = task_payload.get("meta")
            if isinstance(meta, dict):
                meta["post_run_continuation_task_id"] = scheduled_followup_task_id
        return completed
    reason = str(payload.get("reason") or payload.get("error") or "agent run failed")
    return failed_active_from_payload(
        {
            "agent_id": payload["agent_id"],
            "session_key": payload["session_key"],
            "task_id": active.task_id,
            "reason": reason,
        },
        config_path=config_path,
    )


def should_send_short_followup_from_payload(
    payload: dict[str, Any],
    *,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    runtime_config = load_task_system_config(config_path=config_path)
    store = TaskStore(paths=runtime_config.build_paths())
    task_id = str(payload.get("task_id") or "").strip()
    if not task_id:
        return {"should_send": False, "reason": "missing-task-id"}
    try:
        task = store.load_task(task_id, allow_archive=False)
    except FileNotFoundError:
        return {"should_send": False, "reason": "task-not-found"}
    if task.status not in {"received", "queued", "running"}:
        return {"should_send": False, "reason": f"task-not-active:{task.status}", "task": task.to_dict()}
    status_entry = _find_inflight_status_entry(task.task_id, config_path=config_path)
    projection = project_user_facing_status(status_entry or {"status": task.status})
    user_facing_status = projection["label"]
    user_facing_status_code = projection["code"]
    queue_position, ahead_count, active_count, running_count, _ = _queue_metrics(
        store,
        agent_id=task.agent_id,
        task_id=task.task_id,
    )
    estimated_wait_seconds = _estimate_wait_seconds(
        store,
        agent_id=task.agent_id,
        queue_position=queue_position,
        task_status=task.status,
    )

    followup_message = "已收到你的消息，当前仍在处理中；稍后给你正式结果。"
    if task.status in {"received", "queued"}:
        position = queue_position or max(ahead_count + 1, 1)
        if estimated_wait_seconds and ahead_count > 0:
            followup_message = (
                f"已收到你的消息，当前仍在排队处理中；前面还有 {ahead_count} 个号，"
                f"你现在排第 {position} 位，预计约 {max(1, (estimated_wait_seconds + 59) // 60)} 分钟后轮到处理。"
            )
        elif ahead_count > 0:
            followup_message = (
                f"已收到你的消息，当前仍在排队处理中；前面还有 {ahead_count} 个号，"
                f"你现在排第 {position} 位。"
            )
        else:
            if user_facing_status_code == USER_STATUS_PENDING_START:
                followup_message = "已收到你的消息，当前状态：待开始；马上继续。"
            elif user_facing_status_code == USER_STATUS_RECEIVED:
                followup_message = "已收到你的消息，当前状态：已收到；马上继续进入处理。"
            else:
                followup_message = f"已收到你的消息，当前状态：{user_facing_status}；马上继续。"
    elif task.status == "running":
        last_progress_note = str(task.meta.get("last_progress_note") or "").strip()
        if last_progress_note:
            followup_message = f"已收到你的消息，当前仍在处理中；最近进展：{last_progress_note}"
        elif estimated_wait_seconds:
            if estimated_wait_seconds < 60:
                followup_message = (
                    f"已收到你的消息，当前仍在处理中；预计约 {estimated_wait_seconds} 秒内给你正式结果。"
                )
            else:
                followup_message = (
                    f"已收到你的消息，当前仍在处理中；预计约 {max(1, (estimated_wait_seconds + 59) // 60)} 分钟内给你正式结果。"
                )
        elif active_count > 1 or running_count > 1:
            followup_message = "已收到你的消息，当前仍在处理中；系统还有其他活动任务，我会继续同步进展。"

    return {
        "should_send": True,
        "reason": f"task-active:{task.status}",
        "task": task.to_dict(),
        "followup_message": followup_message,
        "control_plane_message": {
            "schema": "openclaw.task-system.control-plane.v1",
            "kind": "short-task-followup",
            "event_name": "short-task-followup",
            "priority": "p2-progress-followup",
            "task_id": task.task_id,
            "task_status": task.status,
            "user_facing_status_code": user_facing_status_code,
            "user_facing_status": user_facing_status,
            "text": followup_message,
            "metadata": {
                "user_facing_status_code": user_facing_status_code,
                "user_facing_status": user_facing_status,
                "queue_position": queue_position,
                "ahead_count": ahead_count,
                "estimated_wait_seconds": estimated_wait_seconds,
            },
        },
        "queue_position": queue_position,
        "ahead_count": ahead_count,
        "active_count": active_count,
        "running_count": running_count,
        "estimated_wait_seconds": estimated_wait_seconds,
        "user_facing_status_code": user_facing_status_code,
        "user_facing_status": user_facing_status,
    }


def taskmonitor_status_from_payload(
    payload: dict[str, Any],
    *,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    session_key = str(payload.get("session_key") or "").strip()
    if not session_key:
        return {"ok": False, "reason": "missing-session-key"}
    enabled = get_taskmonitor_enabled(session_key, config_path=config_path)
    return {
        "ok": True,
        "session_key": session_key,
        "enabled": enabled,
    }


def taskmonitor_control_from_payload(
    payload: dict[str, Any],
    *,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    session_key = str(payload.get("session_key") or "").strip()
    action = str(payload.get("action") or "status").strip().lower()
    if not session_key:
        return {"ok": False, "reason": "missing-session-key"}
    if action == "status":
        enabled = get_taskmonitor_enabled(session_key, config_path=config_path)
        return {
            "ok": True,
            "session_key": session_key,
            "enabled": enabled,
            "message": "当前会话的 taskmonitor 已开启。" if enabled else "当前会话的 taskmonitor 已关闭。",
            "control_plane_message": _build_control_plane_message(
                kind="taskmonitor-status",
                event_name="taskmonitor-status",
                priority="p1-task-management",
                text="当前会话的 taskmonitor 已开启。" if enabled else "当前会话的 taskmonitor 已关闭。",
                session_key=session_key,
                metadata={"enabled": enabled, "action": "status"},
            ),
        }
    if action in {"on", "enable", "enabled"}:
        updated = set_taskmonitor_enabled(session_key, True, config_path=config_path)
        return {
            "ok": True,
            **updated,
            "message": "已开启当前会话的 taskmonitor。",
            "control_plane_message": _build_control_plane_message(
                kind="taskmonitor-updated",
                event_name="taskmonitor-enabled",
                priority="p1-task-management",
                text="已开启当前会话的 taskmonitor。",
                session_key=session_key,
                metadata={"enabled": True, "action": "on"},
            ),
        }
    if action in {"off", "disable", "disabled"}:
        updated = set_taskmonitor_enabled(session_key, False, config_path=config_path)
        return {
            "ok": True,
            **updated,
            "message": "已关闭当前会话的 taskmonitor；后续消息将不再进入 task system 监控。",
            "control_plane_message": _build_control_plane_message(
                kind="taskmonitor-updated",
                event_name="taskmonitor-disabled",
                priority="p1-task-management",
                text="已关闭当前会话的 taskmonitor；后续消息将不再进入 task system 监控。",
                session_key=session_key,
                metadata={"enabled": False, "action": "off"},
            ),
        }
    return {
        "ok": False,
        "reason": "unsupported-action",
        "message": "不支持的 taskmonitor 命令；可用值：on / off / status",
    }


def resume_main_task_from_payload(
    payload: dict[str, Any],
    *,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    task_id = str(payload.get("task_id") or "").strip()
    if not task_id:
        return {"updated": False, "reason": "missing-task-id"}
    runtime_config = load_task_system_config(config_path=config_path)
    resolved_paths = runtime_config.build_paths()
    updated = resume_main_task(
        task_id,
        progress_note=str(payload.get("progress_note") or "").strip() or None,
        paths=resolved_paths,
    )
    if updated.status == "running":
        text = "当前任务已恢复执行。"
    elif updated.status == "queued":
        text = "当前任务已恢复排队，等待继续处理。"
    else:
        text = f"当前任务已恢复到 {updated.status} 状态。"
    return {
        "updated": True,
        "task": updated.to_dict(),
        "control_plane_message": _build_control_plane_message(
            kind="task-resumed",
            event_name="task-resumed",
            priority="p1-task-management",
            text=text,
            task=updated,
            metadata={"progress_note": str(payload.get("progress_note") or "").strip() or None},
        ),
    }


def cancel_main_queue_task_from_payload(
    payload: dict[str, Any],
    *,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    task_id = str(payload.get("task_id") or "").strip() or None
    queue_position_raw = payload.get("queue_position")
    queue_position = int(queue_position_raw) if queue_position_raw is not None else None
    runtime_config = load_task_system_config(config_path=config_path)
    resolved_paths = runtime_config.build_paths()
    store = TaskStore(paths=resolved_paths)

    selected_task = None
    if task_id:
        try:
            selected_task = store.load_task(task_id, allow_archive=False)
        except FileNotFoundError:
            selected_task = None
    elif queue_position is not None and queue_position >= 1:
        queued_tasks = store.find_queued_tasks(agent_id="main")
        if queue_position <= len(queued_tasks):
            selected_task = queued_tasks[queue_position - 1]

    result = cancel_main_queue_task(
        config_path=config_path,
        paths=resolved_paths,
        task_id=task_id,
        queue_position=queue_position,
        reason=str(payload.get("reason") or "user requested queued task cancel"),
    )
    if result.get("action") != "cancelled-queued-task":
        return result

    cancelled_task_id = str(result.get("task_id") or task_id or "").strip()
    archived_task = None
    if cancelled_task_id:
        try:
            archived_task = store.load_task(cancelled_task_id, allow_archive=True)
        except FileNotFoundError:
            archived_task = None
    message_text = str(result.get("suggestion") or "").strip() or "已取消排队中的任务。"
    return {
        **result,
        "task": archived_task.to_dict() if archived_task else (selected_task.to_dict() if selected_task else None),
        "control_plane_message": _build_control_plane_message(
            kind="task-cancelled",
            event_name="task-cancelled",
            priority="p1-task-management",
            text=message_text,
            task=archived_task or selected_task,
            metadata={
                "queue_position": result.get("queue_position"),
                "remaining_queued_count": result.get("remaining_queued_count"),
                "remaining_active_count": result.get("remaining_active_count"),
            },
        ),
    }


def main_continuity_from_payload(
    payload: dict[str, Any],
    *,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    return get_main_continuity_summary(
        config_path=config_path,
        session_key=str(payload.get("session_key") or "").strip() or None,
    )


def _render_session_tasks_summary_text(items: list[dict[str, Any]], *, session_key: Optional[str]) -> str:
    if not items:
        if session_key:
            return "当前会话没有活动中的 task。"
        return "当前没有活动中的 main task。"
    rendered_items: list[str] = []
    for entry in items[:3]:
        status = str(entry.get("status") or "")
        projection = project_user_facing_status(entry)
        label = projection["label"] or (status or "未知状态")
        status_code = projection["code"]
        queue = entry.get("queue") if isinstance(entry.get("queue"), dict) else {}
        position = queue.get("position") if isinstance(queue, dict) else None
        task_label = str(entry.get("task_label") or "").strip() or str(entry.get("task_id") or "")
        if status_code in {USER_STATUS_QUEUED, USER_STATUS_PENDING_START} and position is not None:
            rendered_items.append(f"{label}，第 {position} 位：{task_label}")
        else:
            rendered_items.append(f"{label}：{task_label}")
    summary = "；".join(rendered_items)
    if len(items) > 3:
        summary = f"{summary}；另有 {len(items) - 3} 条任务未展开。"
    prefix = f"当前会话共有 {len(items)} 条活动任务：" if session_key else f"当前共有 {len(items)} 条活动 main task："
    return f"{prefix}{summary}"


def main_tasks_summary_from_payload(
    payload: dict[str, Any],
    *,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    runtime_config = load_task_system_config(config_path=config_path)
    resolved_paths = runtime_config.build_paths()
    session_key = str(payload.get("session_key") or "").strip() or None
    statuses = list_inflight_statuses(paths=resolved_paths)
    relevant = [
        status
        for status in statuses
        if str(status.get("agent_id") or "") == "main"
        and (session_key is None or str(status.get("session_key") or "") == session_key)
        and str(status.get("status") or "") in {"received", "queued", "running", "paused", "blocked"}
    ]
    relevant = sorted(
        relevant,
        key=lambda item: (
            int(((item.get("queue") or {}) if isinstance(item.get("queue"), dict) else {}).get("position") or 999999),
            str(item.get("created_at") or ""),
            str(item.get("task_id") or ""),
        ),
    )
    text = _render_session_tasks_summary_text(relevant, session_key=session_key)
    return {
        "session_key": session_key,
        "task_count": len(relevant),
        "tasks": relevant,
        "control_plane_message": _build_control_plane_message(
            kind="main-tasks-summary",
            event_name="main-tasks-summary",
            priority="p1-task-management",
            text=text,
            session_key=session_key,
            metadata={
                "task_count": len(relevant),
                "focus_session_key": session_key,
            },
        ),
    }


def dispatch(command: str, payload: dict[str, Any], *, config_path: Optional[Path] = None) -> dict[str, Any]:
    if command == "register":
        return register_from_payload(payload, config_path=config_path)
    if command == "create-followup-plan":
        return create_followup_plan_from_payload(payload, config_path=config_path)
    if command == "attach-promise-guard":
        return attach_promise_guard_from_payload(payload, config_path=config_path)
    if command == "schedule-followup-from-plan":
        return schedule_followup_from_plan_from_payload(payload, config_path=config_path)
    if command == "finalize-planned-followup":
        return finalize_planned_followup_from_payload(payload, config_path=config_path)
    if command == "activate-latest":
        return activate_latest_from_payload(payload, config_path=config_path)
    if command == "watchdog-auto-recover":
        return watchdog_auto_recover_from_payload(payload, config_path=config_path)
    if command == "claim-due-continuations":
        return claim_due_continuations_from_payload(payload, config_path=config_path)
    if command == "fulfill-due-continuation":
        return fulfill_due_continuation_from_payload(payload, config_path=config_path)
    if command == "continuation-wake":
        return mark_continuation_wake_from_payload(payload, config_path=config_path)
    if command == "resolve-active":
        return resolve_active_task_from_payload(payload, config_path=config_path)
    if command == "progress":
        return progress_from_payload(payload, config_path=config_path)
    if command == "progress-active":
        return progress_active_from_payload(payload, config_path=config_path)
    if command == "blocked":
        return blocked_from_payload(payload, config_path=config_path)
    if command == "blocked-active":
        return blocked_active_from_payload(payload, config_path=config_path)
    if command == "completed":
        return completed_from_payload(payload, config_path=config_path)
    if command == "completed-active":
        return completed_active_from_payload(payload, config_path=config_path)
    if command == "failed":
        return failed_from_payload(payload, config_path=config_path)
    if command == "failed-active":
        return failed_active_from_payload(payload, config_path=config_path)
    if command == "finalize-active":
        return finalize_active_from_payload(payload, config_path=config_path)
    if command == "should-send-short-followup":
        return should_send_short_followup_from_payload(payload, config_path=config_path)
    if command == "taskmonitor-status":
        return taskmonitor_status_from_payload(payload, config_path=config_path)
    if command == "taskmonitor-control":
        return taskmonitor_control_from_payload(payload, config_path=config_path)
    if command == "resume-main-task":
        return resume_main_task_from_payload(payload, config_path=config_path)
    if command == "cancel-main-queue-task":
        return cancel_main_queue_task_from_payload(payload, config_path=config_path)
    if command == "main-continuity":
        return main_continuity_from_payload(payload, config_path=config_path)
    if command == "main-tasks-summary":
        return main_tasks_summary_from_payload(payload, config_path=config_path)
    raise ValueError(f"unsupported command: {command}")


if __name__ == "__main__":
    args = sys.argv[1:]
    usage = (
        "usage: openclaw_hooks.py "
        "<register|create-followup-plan|attach-promise-guard|schedule-followup-from-plan|finalize-planned-followup|watchdog-auto-recover|claim-due-continuations|fulfill-due-continuation|continuation-wake|resolve-active|progress|progress-active|blocked|blocked-active|completed|completed-active|failed|failed-active|finalize-active|should-send-short-followup|taskmonitor-status|taskmonitor-control|resume-main-task|cancel-main-queue-task|main-continuity|main-tasks-summary> "
        "<payload.json|-> [config.json]"
    )
    if args and args[0] in {"-h", "--help"}:
        print(usage)
        raise SystemExit(0)
    if len(args) < 2:
        raise SystemExit(usage)

    command = args[0]
    payload_source = args[1]
    config_path = Path(args[2]).expanduser().resolve() if len(args) > 2 else None
    payload = load_payload_for_command(command, payload_source)
    result = dispatch(command, payload, config_path=config_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
