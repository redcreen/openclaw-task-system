#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from task_config import TaskSystemConfig, load_task_system_config
from task_state import TaskPaths, TaskStore, default_paths


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


def build_delivery_summary(task_id: str, *, paths: TaskPaths) -> dict[str, object]:
    outbox_path = _artifact_path(paths, "outbox", task_id)
    sent_path = _artifact_path(paths, "sent", task_id)
    delivery_ready_path = _artifact_path(paths, "delivery-ready", task_id)
    send_instruction_path = _artifact_path(paths, "send-instructions", task_id)
    dispatch_result_path = _artifact_path(paths, "dispatch-results", task_id)
    processed_instruction_path = _artifact_path(paths, "processed-instructions", task_id)
    failed_instruction_path = _artifact_path(paths, "failed-instructions", task_id)

    dispatch_result = _load_json_if_exists(dispatch_result_path)
    delivery_state = _resolve_delivery_state(
        outbox_exists=outbox_path.exists(),
        sent_exists=sent_path.exists(),
        delivery_ready_exists=delivery_ready_path.exists(),
        send_instruction_exists=send_instruction_path.exists(),
        processed_instruction_exists=processed_instruction_path.exists(),
        failed_instruction_exists=failed_instruction_path.exists(),
        dispatch_result=dispatch_result,
    )
    return {
        "state": delivery_state,
        "outbox_exists": outbox_path.exists(),
        "sent_exists": sent_path.exists(),
        "delivery_ready_exists": delivery_ready_path.exists(),
        "send_instruction_exists": send_instruction_path.exists(),
        "processed_instruction_exists": processed_instruction_path.exists(),
        "failed_instruction_exists": failed_instruction_path.exists(),
        "dispatch_result_exists": dispatch_result_path.exists(),
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


def build_status_summary(
    task_id: str,
    *,
    paths: Optional[TaskPaths] = None,
    config: Optional[TaskSystemConfig] = None,
    config_path: Optional[Path] = None,
) -> dict[str, object]:
    resolved_paths = _resolve_paths(paths, config=config, config_path=config_path)
    store = TaskStore(paths=resolved_paths)
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
        "delivery": build_delivery_summary(task_id, paths=resolved_paths),
    }


def list_inflight_statuses(
    *,
    paths: Optional[TaskPaths] = None,
    config: Optional[TaskSystemConfig] = None,
    config_path: Optional[Path] = None,
) -> list[dict[str, object]]:
    store = TaskStore(paths=_resolve_paths(paths, config=config, config_path=config_path))
    return [build_status_summary(path.stem, paths=store.paths) for path in store.list_inflight()]


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
        f"- delivery.state: {status['delivery']['state']}",
        f"- delivery.outbox_exists: {status['delivery']['outbox_exists']}",
        f"- delivery.sent_exists: {status['delivery']['sent_exists']}",
        f"- delivery.delivery_ready_exists: {status['delivery']['delivery_ready_exists']}",
        f"- delivery.send_instruction_exists: {status['delivery']['send_instruction_exists']}",
        f"- delivery.processed_instruction_exists: {status['delivery']['processed_instruction_exists']}",
        f"- delivery.failed_instruction_exists: {status['delivery']['failed_instruction_exists']}",
        f"- delivery.dispatch_result_exists: {status['delivery']['dispatch_result_exists']}",
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
            f"- {status['task_id']} | {status['status']} | delivery={status['delivery']['state']} | {status['task_label']}"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    usage = "usage: task_status.py <task_id> [--json]\n   or: task_status.py --list [--json]\n   or: task_status.py --json"
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

    task_id = args[0]
    if len(args) > 1 and args[1] == "--json":
        print(json.dumps(build_status_summary(task_id), ensure_ascii=False, indent=2))
    else:
        print(render_status_markdown(task_id), end="")
