#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from openclaw_bridge import OpenClawInboundContext, record_progress, register_inbound_task
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
    if isinstance(routing, dict) and task_id:
        _persist_same_session_routing_context(store, task_id=task_id, routing=dict(routing))
    return serialized


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
        }

    failure_reason = str(payload.get("reason") or payload.get("error") or "agent run failed").strip()
    failed = store.fail_task(active_task.task_id, failure_reason)
    return {
        "updated": True,
        "reason": "failed",
        "task": failed.to_dict(),
        "lifecycle_transition": "failed",
    }
