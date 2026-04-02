#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HANDLED_DIR = Path("/Users/redcreen/.openclaw/workspace/data/watchdog/bridge-handled")
RUNTIME_READY_DIR = Path("/Users/redcreen/.openclaw/workspace/data/watchdog/runtime-ready")


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def ensure_dirs() -> None:
    RUNTIME_READY_DIR.mkdir(parents=True, exist_ok=True)


def load_record(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def project_runtime_send(record: dict[str, Any]) -> dict[str, Any]:
    plan = record.get("send_plan", {})
    return {
        "schema": "openclaw.watchdog.runtime-ready.v1",
        "prepared_at": now_iso(),
        "session_key": plan.get("session_key"),
        "channel": plan.get("channel"),
        "chat_id": plan.get("chat_id"),
        "message": plan.get("message"),
        "status": "ready-for-real-send"
    }


def prepare_all() -> list[str]:
    ensure_dirs()
    written = []
    for path in sorted(HANDLED_DIR.glob("*.json")):
        record = load_record(path)
        payload = project_runtime_send(record)
        out = RUNTIME_READY_DIR / path.name
        with out.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
        written.append(str(out))
    return written


if __name__ == "__main__":
    print(json.dumps(prepare_all(), ensure_ascii=False, indent=2))
