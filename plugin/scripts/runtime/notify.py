#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from task_config import TaskSystemConfig, load_task_system_config
from task_state import TaskPaths, TaskState, TaskStore, default_paths, now_iso

DEFAULT_NOTIFICATION_TEXT = (
    "当前任务仍在执行中，但 30 秒内还没有新的阶段结果；"
    "我会继续检查真实进展或阻塞点，并在下一条同步。"
)


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


def mark_notified(
    task_id: str,
    *,
    paths: Optional[TaskPaths] = None,
    config: Optional[TaskSystemConfig] = None,
    config_path: Optional[Path] = None,
) -> TaskState:
    store = TaskStore(paths=_resolve_paths(paths, config=config, config_path=config_path))
    task = store.load_task(task_id, allow_archive=False)
    ts = now_iso()
    task.last_monitor_notify_at = ts
    task.notify_count = int(task.notify_count) + 1
    task.monitor_state = "notified"
    task.updated_at = ts
    task.last_internal_touch_at = ts
    return store.save_task(task)


def build_payload(task: TaskState, text: str = DEFAULT_NOTIFICATION_TEXT) -> dict[str, object]:
    return {
        "schema": "openclaw.task-system.notify.v1",
        "task_id": task.task_id,
        "agent_id": task.agent_id,
        "channel": task.channel,
        "account_id": task.account_id,
        "chat_id": task.chat_id,
        "session_key": task.session_key,
        "message": text,
        "status": task.status,
        "updated_at": task.updated_at,
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        raise SystemExit("usage: notify.py <task_id>")
    task = mark_notified(sys.argv[1])
    payload = build_payload(task)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
