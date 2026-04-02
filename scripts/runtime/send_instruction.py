#!/usr/bin/env python3
from __future__ import annotations

import json
from typing import Any, Optional

from task_state import TaskPaths, TaskStore, default_paths


def build_send_instruction(task: dict[str, Any], *, message: Optional[str] = None) -> dict[str, Any]:
    return {
        "session_key": task.get("session_key"),
        "channel": task.get("channel"),
        "account_id": task.get("account_id"),
        "chat_id": task.get("chat_id"),
        "message": message
        or "当前任务仍在执行中，但 30 秒内还没有新的阶段结果；我会继续检查真实进展或阻塞点，并在下一条同步。",
    }


def load_task(task_id: str, *, paths: Optional[TaskPaths] = None) -> dict[str, Any]:
    store = TaskStore(paths=paths or default_paths())
    return store.load_task(task_id, allow_archive=False).to_dict()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        raise SystemExit("usage: send_instruction.py <task_id>")
    task = load_task(sys.argv[1])
    print(json.dumps(build_send_instruction(task), ensure_ascii=False, indent=2))
