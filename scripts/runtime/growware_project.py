#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
POLICY_SOURCE_DIR = Path("docs") / "policy"
POLICY_DIR = Path(".policy")
POLICY_RULES_DIR = POLICY_DIR / "rules"
POLICY_DOC_BASENAMES = ("interaction-contracts", "verification-rules")


def resolve_project_root(project_root: Path | None = None) -> Path:
    return (project_root or PROJECT_ROOT).resolve()


def resolve_growware_dir(project_root: Path | None = None) -> Path:
    return resolve_project_root(project_root) / ".growware"


def required_growware_files(project_root: Path | None = None) -> list[Path]:
    root = resolve_growware_dir(project_root)
    policy_root = resolve_project_root(project_root)
    required = [
        root / "project.json",
        root / "channels.json",
        root / "contracts" / "feedback-event.v1.json",
        root / "contracts" / "incident-record.v1.json",
        root / "policies" / "feedback-intake.v1.json",
        root / "policies" / "judge.v1.json",
        root / "policies" / "deploy-gate.v1.json",
        root / "ops" / "daemon-interface.v1.json",
    ]
    for basename in POLICY_DOC_BASENAMES:
        required.append(policy_root / POLICY_SOURCE_DIR / f"{basename}.md")
        required.append(policy_root / POLICY_SOURCE_DIR / f"{basename}.zh-CN.md")
    required.extend(
        [
            policy_root / POLICY_DIR / "manifest.json",
            policy_root / POLICY_DIR / "index.json",
            policy_root / POLICY_DIR / "provenance.json",
            policy_root / POLICY_RULES_DIR / "growware.feedback-intake.same-session.v1.json",
            policy_root / POLICY_RULES_DIR / "growware.project.local-deploy.v1.json",
        ]
    )
    return required


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


def resolve_policy_dir(project_root: Path | None = None) -> Path:
    return resolve_project_root(project_root) / POLICY_DIR


def load_policy_manifest(project_root: Path | None = None) -> dict[str, Any]:
    root = resolve_policy_dir(project_root)
    return read_json_object(root / "manifest.json")


def load_policy_index(project_root: Path | None = None) -> dict[str, Any]:
    root = resolve_policy_dir(project_root)
    return read_json_object(root / "index.json")


def load_policy_rule(rule_id: str, project_root: Path | None = None) -> dict[str, Any]:
    root = resolve_policy_dir(project_root)
    return read_json_object(root / "rules" / f"{rule_id}.json")


def load_feedback_intake_policy(project_root: Path | None = None) -> dict[str, Any]:
    return load_policy_rule("growware.feedback-intake.same-session.v1", project_root)


def build_summary(project_root: Path | None = None) -> dict[str, Any]:
    project = load_project_definition(project_root)
    channels = load_channel_definition(project_root)
    feedback_intake = load_feedback_intake_policy(project_root)
    policy_manifest = load_policy_manifest(project_root)
    policy_index = load_policy_index(project_root)
    return {
        "projectRoot": str(resolve_project_root(project_root)),
        "growwareDir": str(resolve_growware_dir(project_root)),
        "policyDir": str(resolve_policy_dir(project_root)),
        "projectId": project.get("projectId"),
        "feedbackChannel": channels.get("feedbackChannel"),
        "runtimeSurface": channels.get("runtimeSurface"),
        "daemon": ((project.get("growware") or {}).get("daemon") or {}),
        "policyManifest": policy_manifest,
        "policyIndex": policy_index,
        "feedbackIntake": feedback_intake,
    }
