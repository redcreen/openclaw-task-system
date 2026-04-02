#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = PROJECT_ROOT / "plugin"
HOOKS_SCRIPT = PROJECT_ROOT / "scripts" / "runtime" / "openclaw_hooks.py"
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "task_system.json"
EXAMPLE_CONFIG = PROJECT_ROOT / "config" / "task_system.example.json"


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def choose_config_path() -> Path:
    if DEFAULT_CONFIG.exists():
        return DEFAULT_CONFIG
    return EXAMPLE_CONFIG


def run_checks() -> list[CheckResult]:
    config_path = choose_config_path()
    checks = [
        CheckResult("project_root", PROJECT_ROOT.exists(), str(PROJECT_ROOT)),
        CheckResult("plugin_root", PLUGIN_ROOT.exists(), str(PLUGIN_ROOT)),
        CheckResult("plugin_manifest", (PLUGIN_ROOT / "openclaw.plugin.json").exists(), str(PLUGIN_ROOT / "openclaw.plugin.json")),
        CheckResult("plugin_entry", (PLUGIN_ROOT / "index.ts").exists(), str(PLUGIN_ROOT / "index.ts")),
        CheckResult("plugin_runtime_entry", (PLUGIN_ROOT / "src" / "plugin" / "index.ts").exists(), str(PLUGIN_ROOT / "src" / "plugin" / "index.ts")),
        CheckResult("hooks_script", HOOKS_SCRIPT.exists(), str(HOOKS_SCRIPT)),
        CheckResult("config_path", config_path.exists(), str(config_path)),
    ]
    return checks


def build_openclaw_plugin_entry() -> dict[str, object]:
    return {
        "enabled": True,
        "pythonBin": "python3",
        "runtimeRoot": str(PROJECT_ROOT),
        "configPath": str(choose_config_path()),
        "debugLogPath": str(PROJECT_ROOT / "data" / "plugin-debug.log"),
        "defaultAgentId": "main",
        "registerOnBeforeDispatch": True,
        "syncProgressOnMessageSending": True,
        "finalizeOnAgentEnd": True,
        "minProgressMessageLength": 20,
        "ignoreProgressPatterns": [
            "^收到$",
            "^好的$",
            "^继续$",
            "^处理中$",
            "^稍等$",
            "^thinking\\.\\.\\.$",
            "^\\.\\.\\.$",
        ],
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
            "## Suggested Install Command",
            "",
            f"`openclaw plugins install --link {PLUGIN_ROOT}`",
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
        "installCommand": f"openclaw plugins install --link {PLUGIN_ROOT}",
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
