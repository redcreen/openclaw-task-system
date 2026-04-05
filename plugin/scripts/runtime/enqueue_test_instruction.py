#!/usr/bin/env python3
from __future__ import annotations

import json
import uuid
from argparse import ArgumentParser
from pathlib import Path

from task_config import load_task_system_config
from task_state import TaskPaths, atomic_write_json

INSTRUCTION_SCHEMA = "openclaw.task-system.send-instruction.v1"


def instruction_dir(paths: TaskPaths) -> Path:
    return paths.data_dir / "send-instructions"


def build_instruction(
    *,
    task_id: str,
    agent_id: str,
    session_key: str,
    channel: str,
    chat_id: str,
    message: str,
    account_id: str | None = None,
) -> dict[str, str]:
    payload = {
        "schema": INSTRUCTION_SCHEMA,
        "task_id": task_id,
        "agent_id": agent_id,
        "session_key": session_key,
        "channel": channel,
        "chat_id": chat_id,
        "message": message,
    }
    if account_id:
        payload["account_id"] = account_id
    return payload


def enqueue_instruction(payload: dict[str, str], *, paths: TaskPaths) -> Path:
    instruction_dir(paths).mkdir(parents=True, exist_ok=True)
    path = instruction_dir(paths) / f"{payload['task_id']}.json"
    atomic_write_json(path, payload)
    return path


def parse_args() -> object:
    parser = ArgumentParser(description="Create a test send-instruction for external delivery validation.")
    parser.add_argument("--config", help="Task system config path.")
    parser.add_argument("--task-id", help="Task id to use. Default: generated.")
    parser.add_argument("--agent-id", default="main")
    parser.add_argument("--session-key", default="session:test:dispatch")
    parser.add_argument("--channel", required=True)
    parser.add_argument("--chat-id", required=True)
    parser.add_argument("--message", required=True)
    parser.add_argument("--account-id")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    config = load_task_system_config(config_path=Path(args.config).expanduser() if args.config else None)
    payload = build_instruction(
        task_id=args.task_id or f"task_test_{uuid.uuid4().hex}",
        agent_id=args.agent_id,
        session_key=args.session_key,
        channel=args.channel,
        chat_id=args.chat_id,
        message=args.message,
        account_id=args.account_id,
    )
    path = enqueue_instruction(payload, paths=config.build_paths())
    print(json.dumps({"instruction_path": str(path), "payload": payload}, ensure_ascii=False, indent=2))
