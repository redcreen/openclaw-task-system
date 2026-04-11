#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


SOURCE_RUNTIME_DIR = Path(__file__).resolve().parents[2] / "plugin" / "scripts" / "runtime"
INSTALLED_RUNTIME_DIR = Path.home() / ".openclaw" / "extensions" / "openclaw-task-system" / "scripts" / "runtime"


def collect_file_names(path: Path) -> list[str]:
    if not path.exists():
        return []
    return sorted(item.name for item in path.iterdir() if item.is_file())


def build_install_drift_report() -> dict[str, object]:
    source_files = collect_file_names(SOURCE_RUNTIME_DIR)
    installed_files = collect_file_names(INSTALLED_RUNTIME_DIR)
    missing_in_installed = [name for name in source_files if name not in installed_files]
    extra_in_installed = [name for name in installed_files if name not in source_files]
    installed_exists = INSTALLED_RUNTIME_DIR.exists()
    return {
        "ok": installed_exists and not missing_in_installed and not extra_in_installed,
        "source_runtime_dir": str(SOURCE_RUNTIME_DIR),
        "installed_runtime_dir": str(INSTALLED_RUNTIME_DIR),
        "installed_runtime_exists": installed_exists,
        "source_file_count": len(source_files),
        "installed_file_count": len(installed_files),
        "missing_in_installed": missing_in_installed,
        "extra_in_installed": extra_in_installed,
    }


def render_markdown(payload: dict[str, object]) -> str:
    lines = [
        "# Plugin Install Drift",
        "",
        f"- ok: {payload.get('ok')}",
        f"- installed_runtime_exists: {payload.get('installed_runtime_exists')}",
        f"- source_runtime_dir: {payload.get('source_runtime_dir')}",
        f"- installed_runtime_dir: {payload.get('installed_runtime_dir')}",
        f"- source_file_count: {payload.get('source_file_count')}",
        f"- installed_file_count: {payload.get('installed_file_count')}",
        f"- missing_in_installed: {', '.join(payload.get('missing_in_installed', [])) or 'none'}",
        f"- extra_in_installed: {', '.join(payload.get('extra_in_installed', [])) or 'none'}",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    import sys

    payload = build_install_drift_report()
    if sys.argv[1:] and sys.argv[1] == "--json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(payload), end="")
