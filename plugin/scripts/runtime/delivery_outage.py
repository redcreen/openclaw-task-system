#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from task_config import load_task_system_config
from task_state import TaskPaths, atomic_write_json, default_paths


def _resolve_paths(*, paths: Optional[TaskPaths] = None, config_path: Optional[Path] = None) -> TaskPaths:
    if paths is not None:
        return paths
    config = load_task_system_config(config_path=config_path)
    return config.build_paths() or default_paths()


def outage_registry_path(*, paths: Optional[TaskPaths] = None, config_path: Optional[Path] = None) -> Path:
    resolved_paths = _resolve_paths(paths=paths, config_path=config_path)
    diagnostics_dir = resolved_paths.data_dir / "diagnostics"
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    return diagnostics_dir / "delivery-outages.json"


def load_outages(*, paths: Optional[TaskPaths] = None, config_path: Optional[Path] = None) -> list[dict[str, object]]:
    registry = outage_registry_path(paths=paths, config_path=config_path)
    if not registry.exists():
        return []
    with registry.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return list(payload.get("outages") or [])


def save_outages(
    outages: list[dict[str, object]],
    *,
    paths: Optional[TaskPaths] = None,
    config_path: Optional[Path] = None,
) -> Path:
    registry = outage_registry_path(paths=paths, config_path=config_path)
    atomic_write_json(
        registry,
        {
            "schema": "openclaw.task-system.delivery-outages.v1",
            "outages": outages,
        },
    )
    return registry


def acknowledge_outage(
    *,
    channel: str,
    chat_id: str,
    reason: str,
    paths: Optional[TaskPaths] = None,
    config_path: Optional[Path] = None,
) -> dict[str, object]:
    outages = load_outages(paths=paths, config_path=config_path)
    retained = [entry for entry in outages if not (entry.get("channel") == channel and entry.get("chat_id") == chat_id)]
    entry = {
        "channel": channel,
        "chat_id": chat_id,
        "reason": reason,
        "acknowledged_at": datetime.now(timezone.utc).isoformat(),
    }
    retained.append(entry)
    save_outages(retained, paths=paths, config_path=config_path)
    return entry


def clear_outage(
    *,
    channel: str,
    chat_id: str,
    paths: Optional[TaskPaths] = None,
    config_path: Optional[Path] = None,
) -> int:
    outages = load_outages(paths=paths, config_path=config_path)
    retained = [entry for entry in outages if not (entry.get("channel") == channel and entry.get("chat_id") == chat_id)]
    removed = len(outages) - len(retained)
    save_outages(retained, paths=paths, config_path=config_path)
    return removed


def find_outage(
    *,
    channel: str,
    chat_id: str,
    paths: Optional[TaskPaths] = None,
    config_path: Optional[Path] = None,
) -> Optional[dict[str, object]]:
    for entry in load_outages(paths=paths, config_path=config_path):
        if entry.get("channel") == channel and entry.get("chat_id") == chat_id:
            return entry
    return None
