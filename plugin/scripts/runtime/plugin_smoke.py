#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from openclaw_hooks import (
    finalize_active_from_payload,
    progress_active_from_payload,
    register_from_payload,
    resolve_active_task_from_payload,
)


@dataclass(frozen=True)
class SmokeStepResult:
    step: str
    ok: bool
    detail: str


def _write_config(path: Path, data_dir: Path) -> None:
    path.write_text(
        json.dumps({"taskSystem": {"storageDir": str(data_dir)}}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def run_plugin_smoke() -> dict[str, Any]:
    temp_dir = Path(tempfile.mkdtemp(prefix="task-system-plugin-smoke."))
    data_dir = temp_dir / "data"
    config_path = temp_dir / "task_system.json"
    _write_config(config_path, data_dir)

    previous_env = os.environ.get("OPENCLAW_TASK_SYSTEM_CONFIG")
    os.environ["OPENCLAW_TASK_SYSTEM_CONFIG"] = str(config_path)

    steps: list[SmokeStepResult] = []
    try:
        register_result = register_from_payload(
            {
                "agent_id": "main",
                "session_key": "feishu:smoke:chat:test",
                "channel": "feishu",
                "chat_id": "chat:smoke",
                "user_id": "ou_smoke",
                "user_request": "帮我排查这个长任务，并修复后验证结果",
                "estimated_steps": 4,
                "needs_verification": True,
            },
            config_path=config_path,
        )
        task_id = register_result.get("task_id")
        steps.append(
            SmokeStepResult(
                step="register",
                ok=bool(register_result.get("should_register_task")) and task_id is not None,
                detail=json.dumps(register_result, ensure_ascii=False),
            )
        )

        resolve_result = resolve_active_task_from_payload(
            {
                "agent_id": "main",
                "session_key": "feishu:smoke:chat:test",
            },
            config_path=config_path,
        )
        steps.append(
            SmokeStepResult(
                step="resolve-active",
                ok=bool(resolve_result.get("found")) and resolve_result.get("task_id") == task_id,
                detail=json.dumps(resolve_result, ensure_ascii=False),
            )
        )

        progress_result = progress_active_from_payload(
            {
                "agent_id": "main",
                "session_key": "feishu:smoke:chat:test",
                "progress_note": "已读取关键文件，正在验证修复路径和测试策略。",
            },
            config_path=config_path,
        )
        steps.append(
            SmokeStepResult(
                step="progress-active",
                ok=bool(progress_result.get("updated")),
                detail=json.dumps(progress_result, ensure_ascii=False),
            )
        )

        finalize_result = finalize_active_from_payload(
            {
                "agent_id": "main",
                "session_key": "feishu:smoke:chat:test",
                "success": True,
                "result_summary": "已完成修复并通过本地验证。",
            },
            config_path=config_path,
        )
        final_task = finalize_result.get("task", {})
        steps.append(
            SmokeStepResult(
                step="finalize-active",
                ok=bool(finalize_result.get("updated")) and final_task.get("status") == "done",
                detail=json.dumps(finalize_result, ensure_ascii=False),
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
        if previous_env is None:
            os.environ.pop("OPENCLAW_TASK_SYSTEM_CONFIG", None)
        else:
            os.environ["OPENCLAW_TASK_SYSTEM_CONFIG"] = previous_env
        shutil.rmtree(temp_dir, ignore_errors=True)


def render_markdown(payload: dict[str, Any]) -> str:
    lines = ["# Plugin Smoke", ""]
    lines.append(f"- ok: {payload['ok']}")
    for step in payload["steps"]:
        status = "ok" if step["ok"] else "failed"
        lines.append(f"- {step['step']}: {status}")
        lines.append(f"  detail: {step['detail']}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    payload = run_plugin_smoke()
    if args and args[0] == "--json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(payload), end="")
