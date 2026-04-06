#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from task_state import TaskPaths, atomic_write_json, default_paths

DELIVERY_INSTRUCTION_SCHEMA = "openclaw.task-system.send-instruction.v1"


def delivery_dir(paths: TaskPaths) -> Path:
    return paths.data_dir / "delivery-ready"


def instruction_dir(paths: TaskPaths) -> Path:
    return paths.data_dir / "send-instructions"


def ensure_dirs(paths: TaskPaths) -> None:
    instruction_dir(paths).mkdir(parents=True, exist_ok=True)


def load_delivery(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_instruction(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": DELIVERY_INSTRUCTION_SCHEMA,
        "task_id": payload["task_id"],
        "agent_id": payload.get("agent_id"),
        "session_key": payload.get("session_key"),
        "channel": payload.get("channel"),
        "account_id": payload.get("account_id"),
        "chat_id": payload.get("chat_id"),
        "message": payload["message"],
        "reply_to_id": payload.get("reply_to_id"),
        "thread_id": payload.get("thread_id"),
    }


def write_instruction(payload: dict[str, Any], name: str, *, paths: TaskPaths) -> Path:
    ensure_dirs(paths)
    target = instruction_dir(paths) / name
    atomic_write_json(target, payload)
    return target


def dispatch_all(*, paths: Optional[TaskPaths] = None) -> list[str]:
    resolved_paths = paths or default_paths()
    ensure_dirs(resolved_paths)
    written: list[str] = []
    for path in sorted(delivery_dir(resolved_paths).glob("*.json")):
        payload = load_delivery(path)
        instruction = build_instruction(payload)
        out = write_instruction(instruction, path.name, paths=resolved_paths)
        written.append(str(out))
    return written


if __name__ == "__main__":
    print(json.dumps(dispatch_all(), ensure_ascii=False, indent=2))
