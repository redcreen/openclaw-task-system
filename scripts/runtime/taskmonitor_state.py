#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Optional

from task_config import load_task_system_config


def _state_path(*, config_path: Optional[Path] = None) -> Path:
    config = load_task_system_config(config_path=config_path)
    paths = config.build_paths()
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    return paths.data_dir / "taskmonitor-overrides.json"


def _read_state(path: Path) -> dict[str, bool]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    raw = payload.get("sessions")
    if not isinstance(raw, dict):
        return {}
    result: dict[str, bool] = {}
    for key, value in raw.items():
        normalized = str(key or "").strip()
        if not normalized:
            continue
        result[normalized] = bool(value)
    return result


def _write_state(path: Path, sessions: dict[str, bool]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump({"sessions": sessions}, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
        os.replace(tmp_path, path)
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except OSError:
            pass


def get_taskmonitor_enabled(session_key: str, *, config_path: Optional[Path] = None) -> bool:
    normalized = str(session_key or "").strip()
    if not normalized:
        return True
    sessions = _read_state(_state_path(config_path=config_path))
    return sessions.get(normalized, True)


def set_taskmonitor_enabled(
    session_key: str,
    enabled: bool,
    *,
    config_path: Optional[Path] = None,
) -> dict[str, object]:
    normalized = str(session_key or "").strip()
    if not normalized:
        raise ValueError("session_key is required")
    path = _state_path(config_path=config_path)
    sessions = _read_state(path)
    sessions[normalized] = bool(enabled)
    _write_state(path, sessions)
    return {
        "session_key": normalized,
        "enabled": bool(enabled),
        "state_path": str(path),
    }
