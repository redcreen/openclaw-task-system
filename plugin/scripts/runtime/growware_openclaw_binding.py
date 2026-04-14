#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from growware_project import load_channel_definition, load_project_definition, resolve_project_root


DEFAULT_OPENCLAW_CONFIG = Path.home() / ".openclaw" / "openclaw.json"
DEFAULT_BACKUP_DIR = Path.home() / ".openclaw" / "backups"
PLUGIN_ID = "openclaw-task-system"


def read_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return payload


def ensure_object(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        value = {}
        parent[key] = value
    return value


def ensure_list(parent: dict[str, Any], key: str) -> list[Any]:
    value = parent.get(key)
    if not isinstance(value, list):
        value = []
        parent[key] = value
    return value


def build_growware_agent(project_root: Path, daemon: dict[str, Any]) -> dict[str, Any]:
    agent_dir = Path(str(daemon.get("agentDir") or "")).expanduser()
    workspace = Path(str(daemon.get("workspace") or project_root)).expanduser()
    return {
        "id": str(daemon.get("agentId") or "growware"),
        "name": "growware",
        "workspace": str(workspace.resolve()),
        "agentDir": str(agent_dir.resolve()) if str(agent_dir) else str((Path.home() / ".openclaw" / "agents" / "growware" / "agent").resolve()),
    }


def ensure_growware_binding(data: dict[str, Any], *, project_root: Path) -> tuple[dict[str, Any], bool, dict[str, Any]]:
    updated = deepcopy(data)
    changed = False

    project = load_project_definition(project_root)
    channels = load_channel_definition(project_root)
    daemon = ((project.get("growware") or {}).get("daemon") or {})
    feedback = channels.get("feedbackChannel") or {}
    target_agent_id = str(daemon.get("agentId") or "growware")
    target_account = str(feedback.get("accountId") or "feishu6-chat")
    target_provider = str(feedback.get("provider") or "feishu")

    agents = ensure_object(updated, "agents")
    agent_list = ensure_list(agents, "list")
    desired_agent = build_growware_agent(project_root, daemon)
    Path(desired_agent["agentDir"]).mkdir(parents=True, exist_ok=True)

    existing_agent = next((item for item in agent_list if isinstance(item, dict) and item.get("id") == target_agent_id), None)
    if existing_agent is None:
        agent_list.append(desired_agent)
        changed = True
    elif existing_agent != desired_agent:
        existing_agent.clear()
        existing_agent.update(desired_agent)
        changed = True

    plugins = ensure_object(updated, "plugins")
    allow = ensure_list(plugins, "allow")
    if PLUGIN_ID not in allow:
        allow.append(PLUGIN_ID)
        changed = True

    entries = ensure_object(plugins, "entries")
    existing_entry = entries.get(PLUGIN_ID)
    if not isinstance(existing_entry, dict):
        entries[PLUGIN_ID] = {"enabled": True, "config": {"enabled": True}}
        changed = True
    else:
        if existing_entry.get("enabled") is not True:
            existing_entry["enabled"] = True
            changed = True
        config = ensure_object(existing_entry, "config")
        if config.get("enabled") is not True:
            config["enabled"] = True
            changed = True

    bindings = ensure_list(updated, "bindings")
    matched = False
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        match = binding.get("match")
        if not isinstance(match, dict):
            continue
        if match.get("channel") == target_provider and match.get("accountId") == target_account:
            matched = True
            if binding.get("agentId") != target_agent_id:
                binding["agentId"] = target_agent_id
                changed = True
            binding["type"] = "route"
            binding["comment"] = "Growware Project 1 feedback / approval / notification ingress"
    if not matched:
        bindings.append(
            {
                "type": "route",
                "agentId": target_agent_id,
                "comment": "Growware Project 1 feedback / approval / notification ingress",
                "match": {
                    "channel": target_provider,
                    "accountId": target_account,
                },
            }
        )
        changed = True

    report = {
        "targetAgentId": target_agent_id,
        "feedbackProvider": target_provider,
        "feedbackAccountId": target_account,
        "agentWorkspace": desired_agent["workspace"],
    }
    return updated, changed, report


def validate_live_config() -> dict[str, Any]:
    result = subprocess.run(
        ["openclaw", "config", "validate", "--json"],
        check=False,
        capture_output=True,
        text=True,
    )
    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    if stdout:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            payload = {"valid": False, "stdout": stdout}
    else:
        payload = {"valid": result.returncode == 0}
    if stderr:
        payload["stderr"] = stderr
    payload["returncode"] = result.returncode
    return payload


def write_and_validate(
    updated: dict[str, Any],
    *,
    config_path: Path,
    backup_dir: Path,
    restart: bool,
) -> dict[str, Any]:
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = backup_dir / f"openclaw.json.{timestamp}.bak"
    if config_path.exists():
        shutil.copy2(config_path, backup_path)
    else:
        backup_path.write_text("{}\n", encoding="utf-8")

    config_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    validation = validate_live_config()
    if not validation.get("valid"):
        shutil.copy2(backup_path, config_path)
        validation["restoredBackup"] = str(backup_path)
        validation["applied"] = False
        return validation

    if restart:
        restart_result = subprocess.run(
            ["openclaw", "gateway", "restart", "--json"],
            check=False,
            capture_output=True,
            text=True,
        )
        validation["restart"] = {
            "returncode": restart_result.returncode,
            "stdout": restart_result.stdout.strip(),
            "stderr": restart_result.stderr.strip(),
        }
    validation["backupPath"] = str(backup_path)
    validation["applied"] = True
    return validation


def run_binding(
    *,
    config_path: Path = DEFAULT_OPENCLAW_CONFIG,
    project_root: Path | None = None,
    write: bool = False,
    restart: bool = False,
    backup_dir: Path = DEFAULT_BACKUP_DIR,
) -> dict[str, Any]:
    root = resolve_project_root(project_root)
    current = read_config(config_path)
    updated, changed, report = ensure_growware_binding(current, project_root=root)
    payload: dict[str, Any] = {
        "configPath": str(config_path),
        "projectRoot": str(root),
        "changed": changed,
        "write": write,
        "binding": report,
    }
    if write and changed:
        payload["validation"] = write_and_validate(updated, config_path=config_path, backup_dir=backup_dir, restart=restart)
    elif write:
        payload["validation"] = {"valid": True, "applied": False, "reason": "no-change"}
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preview or apply the Growware feishu6 -> growware OpenClaw binding.")
    parser.add_argument("--config-path", type=Path, default=DEFAULT_OPENCLAW_CONFIG)
    parser.add_argument("--project-root", type=Path, default=resolve_project_root())
    parser.add_argument("--backup-dir", type=Path, default=DEFAULT_BACKUP_DIR)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--restart", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def render_markdown(payload: dict[str, Any]) -> str:
    lines = ["# Growware OpenClaw Binding", ""]
    lines.append(f"- config_path: `{payload['configPath']}`")
    lines.append(f"- project_root: `{payload['projectRoot']}`")
    lines.append(f"- changed: `{str(payload['changed']).lower()}`")
    lines.append(f"- write: `{str(payload['write']).lower()}`")
    binding = payload["binding"]
    lines.append(f"- target_agent: `{binding['targetAgentId']}`")
    lines.append(f"- feedback_channel: `{binding['feedbackProvider']}:{binding['feedbackAccountId']}`")
    lines.append(f"- workspace: `{binding['agentWorkspace']}`")
    validation = payload.get("validation")
    if validation:
        lines.append(f"- validation_valid: `{str(validation.get('valid')).lower()}`")
        lines.append(f"- applied: `{str(validation.get('applied')).lower()}`")
        if validation.get("backupPath"):
            lines.append(f"- backup_path: `{validation['backupPath']}`")
        if validation.get("restoredBackup"):
            lines.append(f"- restored_backup: `{validation['restoredBackup']}`")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    payload = run_binding(
        config_path=args.config_path,
        project_root=args.project_root,
        write=args.write,
        restart=args.restart,
        backup_dir=args.backup_dir,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(payload), end="")
    validation = payload.get("validation")
    if validation and validation.get("valid") is False:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
