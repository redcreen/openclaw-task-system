#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WATCHDOG_DIR = PROJECT_ROOT / "data" / "watchdog"
READY_DIR = WATCHDOG_DIR / "delivery-ready"
DELIVERED_DIR = WATCHDOG_DIR / "delivered"


def ensure_dirs() -> None:
    DELIVERED_DIR.mkdir(parents=True, exist_ok=True)


def load_payload(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def mark_delivered(path: Path, payload: dict[str, Any]) -> Path:
    ensure_dirs()
    target = DELIVERED_DIR / path.name
    with target.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    path.unlink(missing_ok=True)
    return target


def deliver_all() -> list[dict[str, Any]]:
    ensure_dirs()
    results = []
    for path in sorted(READY_DIR.glob("*.json")):
        payload = load_payload(path)
        delivered = mark_delivered(path, payload)
        results.append({
            "delivery_payload": payload,
            "delivered_record": str(delivered),
            "next_integration": "message or sessions_send",
        })
    return results


if __name__ == "__main__":
    print(json.dumps(deliver_all(), ensure_ascii=False, indent=2))
