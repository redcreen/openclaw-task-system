#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from health_report import build_health_report
from instruction_executor import retry_failed_instructions
from main_acceptance import run_main_acceptance
from plugin_doctor import run_checks
from plugin_smoke import run_plugin_smoke
from task_state import TaskPaths


@dataclass(frozen=True)
class StableAcceptanceStep:
    step: str
    ok: bool
    detail: str


def _write_config(path: Path, data_dir: Path) -> None:
    path.write_text(
        json.dumps({"taskSystem": {"storageDir": str(data_dir)}}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _set_env(config_path: Path) -> str | None:
    previous = os.environ.get("OPENCLAW_TASK_SYSTEM_CONFIG")
    os.environ["OPENCLAW_TASK_SYSTEM_CONFIG"] = str(config_path)
    return previous


def _restore_env(previous: str | None) -> None:
    if previous is None:
        os.environ.pop("OPENCLAW_TASK_SYSTEM_CONFIG", None)
    else:
        os.environ["OPENCLAW_TASK_SYSTEM_CONFIG"] = previous


def run_stable_acceptance() -> dict[str, Any]:
    temp_dir = Path(tempfile.mkdtemp(prefix="task-system-stable-acceptance."))
    data_dir = temp_dir / "data"
    config_path = temp_dir / "task_system.json"
    _write_config(config_path, data_dir)
    previous_env = _set_env(config_path)
    steps: list[StableAcceptanceStep] = []

    try:
        plugin_checks = run_checks()
        steps.append(
            StableAcceptanceStep(
                step="plugin-doctor-checks",
                ok=all(check.ok for check in plugin_checks),
                detail=json.dumps([asdict(check) for check in plugin_checks], ensure_ascii=False),
            )
        )

        plugin_payload = run_plugin_smoke()
        steps.append(
            StableAcceptanceStep(
                step="plugin-smoke",
                ok=bool(plugin_payload.get("ok")),
                detail=json.dumps(plugin_payload, ensure_ascii=False),
            )
        )

        main_payload = run_main_acceptance()
        steps.append(
            StableAcceptanceStep(
                step="main-acceptance",
                ok=bool(main_payload.get("ok")),
                detail=json.dumps(main_payload, ensure_ascii=False),
            )
        )

        paths = TaskPaths.from_root(temp_dir)
        failed_dir = paths.data_dir / "failed-instructions"
        failed_dir.mkdir(parents=True, exist_ok=True)
        failed_path = failed_dir / "task_retryable.json"
        failed_path.write_text(
            json.dumps(
                {
                    "task_id": "task_retryable",
                    "agent_id": "main",
                    "session_key": "session:stable:retry",
                    "channel": "telegram",
                    "chat_id": "chat:test",
                    "message": "retry acceptance",
                    "_retry_count": 0,
                    "_last_failure_retryable": True,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        mock_bin = temp_dir / "mock-openclaw"
        mock_bin.write_text("#!/bin/sh\nprintf 'sent\\n'\nexit 0\n", encoding="utf-8")
        os.chmod(mock_bin, 0o755)
        retry_results = retry_failed_instructions(paths=paths, openclaw_bin=str(mock_bin), execution_context="host")
        retry_ok = bool(retry_results) and retry_results[0].get("exit_code") == 0
        steps.append(
            StableAcceptanceStep(
                step="retry-failed-instructions",
                ok=retry_ok,
                detail=json.dumps(retry_results, ensure_ascii=False),
            )
        )

        health_payload = build_health_report(config_path=config_path)
        steps.append(
            StableAcceptanceStep(
                step="health-report-clean",
                ok=health_payload.get("status") == "ok",
                detail=json.dumps(health_payload, ensure_ascii=False),
            )
        )

        return {
            "ok": all(step.ok for step in steps),
            "steps": [asdict(step) for step in steps],
            "tempDir": str(temp_dir),
            "configPath": str(config_path),
            "dataDir": str(data_dir),
        }
    finally:
        _restore_env(previous_env)
        shutil.rmtree(temp_dir, ignore_errors=True)


def render_markdown(payload: dict[str, Any]) -> str:
    lines = ["# Stable Acceptance", ""]
    lines.append(f"- ok: {payload['ok']}")
    for step in payload["steps"]:
        status = "ok" if step["ok"] else "failed"
        lines.append(f"- {step['step']}: {status}")
        lines.append(f"  detail: {step['detail']}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    payload = run_stable_acceptance()
    if args and args[0] == "--json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(payload), end="")
