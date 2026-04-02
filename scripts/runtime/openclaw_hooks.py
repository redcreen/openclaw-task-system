#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
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
        "<register|resolve-active|progress|progress-active|blocked|blocked-active|completed|completed-active|failed|failed-active|finalize-active> "
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
