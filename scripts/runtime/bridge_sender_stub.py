#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BRIDGE_DIR = Path("/Users/redcreen/.openclaw/workspace/data/watchdog/bridge-ready")
HANDLED_DIR = Path("/Users/redcreen/.openclaw/workspace/data/watchdog/bridge-handled")


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def ensure_dirs() -> None:
    HANDLED_DIR.mkdir(parents=True, exist_ok=True)


def load_payload(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_send_plan(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_key": payload.get("session_key"),
        "channel": payload.get("channel"),
        "chat_id": payload.get("chat_id"),
        "message": payload.get("message"),
        "preferred_path": "session_key",
        "fallback_path": "channel+chat_id",
    }


def handle_all() -> list[dict[str, Any]]:
    ensure_dirs()
    results = []
    for path in sorted(BRIDGE_DIR.glob("*.json")):
        payload = load_payload(path)
        plan = build_send_plan(payload)
        handled = HANDLED_DIR / path.name
        record = {
            "handled_at": now_iso(),
            "bridge_payload": payload,
            "send_plan": plan,
            "status": "stubbed-not-sent"
        }
        with handled.open("w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
            f.write("\n")
        path.unlink(missing_ok=True)
        results.append(record)
    return results


if __name__ == "__main__":
    print(json.dumps(handle_all(), ensure_ascii=False, indent=2))
