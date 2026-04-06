#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from task_state import TaskPaths, atomic_write_json, default_paths

DELIVERY_SCHEMA = "openclaw.task-system.delivery.v1"


def sent_dir(paths: TaskPaths) -> Path:
    return paths.data_dir / "sent"


def delivery_dir(paths: TaskPaths) -> Path:
    return paths.data_dir / "delivery-ready"


def ensure_dirs(paths: TaskPaths) -> None:
    delivery_dir(paths).mkdir(parents=True, exist_ok=True)


def load_sent(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_delivery_payload(payload: dict[str, Any]) -> dict[str, Any]:
    event = payload.get("event", payload)
    return {
        "schema": DELIVERY_SCHEMA,
        "task_id": event["task_id"],
        "agent_id": event.get("agent_id"),
        "session_key": event.get("session_key"),
        "channel": event.get("channel"),
        "account_id": event.get("account_id"),
        "chat_id": event.get("chat_id"),
        "message": event["message"],
        "reply_to_id": event.get("reply_to_id"),
        "thread_id": event.get("thread_id"),
    }


def write_delivery_ready(payload: dict[str, Any], name: str, *, paths: TaskPaths) -> Path:
    ensure_dirs(paths)
    out = delivery_dir(paths) / name
    atomic_write_json(out, payload)
    return out


def prepare_all(*, paths: Optional[TaskPaths] = None) -> list[str]:
    resolved_paths = paths or default_paths()
    ensure_dirs(resolved_paths)
    written = []
    for path in sorted(sent_dir(resolved_paths).glob("*.json")):
        payload = load_sent(path)
        delivery = build_delivery_payload(payload)
        out = write_delivery_ready(delivery, path.name, paths=resolved_paths)
        written.append(str(out))
    return written


if __name__ == "__main__":
    print(json.dumps(prepare_all(), ensure_ascii=False, indent=2))
