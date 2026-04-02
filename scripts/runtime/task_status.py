#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Optional

from task_config import TaskSystemConfig, load_task_system_config
from task_state import TaskPaths, TaskStore, default_paths

FINAL_INSTRUCTION_DIRS = ("processed-instructions", "failed-instructions")
INTERMEDIATE_DELIVERY_DIRS = ("outbox", "sent", "delivery-ready", "send-instructions")


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

    archived_counts: Counter[str] = Counter()
    for archived_path in sorted(resolved_paths.archive_dir.glob("*.json")):
        archived_payload = _load_json_if_exists(archived_path) or {}
        archived_status = archived_payload.get("status")
        if archived_status:
            archived_counts[str(archived_status)] += 1

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
    if overview["active_tasks"]:
        lines.append("")
        lines.append("## Active Tasks")
        lines.append("")
        for status in overview["active_tasks"]:
            lines.append(
                f"- {status['task_id']} | {status['status']} | delivery={status['delivery']['state']} | {status['task_label']}"
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
