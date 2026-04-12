#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from openclaw_bridge import (
    OpenClawInboundContext,
    record_blocked,
    record_completed,
    record_failed,
    record_progress,
    register_inbound_task,
)
from task_config import TaskSystemConfig, load_task_system_config
from task_state import TaskStore, now_iso


GENERIC_SUCCESS_SUMMARIES = {
    "openai-codex-responses",
    "agent run completed",
    "assistant",
}
REPLY_TO_CURRENT_MARKER = "[[reply_to_current]]"

SameSessionRoutingClassifier = Callable[[dict[str, Any]], dict[str, Any]]


def _resolve_store(config_path: Optional[Path]) -> tuple[TaskSystemConfig, TaskStore]:
    runtime_config = load_task_system_config(config_path=config_path)
    return runtime_config, TaskStore(paths=runtime_config.build_paths())


def _sanitize_visible_text(text: Any) -> str:
    normalized = str(text or "").strip()
    if not normalized:
        return ""
    if normalized.startswith(REPLY_TO_CURRENT_MARKER):
        normalized = normalized[len(REPLY_TO_CURRENT_MARKER) :].strip()
    if normalized.startswith("[wd]"):
        normalized = normalized[4:].strip()
    return " ".join(normalized.split()).strip()


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


def _compact_task_target(task: Any) -> Optional[str]:
    target = str(task.meta.get("original_user_request") or task.task_label or "").strip()
    if not target:
        return None
    compact = " ".join(target.split())
    if len(compact) > 48:
        return f"{compact[:45].rstrip()}..."
    return compact


def _build_terminal_message_text(task: Any, *, success: bool) -> str:
    summary = str(task.meta.get("result_summary") or "").strip()
    if success:
        normalized_summary = summary.lower()
        generic_summary = normalized_summary in GENERIC_SUCCESS_SUMMARIES or summary.startswith("{")
        if summary and not generic_summary:
            return f"当前任务已完成：{summary}"
        target = _compact_task_target(task)
        if target:
            return f"当前任务已完成：{target}"
        return "当前任务已完成。"
    failure_reason = str(getattr(task, "failure_reason", "") or task.meta.get("failure_reason") or "").strip()
    if failure_reason:
        return f"当前任务已失败：{failure_reason}"
    return "当前任务已失败。"


def _render_same_session_routing_receipt(routing: dict[str, Any]) -> Optional[dict[str, Any]]:
    decision = str(routing.get("execution_decision") or "").strip()
    reason_code = str(routing.get("reason_code") or "").strip() or None
    reason_text = str(routing.get("reason_text") or "").strip() or None
    target_task_id = str(routing.get("target_task_id") or "").strip() or None
    session_key = str(routing.get("session_key") or "").strip() or None
    target_session_key = str(routing.get("target_session_key") or "").strip() or session_key
    if not decision:
        return None

    templates = {
        "merge-before-start": "这次更新已并入当前任务，因为任务还没正式开始执行。",
        "interrupt-and-restart": "当前任务已按这次更新重新开始，因为现在仍处于可安全重启阶段。",
        "append-as-next-step": "这次更新已追加为当前任务的下一步，因为执行已产生外部动作。",
        "queue-as-new-task": "这次内容已作为独立任务排队，因为它是新的独立目标。",
        "enter-collecting-window": "我会先等待你继续补充，再开始执行。",
        "handle-as-control-plane": "这条控制指令已收到，我会按当前任务状态处理。",
    }
    text = templates.get(decision)
    if not text:
        return None
    return {
        "decision": decision,
        "reason_code": reason_code,
        "reason_text": reason_text,
        "target_task_id": target_task_id,
        "target_session_key": target_session_key,
        "user_visible_wd": f"[wd] {text}",
    }


def _build_same_session_routing_control_plane_message(
    routing: dict[str, Any],
) -> Optional[dict[str, Any]]:
    receipt = _render_same_session_routing_receipt(routing)
    if not receipt:
        return None
    task_id = str(receipt.get("target_task_id") or "").strip() or None
    metadata = {
        "routing_decision": routing,
        "wd_receipt": receipt,
    }
    message = _build_control_plane_message(
        kind="same-session-routing-receipt",
        event_name="same-session-routing-receipt",
        priority="p0-receive-ack",
        text=str(receipt["user_visible_wd"]).replace("[wd]", "", 1).strip(),
        task=None,
        session_key=str(receipt.get("target_session_key") or routing.get("session_key") or "").strip() or None,
        metadata=metadata,
    )
    if task_id:
        message["task_id"] = task_id
    return message


def _build_queue_receipt_text(
    *,
    queue_position: Optional[int],
    ahead_count: int,
    running_count: int,
    estimated_wait_seconds: Optional[int],
) -> str:
    position = queue_position or max(ahead_count + 1, 1)
    suppress_short_eta = ahead_count > 0 and estimated_wait_seconds is not None and estimated_wait_seconds < 60
    if estimated_wait_seconds and not suppress_short_eta:
        if ahead_count > 0 and running_count <= 0:
            return (
                f"已收到，你的请求已进入队列；前面还有 {ahead_count} 个号，"
                f"你现在排第 {position} 位，预计约 {max(1, (estimated_wait_seconds + 59) // 60)} 分钟后轮到处理。"
            )
        if running_count <= 0:
            return (
                f"已收到，你的请求已进入队列；你现在排第 {position} 位，"
                f"预计约 {max(1, (estimated_wait_seconds + 59) // 60)} 分钟后轮到处理。"
            )
        return (
            f"已收到，当前有 {running_count} 条任务正在处理；你的请求已进入队列，"
            f"前面还有 {ahead_count} 个号，你现在排第 {position} 位，"
            f"预计约 {max(1, (estimated_wait_seconds + 59) // 60)} 分钟后轮到处理。"
        )
    if ahead_count > 0 and running_count <= 0:
        return f"已收到，你的请求已进入队列；前面还有 {ahead_count} 个号，你现在排第 {position} 位。"
    if running_count <= 0:
        return f"已收到，你的请求已进入队列；你现在排第 {position} 位。"
    return (
        f"已收到，当前有 {running_count} 条任务正在处理；你的请求已进入队列，"
        f"前面还有 {ahead_count} 个号，你现在排第 {position} 位。"
    )


def _build_blocked_control_plane_message(task: Any, *, reason: Optional[str] = None) -> dict[str, Any]:
    blocked_reason = str(reason or task.meta.get("blocked_reason") or "").strip()
    return _build_control_plane_message(
        kind="task-blocked",
        event_name="task-blocked",
        priority="p1-task-management",
        text=f"当前任务已阻塞：{blocked_reason}" if blocked_reason else "当前任务已阻塞。",
        task=task,
    )


def _build_completed_control_plane_message(task: Any) -> dict[str, Any]:
    return _build_control_plane_message(
        kind="task-completed",
        event_name="task-completed",
        priority="p1-task-management",
        text=_build_terminal_message_text(task, success=True),
        task=task,
    )


def _build_failed_control_plane_message(task: Any) -> dict[str, Any]:
    return _build_control_plane_message(
        kind="task-failed",
        event_name="task-failed",
        priority="p1-task-management",
        text=_build_terminal_message_text(task, success=False),
        task=task,
    )


def _persist_same_session_routing_context(
    store: TaskStore,
    *,
    task_id: str,
    routing: dict[str, Any],
) -> None:
    try:
        task = store.load_task(task_id, allow_archive=False)
    except FileNotFoundError:
        return
    task.meta["same_session_routing"] = routing
    store.save_task(task)


def register_inbound_lifecycle(
    ctx: OpenClawInboundContext,
    *,
    config_path: Optional[Path] = None,
    observe_only: bool = False,
    same_session_classifier: Optional[SameSessionRoutingClassifier] = None,
    same_session_classifier_min_confidence: float = 0.75,
) -> dict[str, Any]:
    _, store = _resolve_store(config_path)
    decision = register_inbound_task(
        ctx,
        config_path=config_path,
        observe_only=observe_only,
        same_session_classifier=same_session_classifier,
        same_session_classifier_min_confidence=same_session_classifier_min_confidence,
    )
    serialized = decision.to_payload()
    routing = serialized.get("routing_decision")
    task_id = str(serialized.get("task_id") or "").strip()
    if isinstance(routing, dict):
        routing = dict(routing)
        wd_receipt = _render_same_session_routing_receipt(routing)
        control_plane_message = None
        if wd_receipt:
            control_plane_message = _build_same_session_routing_control_plane_message(routing)
            if control_plane_message and str(routing.get("execution_decision") or "").strip() == "queue-as-new-task":
                queue_text = _build_queue_receipt_text(
                    queue_position=serialized.get("queue_position"),
                    ahead_count=int(serialized.get("ahead_count") or 0),
                    running_count=int(serialized.get("running_count") or 0),
                    estimated_wait_seconds=(
                        int(serialized["estimated_wait_seconds"])
                        if serialized.get("estimated_wait_seconds") is not None
                        else None
                    ),
                )
                wd_receipt["user_visible_wd"] = f"[wd] {queue_text}"
                control_plane_message["text"] = queue_text
            routing["wd_receipt"] = wd_receipt
            if control_plane_message and isinstance(control_plane_message.get("metadata"), dict):
                control_plane_message["metadata"]["routing_decision"] = routing
                control_plane_message["metadata"]["wd_receipt"] = wd_receipt
            serialized["wd_receipt"] = wd_receipt
            serialized["control_plane_message"] = control_plane_message
        serialized["routing_decision"] = routing
        if task_id:
            _persist_same_session_routing_context(store, task_id=task_id, routing=routing)
    return serialized


def block_task_lifecycle(
    task_id: str,
    *,
    reason: str,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    task = record_blocked(task_id, reason, config_path=config_path)
    return {
        "updated": True,
        "task": task.to_dict(),
        "lifecycle_transition": "blocked",
        "control_plane_message": _build_blocked_control_plane_message(task, reason=reason),
    }


def complete_task_lifecycle(
    task_id: str,
    *,
    result_summary: Optional[str] = None,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    task = record_completed(task_id, result_summary=result_summary, config_path=config_path)
    return {
        "updated": True,
        "task": task.to_dict(),
        "lifecycle_transition": "completed",
        "control_plane_message": _build_completed_control_plane_message(task),
    }


def fail_task_lifecycle(
    task_id: str,
    *,
    reason: str,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    task = record_failed(task_id, reason, config_path=config_path)
    return {
        "updated": True,
        "task": task.to_dict(),
        "lifecycle_transition": "failed",
        "control_plane_message": _build_failed_control_plane_message(task),
    }


def progress_active_lifecycle(
    *,
    task_id: str,
    progress_note: Any = None,
    status: Any = None,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    runtime_config, store = _resolve_store(config_path)
    task = record_progress(
        task_id,
        progress_note=progress_note,
        status=status,
        config=runtime_config,
    )
    visible_summary = _sanitize_visible_text(progress_note)[:240]
    should_finalize = (
        task.status == "running"
        and str(task.meta.get("finalize_skipped_reason") or "").strip() == "success-without-visible-progress"
        and bool(visible_summary)
    )
    if not should_finalize:
        return {
            "updated": True,
            "task": task.to_dict(),
            "lifecycle_transition": "progress-recorded",
            "finalize_repaired": False,
        }

    completed = store.complete_task(
        task.task_id,
        meta={
            "result_summary": visible_summary,
            "finalize_skipped_repaired_at": now_iso(),
            "finalize_skipped_repaired_source": "visible-progress",
        },
    )
    return {
        "updated": True,
        "task": completed.to_dict(),
        "lifecycle_transition": "finalized-after-visible-progress",
        "finalize_repaired": True,
    }


def _maybe_mark_promise_without_task(store: TaskStore, task: Any) -> None:
    promise_guard = task.meta.get("planning_promise_guard")
    tool_plan = task.meta.get("tool_followup_plan")
    if not isinstance(promise_guard, dict) or not bool(promise_guard.get("expected_by_finalize", False)):
        return
    followup_task_id = ""
    if isinstance(tool_plan, dict):
        followup_task_id = str(tool_plan.get("followup_task_id") or "").strip()
    if followup_task_id:
        return
    promise_guard["status"] = "anomaly"
    promise_guard["checked_at"] = now_iso()
    task.meta["planning_promise_guard"] = promise_guard
    task.meta["planning_anomaly"] = "promise-without-task"
    task.meta["planning_anomaly_at"] = now_iso()
    store.save_task(task)


def _clear_legacy_post_run_continuation(store: TaskStore, task: Any) -> None:
    if not isinstance(task.meta.get("post_run_continuation_plan"), dict):
        return
    task.meta.pop("post_run_continuation_plan", None)
    task.meta["legacy_post_run_continuation_ignored_at"] = now_iso()
    task.meta["legacy_post_run_continuation_reason"] = "structured-tool-plan-required"
    store.save_task(task)


def finalize_active_lifecycle(
    *,
    active_task: Any,
    payload: dict[str, Any],
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    _, store = _resolve_store(config_path)
    success = bool(payload.get("success", False))
    result_summary = _sanitize_visible_text(payload.get("result_summary") or payload.get("summary"))
    if success:
        last_progress_note = _sanitize_visible_text(active_task.meta.get("last_progress_note"))
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
                active_task.task_id,
                user_visible=False,
                meta={
                    "finalize_skipped": True,
                    "finalize_skipped_reason": "success-without-visible-progress",
                    "last_result_summary": result_summary,
                },
            )
            return {
                "updated": False,
                "reason": "awaiting-visible-output",
                "task": touched.to_dict(),
                "lifecycle_transition": "awaiting-visible-output",
            }

        _maybe_mark_promise_without_task(store, active_task)
        _clear_legacy_post_run_continuation(store, active_task)
        completed = store.complete_task(
            active_task.task_id,
            meta={"result_summary": result_summary or "agent run completed"},
        )
        return {
            "updated": True,
            "reason": "completed",
            "task": completed.to_dict(),
            "lifecycle_transition": "completed",
            "control_plane_message": _build_completed_control_plane_message(completed),
        }

    failure_reason = str(payload.get("reason") or payload.get("error") or "agent run failed").strip()
    failed = store.fail_task(active_task.task_id, failure_reason)
    return {
        "updated": True,
        "reason": "failed",
        "task": failed.to_dict(),
        "lifecycle_transition": "failed",
        "control_plane_message": _build_failed_control_plane_message(failed),
    }
