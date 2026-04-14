#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from growware_project import resolve_project_root


PLUGIN_RUNTIME_DIR = Path("plugin") / "scripts" / "runtime"
PLUGIN_CONFIG_DIR = Path("plugin") / "config"
PLUGIN_SOURCE_DIR = Path("plugin") / "src"
GROWWARE_DIR = Path(".growware")
PLUGIN_MANIFEST = Path("plugin") / "openclaw.plugin.json"
INSTALLED_PLUGIN_ROOT = Path.home() / ".openclaw" / "extensions" / "openclaw-task-system"
BACKUP_ROOT = Path.home() / ".openclaw" / "backups" / "openclaw-task-system"


def run_command(cmd: list[str], *, cwd: Path) -> dict[str, Any]:
    result = subprocess.run(cmd, cwd=cwd, check=False, capture_output=True, text=True)
    return {
        "command": cmd,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "ok": result.returncode == 0,
    }


def _sync_dir(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        destination = target / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(item, destination)


def sync_installed_payload(project_root: Path) -> dict[str, Any]:
    plugin_root = project_root / "plugin"
    installed_root = INSTALLED_PLUGIN_ROOT
    runtime_source = project_root / PLUGIN_RUNTIME_DIR
    runtime_target = installed_root / "scripts" / "runtime"
    config_source = project_root / PLUGIN_CONFIG_DIR
    config_target = installed_root / "config"
    source_source = project_root / PLUGIN_SOURCE_DIR
    source_target = installed_root / "src"
    growware_source = project_root / GROWWARE_DIR
    growware_target = installed_root / ".growware"
    backup_dir = BACKUP_ROOT / datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)
    installed_root.mkdir(parents=True, exist_ok=True)

    if installed_root.exists():
        if runtime_target.exists():
            shutil.copytree(runtime_target, backup_dir / "runtime", dirs_exist_ok=True)
        if config_target.exists():
            shutil.copytree(config_target, backup_dir / "config", dirs_exist_ok=True)
        if source_target.exists():
            shutil.copytree(source_target, backup_dir / "src", dirs_exist_ok=True)
        if growware_target.exists():
            shutil.copytree(growware_target, backup_dir / ".growware", dirs_exist_ok=True)
        if (installed_root / "openclaw.plugin.json").exists():
            shutil.copy2(installed_root / "openclaw.plugin.json", backup_dir / "openclaw.plugin.json")

    _sync_dir(runtime_source, runtime_target)
    _sync_dir(config_source, config_target)
    if source_source.exists():
        _sync_dir(source_source, source_target)
    if growware_source.exists():
        _sync_dir(growware_source, growware_target)
    shutil.copy2(plugin_root / "openclaw.plugin.json", installed_root / "openclaw.plugin.json")
    return {
        "command": ["sync-installed-payload"],
        "returncode": 0,
        "stdout": json.dumps(
            {
                "mode": "runtime-sync-fallback",
                "installedRoot": str(installed_root),
                "backupDir": str(backup_dir),
            },
            ensure_ascii=False,
        ),
        "stderr": "",
        "ok": True,
    }


def run_local_deploy(project_root: Path | None = None) -> dict[str, Any]:
    root = resolve_project_root(project_root)
    steps = [
        run_command(["python3", "scripts/runtime/growware_policy_sync.py", "--write", "--json"], cwd=root),
        run_command(["python3", "scripts/runtime/growware_policy_sync.py", "--check", "--json"], cwd=root),
        run_command(["python3", "scripts/runtime/runtime_mirror.py", "--write"], cwd=root),
        run_command(["python3", "scripts/runtime/plugin_doctor.py", "--json"], cwd=root),
    ]
    install_step = run_command(["openclaw", "plugins", "install", "./plugin"], cwd=root)
    install_step["optional"] = True
    steps.append(install_step)

    deploy_mode = "plugin-install"
    deploy_succeeded = install_step["ok"]
    if not install_step["ok"]:
        forced_step = run_command(
            ["openclaw", "plugins", "install", "--dangerously-force-unsafe-install", "--link", "./plugin"],
            cwd=root,
        )
        forced_step["optional"] = True
        steps.append(forced_step)
        if forced_step["ok"]:
            deploy_mode = "plugin-link-install"
            deploy_succeeded = True
        else:
            steps.append(sync_installed_payload(root))
            deploy_mode = "runtime-sync-fallback"
            deploy_succeeded = True

    steps.append(run_command(["openclaw", "gateway", "restart", "--json"], cwd=root))
    steps.append(run_command(["python3", "scripts/runtime/plugin_smoke.py", "--json"], cwd=root))
    steps.append(run_command(["python3", "scripts/runtime/plugin_install_drift.py", "--json"], cwd=root))
    required_ok = all(step["ok"] for step in steps if not step.get("optional"))
    return {
        "ok": deploy_succeeded and required_ok,
        "projectRoot": str(root),
        "deployMode": deploy_mode,
        "steps": steps,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local Growware deploy path for openclaw-task-system.")
    parser.add_argument("--project-root", type=Path, default=resolve_project_root())
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def render_markdown(payload: dict[str, Any]) -> str:
    lines = ["# Growware Local Deploy", ""]
    lines.append(f"- ok: `{str(payload['ok']).lower()}`")
    lines.append(f"- project_root: `{payload['projectRoot']}`")
    lines.append(f"- deploy_mode: `{payload['deployMode']}`")
    lines.append("")
    for step in payload["steps"]:
        status = "ok" if step["ok"] else "failed"
        lines.append(f"- {' '.join(step['command'])}: `{status}`")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    payload = run_local_deploy(args.project_root)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(payload), end="")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
