#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Optional

from openclaw_bridge import (
    OpenClawInboundContext,
    record_blocked,
    record_completed,
    record_failed,
    record_progress,
    register_inbound_task,
)
from task_config import load_task_system_config
from task_state import TaskStore


GENERIC_SUCCESS_SUMMARIES = {
    "openai-codex-responses",
    "agent run completed",
    "assistant",
}


def load_payload(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


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
    active = resolve_active_task_from_payload(
        {
            "agent_id": payload["agent_id"],
            "session_key": payload["session_key"],
        },
        config_path=config_path,
    )
    if active["found"]:
        return {
            "should_register_task": True,
            "task_id": active["task_id"],
            "classification_reason": "existing-active-task",
            "confidence": "high",
            "task_status": active.get("status"),
            "queue_position": None,
            "ahead_count": 0,
            "active_count": 1,
            "running_count": 1 if active.get("status") == "running" else 0,
            "queued_count": 1 if active.get("status") == "queued" else 0,
            "continuation_due_at": None,
        }
    decision = register_inbound_task(
        _build_context(payload),
        config_path=config_path,
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
        "continuation_due_at": decision.continuation_due_at,
    }


def claim_due_continuations_from_payload(
    payload: dict[str, Any],
    *,
    config_path: Optional[Path] = None,
) -> dict[str, Any]:
    runtime_config = load_task_system_config(config_path=config_path)
    store = TaskStore(paths=runtime_config.build_paths())
    now_dt = datetime.now(timezone.utc).astimezone()
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
    task = store.load_task(payload["task_id"], allow_archive=False)
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
    task = store.find_latest_active_task(
        agent_id=payload["agent_id"],
        session_key=payload["session_key"],
    )
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
    active = store.find_latest_active_task(
        agent_id=payload["agent_id"],
        session_key=payload["session_key"],
    )
    if not active:
        return {"updated": False, "reason": "no-active-task"}

    success = bool(payload.get("success", False))
    result_summary = str(payload.get("result_summary") or payload.get("summary") or "").strip()
    if success:
        last_progress_note = str(active.meta.get("last_progress_note") or "").strip()
        has_visible_progress = bool(last_progress_note)
        normalized_summary = result_summary.lower()
        word_count = len([part for part in normalized_summary.split() if part])
        generic_summary = (
            normalized_summary in GENERIC_SUCCESS_SUMMARIES
            or result_summary.startswith("{")
            or word_count <= 2
        )
        if not has_visible_progress and generic_summary:
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
                "result_summary": result_summary or "agent run completed",
            },
            config_path=config_path,
        )
    reason = str(payload.get("reason") or payload.get("error") or "agent run failed")
    return failed_active_from_payload(
        {
            "agent_id": payload["agent_id"],
            "session_key": payload["session_key"],
            "reason": reason,
        },
        config_path=config_path,
    )


def dispatch(command: str, payload: dict[str, Any], *, config_path: Optional[Path] = None) -> dict[str, Any]:
    if command == "register":
        return register_from_payload(payload, config_path=config_path)
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
    raise ValueError(f"unsupported command: {command}")


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    usage = (
        "usage: openclaw_hooks.py "
        "<register|claim-due-continuations|fulfill-due-continuation|continuation-wake|resolve-active|progress|progress-active|blocked|blocked-active|completed|completed-active|failed|failed-active|finalize-active> "
        "<payload.json> [config.json]"
    )
    if args and args[0] in {"-h", "--help"}:
        print(usage)
        raise SystemExit(0)
    if len(args) < 2:
        raise SystemExit(usage)

    command = args[0]
    payload_path = Path(args[1]).expanduser().resolve()
    config_path = Path(args[2]).expanduser().resolve() if len(args) > 2 else None
    result = dispatch(command, load_payload(payload_path), config_path=config_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
