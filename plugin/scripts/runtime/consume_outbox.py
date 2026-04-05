#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from task_state import TaskPaths, atomic_write_json, default_paths, now_iso


def outbox_dir(paths: TaskPaths) -> Path:
    return paths.data_dir / "outbox"


def sent_dir(paths: TaskPaths) -> Path:
    return paths.data_dir / "sent"


def ensure_dirs(paths: TaskPaths) -> None:
    outbox_dir(paths).mkdir(parents=True, exist_ok=True)
    sent_dir(paths).mkdir(parents=True, exist_ok=True)


def load_event(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def mark_sent(path: Path, payload: dict[str, Any], *, paths: TaskPaths) -> Path:
    enriched = dict(payload)
    enriched["sent_at"] = now_iso()
    target = sent_dir(paths) / path.name
    atomic_write_json(target, enriched)
    path.unlink(missing_ok=True)
    return target


def consume_once(*, paths: Optional[TaskPaths] = None) -> list[dict[str, Any]]:
    resolved_paths = paths or default_paths()
    ensure_dirs(resolved_paths)
    results = []
    for path in sorted(outbox_dir(resolved_paths).glob("*.json")):
        payload = load_event(path)
        sent_path = mark_sent(path, payload, paths=resolved_paths)
        results.append(
            {
                "event": payload,
                "sent_record": str(sent_path),
            }
        )
    return results


if __name__ == "__main__":
    print(json.dumps(consume_once(), ensure_ascii=False, indent=2))
