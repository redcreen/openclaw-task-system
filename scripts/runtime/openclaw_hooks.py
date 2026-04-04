#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Optional

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
from main_ops import auto_resume_watchdog_blocked_main_tasks_if_safe
from silence_monitor import process_overdue_tasks
from task_config import load_task_system_config
from task_state import TaskStore, now_iso
from taskmonitor_state import get_taskmonitor_enabled, set_taskmonitor_enabled


GENERIC_SUCCESS_SUMMARIES = {
    "openai-codex-responses",
    "agent run completed",
    "assistant",
}


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
    return {
        "should_register_task": decision.should_register_task,
        "task_id": decision.task_id,
        "classification_reason": decision.classification_reason,
        "confidence": decision.confidence,
        "task_status": decision.task_status,
        "queue_position": decision.queue_position,
        "ahead_count": decision.ahead_count,
        "active_count": decision.active_count,
        "running_count": decision.running_count,
        "queued_count": decision.queued_count,
        "estimated_wait_seconds": decision.estimated_wait_seconds,
        "continuation_due_at": decision.continuation_due_at,
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
    busy_sessions: set[tuple[str, str]] = set()
    for path in store.list_inflight():
        task = store.load_task(path.stem, allow_archive=False)
        if task.status == "running":
            busy_sessions.add((task.agent_id, task.session_key))
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

    claimed_sessions: set[tuple[str, str]] = set()
    for _, _, task in claimable:
        session_lane = (task.agent_id, task.session_key)
        if session_lane in busy_sessions or session_lane in claimed_sessions:
            continue
        task.status = "running"
        task.meta["continuation_state"] = "claimed"
        task.meta["continuation_claimed_at"] = now_dt.isoformat()
        task.updated_at = now_dt.isoformat()
        task.last_internal_touch_at = now_dt.isoformat()
        store.save_task(task)
        claimed_sessions.add(session_lane)
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
    return task.to_dict()


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
    return {"updated": True, "task": task.to_dict()}


def completed_from_payload(
    payload: dict[str, Any],
    *,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    task = record_completed(payload["task_id"], result_summary=payload.get("result_summary"), config_path=config_path)
    return task.to_dict()


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
    return {"updated": True, "task": task.to_dict()}


def failed_from_payload(
    payload: dict[str, Any],
    *,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    task = record_failed(payload["task_id"], payload["reason"], config_path=config_path)
    return task.to_dict()


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
    return {"updated": True, "task": task.to_dict()}


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
        return completed_active_from_payload(
            {
                "agent_id": payload["agent_id"],
                "session_key": payload["session_key"],
                "task_id": active.task_id,
                "result_summary": result_summary or "agent run completed",
            },
            config_path=config_path,
        )
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
            followup_message = "已收到你的消息，当前正在等待真正开始处理；马上继续。"
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
        "queue_position": queue_position,
        "ahead_count": ahead_count,
        "active_count": active_count,
        "running_count": running_count,
        "estimated_wait_seconds": estimated_wait_seconds,
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
        }
    if action in {"on", "enable", "enabled"}:
        updated = set_taskmonitor_enabled(session_key, True, config_path=config_path)
        return {
            "ok": True,
            **updated,
            "message": "已开启当前会话的 taskmonitor。",
        }
    if action in {"off", "disable", "disabled"}:
        updated = set_taskmonitor_enabled(session_key, False, config_path=config_path)
        return {
            "ok": True,
            **updated,
            "message": "已关闭当前会话的 taskmonitor；后续消息将不再进入 task system 监控。",
        }
    return {
        "ok": False,
        "reason": "unsupported-action",
        "message": "不支持的 taskmonitor 命令；可用值：on / off / status",
    }


def dispatch(command: str, payload: dict[str, Any], *, config_path: Optional[Path] = None) -> dict[str, Any]:
    if command == "register":
        return register_from_payload(payload, config_path=config_path)
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
    raise ValueError(f"unsupported command: {command}")


if __name__ == "__main__":
    args = sys.argv[1:]
    usage = (
        "usage: openclaw_hooks.py "
        "<register|watchdog-auto-recover|claim-due-continuations|fulfill-due-continuation|continuation-wake|resolve-active|progress|progress-active|blocked|blocked-active|completed|completed-active|failed|failed-active|finalize-active|should-send-short-followup|taskmonitor-status|taskmonitor-control> "
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
