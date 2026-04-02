#!/usr/bin/env python3
from __future__ import annotations

import json
from argparse import ArgumentParser
from pathlib import Path
from typing import Optional

from task_config import load_task_system_config
from task_state import TaskPaths, default_paths

FINAL_INSTRUCTION_DIRS = ("processed-instructions", "failed-instructions")
INTERMEDIATE_DIRS = ("outbox", "sent", "delivery-ready", "send-instructions")


def _resolve_paths(*, paths: Optional[TaskPaths] = None, config_path: Optional[Path] = None) -> TaskPaths:
    if paths is not None:
        return paths
    config = load_task_system_config(config_path=config_path)
    return config.build_paths() or default_paths()


def _artifact_path(paths: TaskPaths, directory: str, task_id: str) -> Path:
    return paths.data_dir / directory / f"{task_id}.json"


def _list_finalized_task_ids(paths: TaskPaths) -> list[str]:
    task_ids: set[str] = set()
    for directory in FINAL_INSTRUCTION_DIRS:
        base = paths.data_dir / directory
        if not base.exists():
            continue
        for path in base.glob("*.json"):
            task_ids.add(path.stem)
    return sorted(task_ids)


def reconcile_delivery_artifacts(
    *,
    paths: Optional[TaskPaths] = None,
    config_path: Optional[Path] = None,
    apply_changes: bool = False,
) -> list[dict[str, object]]:
    resolved_paths = _resolve_paths(paths=paths, config_path=config_path)
    findings: list[dict[str, object]] = []

    for task_id in _list_finalized_task_ids(resolved_paths):
        stale_paths = [
            _artifact_path(resolved_paths, directory, task_id)
            for directory in INTERMEDIATE_DIRS
            if _artifact_path(resolved_paths, directory, task_id).exists()
        ]
        if not stale_paths:
            continue
        finding = {
            "task_id": task_id,
            "stale_paths": [str(path) for path in stale_paths],
            "applied": apply_changes,
        }
        if apply_changes:
            for path in stale_paths:
                path.unlink(missing_ok=True)
        findings.append(finding)
    return findings


def render_markdown(findings: list[dict[str, object]]) -> str:
    if not findings:
        return "# Delivery Reconcile\n\n- clean\n"
    lines = ["# Delivery Reconcile", ""]
    for finding in findings:
        lines.append(f"- {finding['task_id']} | applied={finding['applied']}")
        for stale_path in finding["stale_paths"]:
            lines.append(f"  stale: {stale_path}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    parser = ArgumentParser(description="Detect or clean stale delivery artifacts after final instruction archival.")
    parser.add_argument("config", nargs="?", default=None, help="Optional task system config path")
    parser.add_argument("--apply", action="store_true", help="Delete stale intermediate delivery artifacts")
    parser.add_argument("--json", action="store_true", help="Render JSON output")
    args = parser.parse_args()

    config_path = Path(args.config).expanduser() if args.config else None
    findings = reconcile_delivery_artifacts(config_path=config_path, apply_changes=args.apply)
    if args.json:
        print(json.dumps(findings, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(findings), end="")
