#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from task_state import TaskPaths, TaskStore, atomic_write_json, default_paths

OUTBOX_SCHEMA = "openclaw.task-system.outbox.v1"


def outbox_dir(paths: TaskPaths) -> Path:
    return paths.data_dir / "outbox"


def ensure_dirs(paths: TaskPaths) -> None:
    outbox_dir(paths).mkdir(parents=True, exist_ok=True)


def load_task(task_id: str, *, paths: Optional[TaskPaths] = None) -> dict[str, Any]:
    store = TaskStore(paths=paths)
    return store.load_task(task_id, allow_archive=False).to_dict()


def write_outbox(task: dict[str, Any], *, message: str, paths: Optional[TaskPaths] = None) -> Path:
    resolved_paths = paths or default_paths()
    ensure_dirs(resolved_paths)
    payload = {
        "schema": OUTBOX_SCHEMA,
        "task_id": task["task_id"],
        "agent_id": task.get("agent_id"),
        "session_key": task.get("session_key"),
        "channel": task.get("channel"),
        "account_id": task.get("account_id"),
        "chat_id": task.get("chat_id"),
        "message": message,
        "created_at": task.get("updated_at") or task.get("last_internal_touch_at"),
    }
    path = outbox_dir(resolved_paths) / f"{task['task_id']}.json"
    atomic_write_json(path, payload)
    return path


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        raise SystemExit("usage: emit_task_event.py <task_id>")
    task = load_task(sys.argv[1])
    path = write_outbox(
        task,
        message="当前任务仍在执行中，但 30 秒内还没有新的阶段结果；我会继续检查真实进展或阻塞点，并在下一条同步。",
    )
    print(path)
