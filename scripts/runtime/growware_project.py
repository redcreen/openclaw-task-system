#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def resolve_project_root(project_root: Path | None = None) -> Path:
    return (project_root or PROJECT_ROOT).resolve()


def resolve_growware_dir(project_root: Path | None = None) -> Path:
    return resolve_project_root(project_root) / ".growware"


def required_growware_files(project_root: Path | None = None) -> list[Path]:
    root = resolve_growware_dir(project_root)
    return [
        root / "project.json",
        root / "channels.json",
        root / "contracts" / "feedback-event.v1.json",
        root / "contracts" / "incident-record.v1.json",
        root / "policies" / "feedback-intake.v1.json",
        root / "policies" / "judge.v1.json",
        root / "policies" / "deploy-gate.v1.json",
        root / "ops" / "daemon-interface.v1.json",
    ]


def read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return payload


def load_project_definition(project_root: Path | None = None) -> dict[str, Any]:
    root = resolve_growware_dir(project_root)
    return read_json_object(root / "project.json")


def load_channel_definition(project_root: Path | None = None) -> dict[str, Any]:
    root = resolve_growware_dir(project_root)
    return read_json_object(root / "channels.json")


def load_feedback_intake_policy(project_root: Path | None = None) -> dict[str, Any]:
    root = resolve_growware_dir(project_root)
    return read_json_object(root / "policies" / "feedback-intake.v1.json")


def build_summary(project_root: Path | None = None) -> dict[str, Any]:
    project = load_project_definition(project_root)
    channels = load_channel_definition(project_root)
    feedback_intake = load_feedback_intake_policy(project_root)
    return {
        "projectRoot": str(resolve_project_root(project_root)),
        "growwareDir": str(resolve_growware_dir(project_root)),
        "projectId": project.get("projectId"),
        "feedbackChannel": channels.get("feedbackChannel"),
        "runtimeSurface": channels.get("runtimeSurface"),
        "daemon": ((project.get("growware") or {}).get("daemon") or {}),
        "feedbackIntake": feedback_intake,
    }
