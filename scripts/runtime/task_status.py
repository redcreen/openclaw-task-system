#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from task_config import TaskSystemConfig, load_task_system_config
from task_state import TaskPaths, TaskStore, default_paths


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
    store = TaskStore(paths=_resolve_paths(paths, config=config, config_path=config_path))
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
    ]
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
        lines.append(f"- {status['task_id']} | {status['status']} | {status['task_label']}")
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
