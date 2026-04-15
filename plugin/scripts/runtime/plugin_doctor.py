#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from plugin_install_drift import build_install_drift_report
from runtime_mirror import build_runtime_mirror_report

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = PROJECT_ROOT / "plugin"
HOOKS_SCRIPT = PLUGIN_ROOT / "scripts" / "runtime" / "openclaw_hooks.py"
DEFAULT_CONFIG = PLUGIN_ROOT / "config" / "task_system.json"
EXAMPLE_CONFIG = PLUGIN_ROOT / "config" / "task_system.example.json"


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def choose_config_path() -> Path:
    if DEFAULT_CONFIG.exists():
        return DEFAULT_CONFIG
    return EXAMPLE_CONFIG


def resolve_plugin_entry_target() -> Path | None:
    entry_path = PLUGIN_ROOT / "index.ts"
    if not entry_path.exists():
        return None
    content = entry_path.read_text(encoding="utf-8")
    marker = 'export { default } from "'
    start = content.find(marker)
    if start < 0:
        return None
    start += len(marker)
    end = content.find('"', start)
    if end < 0:
        return None
    relative_target = content[start:end]
    return (PLUGIN_ROOT / relative_target).resolve()


def run_checks() -> list[CheckResult]:
    config_path = choose_config_path()
    plugin_entry_target = resolve_plugin_entry_target()
    runtime_mirror = build_runtime_mirror_report()
    install_drift = build_install_drift_report()
    checks = [
        CheckResult("project_root", PROJECT_ROOT.exists(), str(PROJECT_ROOT)),
        CheckResult("plugin_root", PLUGIN_ROOT.exists(), str(PLUGIN_ROOT)),
        CheckResult("plugin_manifest", (PLUGIN_ROOT / "openclaw.plugin.json").exists(), str(PLUGIN_ROOT / "openclaw.plugin.json")),
        CheckResult("plugin_entry", (PLUGIN_ROOT / "index.ts").exists(), str(PLUGIN_ROOT / "index.ts")),
        CheckResult(
            "plugin_entry_target",
            plugin_entry_target.exists() if plugin_entry_target is not None else False,
            str(plugin_entry_target or (PLUGIN_ROOT / "<unresolved-entry-target>")),
        ),
        CheckResult("plugin_runtime_entry", (PLUGIN_ROOT / "src" / "plugin" / "index.ts").exists(), str(PLUGIN_ROOT / "src" / "plugin" / "index.ts")),
        CheckResult("hooks_script", HOOKS_SCRIPT.exists(), str(HOOKS_SCRIPT)),
        CheckResult("config_path", config_path.exists(), str(config_path)),
        CheckResult(
            "repo_runtime_mirror_sync",
            bool(runtime_mirror["ok"]),
            json.dumps(
                {
                    "canonical_runtime_dir": runtime_mirror["canonical_runtime_dir"],
                    "mirror_runtime_dir": runtime_mirror["mirror_runtime_dir"],
                    "missing_in_mirror": runtime_mirror["missing_in_mirror"],
                    "extra_in_mirror": runtime_mirror["extra_in_mirror"],
                    "changed_files": runtime_mirror["changed_files"],
                },
                ensure_ascii=False,
            ),
        ),
        CheckResult(
            "installed_runtime_sync",
            bool(install_drift["ok"]),
            json.dumps(
                {
                    "installed_runtime_dir": install_drift["installed_runtime_dir"],
                    "missing_in_installed": install_drift["missing_in_installed"],
                    "extra_in_installed": install_drift["extra_in_installed"],
                },
                ensure_ascii=False,
            ),
        ),
    ]
    return checks


def detect_python_bin() -> str:
    for candidate in (
        shutil.which("python3"),
        shutil.which("python"),
        sys.executable,
    ):
        if candidate:
            return str(Path(candidate).resolve())
    return "python3"


def build_openclaw_plugin_entry() -> dict[str, object]:
    return {
        "enabled": True,
        "pythonBin": detect_python_bin(),
        "defaultAgentId": "main",
        "taskMessagePrefix": "[wd] ",
        "hostDeliveryPollMs": 10000,
        "warmOutboundAdaptersOnStart": False,
        "continuationPollMs": 10000,
        "watchdogRecoveryPollMs": 60000,
        "watchdogMaxResumesPerCycle": 1,
        "debugLogMaxBytes": 8388608,
        "debugLogMaxFiles": 4,
        "debugVerbosePolling": False,
    }


def build_openclaw_config_snippet() -> dict[str, object]:
    return {
        "plugins": {
            "entries": {
                "openclaw-task-system": {
                    "enabled": True,
                    "config": build_openclaw_plugin_entry(),
                }
            }
        }
    }


def render_markdown() -> str:
    checks = run_checks()
    lines = ["# Plugin Doctor", ""]
    for check in checks:
        status = "ok" if check.ok else "missing"
        lines.append(f"- {check.name}: {status} ({check.detail})")
    lines.extend(
        [
            "",
            "## Canonical Runtime Source",
            "",
            "- editable source: `scripts/runtime/`",
            "- installable mirror: `plugin/scripts/runtime/`",
            "- sync command: `python3 scripts/runtime/runtime_mirror.py --write`",
            "",
            "## Suggested Install Command",
            "",
            "`openclaw plugins install ./plugin`",
            "",
            "## Suggested OpenClaw Config Snippet",
            "",
            "```json",
            json.dumps(build_openclaw_config_snippet(), ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def render_json() -> str:
    payload = {
        "checks": [asdict(check) for check in run_checks()],
        "installCommand": "openclaw plugins install ./plugin",
        "canonicalRuntimeSource": "scripts/runtime/",
        "runtimeMirrorDir": "plugin/scripts/runtime/",
        "runtimeMirrorSyncCommand": "python3 scripts/runtime/runtime_mirror.py --write",
        "openclawConfigSnippet": build_openclaw_config_snippet(),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] in {"--help", "-h"}:
        print("usage: plugin_doctor.py [--json]")
        raise SystemExit(0)
    if args and args[0] == "--json":
        print(render_json())
    else:
        print(render_markdown(), end="")
