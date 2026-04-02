#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DELIVERED_DIR = Path("/Users/redcreen/.openclaw/workspace/data/watchdog/delivered")
BRIDGE_DIR = Path("/Users/redcreen/.openclaw/workspace/data/watchdog/bridge-ready")


def ensure_dirs() -> None:
    BRIDGE_DIR.mkdir(parents=True, exist_ok=True)


def load_payload(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_bridge(payload: dict[str, Any], name: str) -> Path:
    ensure_dirs()
    out = BRIDGE_DIR / name
    bridge = {
        "schema": "openclaw.watchdog.bridge.v1",
        "channel": payload.get("channel"),
        "chat_id": payload.get("chat_id"),
        "session_key": payload.get("session_key"),
        "message": payload.get("message"),
        "recommended_tool": "message",
    }
    with out.open("w", encoding="utf-8") as f:
        json.dump(bridge, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return out


def prepare_all() -> list[str]:
    ensure_dirs()
    written = []
    for path in sorted(DELIVERED_DIR.glob("*.json")):
        payload = load_payload(path)
        out = write_bridge(payload, path.name)
        written.append(str(out))
    return written


if __name__ == "__main__":
    print(json.dumps(prepare_all(), ensure_ascii=False, indent=2))
