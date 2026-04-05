#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path


PLUGIN_ID = "openclaw-task-system"
DEFAULT_OPENCLAW_CONFIG = Path.home() / ".openclaw" / "openclaw.json"


@dataclass(frozen=True)
class ConfigureResult:
    config_path: Path
    changed: bool
    plugin_enabled: bool
    allow_contains_plugin: bool


def build_minimal_plugin_entry(
    *,
    python_bin: str = "python3",
    default_agent_id: str = "main",
    task_message_prefix: str = "[wd] ",
) -> dict[str, object]:
    return {
        "enabled": True,
        "config": {
            "enabled": True,
            "pythonBin": python_bin,
            "defaultAgentId": default_agent_id,
            "taskMessagePrefix": task_message_prefix,
        },
    }


def _ensure_dict(parent: dict[str, object], key: str) -> dict[str, object]:
    value = parent.get(key)
    if not isinstance(value, dict):
        value = {}
        parent[key] = value
    return value


def _ensure_list(parent: dict[str, object], key: str) -> list[object]:
    value = parent.get(key)
    if not isinstance(value, list):
        value = []
        parent[key] = value
    return value


def load_config(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected object at top level in {path}")
    return payload


def apply_minimal_plugin_config(
    data: dict[str, object],
    *,
    python_bin: str = "python3",
    default_agent_id: str = "main",
    task_message_prefix: str = "[wd] ",
) -> tuple[dict[str, object], bool]:
    changed = False

    plugins = _ensure_dict(data, "plugins")
    allow = _ensure_list(plugins, "allow")
    if PLUGIN_ID not in allow:
        allow.append(PLUGIN_ID)
        changed = True

    entries = _ensure_dict(plugins, "entries")
    desired_entry = build_minimal_plugin_entry(
        python_bin=python_bin,
        default_agent_id=default_agent_id,
        task_message_prefix=task_message_prefix,
    )
    current_entry = entries.get(PLUGIN_ID)
    if current_entry != desired_entry:
        entries[PLUGIN_ID] = desired_entry
        changed = True

    return data, changed


def configure_openclaw_plugin(
    *,
    path: Path = DEFAULT_OPENCLAW_CONFIG,
    write: bool = False,
    python_bin: str = "python3",
    default_agent_id: str = "main",
    task_message_prefix: str = "[wd] ",
) -> ConfigureResult:
    data = load_config(path)
    updated, changed = apply_minimal_plugin_config(
        data,
        python_bin=python_bin,
        default_agent_id=default_agent_id,
        task_message_prefix=task_message_prefix,
    )
    if write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(updated, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    plugins = updated.get("plugins", {})
    allow = plugins.get("allow", []) if isinstance(plugins, dict) else []
    entries = plugins.get("entries", {}) if isinstance(plugins, dict) else {}
    plugin_entry = entries.get(PLUGIN_ID, {}) if isinstance(entries, dict) else {}

    return ConfigureResult(
        config_path=path,
        changed=changed,
        plugin_enabled=bool(isinstance(plugin_entry, dict) and plugin_entry.get("enabled") is True),
        allow_contains_plugin=PLUGIN_ID in allow if isinstance(allow, list) else False,
    )


def render_json(result: ConfigureResult) -> str:
    payload = {
        "configPath": str(result.config_path),
        "changed": result.changed,
        "pluginEnabled": result.plugin_enabled,
        "allowContainsPlugin": result.allow_contains_plugin,
        "pluginId": PLUGIN_ID,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def render_markdown(result: ConfigureResult, *, write: bool) -> str:
    action = "updated" if write else "previewed"
    lines = [
        "# OpenClaw Plugin Config",
        "",
        f"- config_path: `{result.config_path}`",
        f"- action: `{action}`",
        f"- changed: `{str(result.changed).lower()}`",
        f"- plugin_enabled: `{str(result.plugin_enabled).lower()}`",
        f"- allow_contains_plugin: `{str(result.allow_contains_plugin).lower()}`",
        "",
    ]
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write a minimal OpenClaw plugin entry for openclaw-task-system.")
    parser.add_argument("--path", type=Path, default=DEFAULT_OPENCLAW_CONFIG)
    parser.add_argument("--python-bin", default="python3")
    parser.add_argument("--default-agent-id", default="main")
    parser.add_argument("--task-message-prefix", default="[wd] ")
    parser.add_argument("--write", action="store_true", help="Write changes back to openclaw.json")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = configure_openclaw_plugin(
        path=args.path,
        write=args.write,
        python_bin=args.python_bin,
        default_agent_id=args.default_agent_id,
        task_message_prefix=args.task_message_prefix,
    )
    if args.json:
        print(render_json(result))
    else:
        print(render_markdown(result, write=args.write), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
