#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from openclaw_hooks import finalize_active_from_payload, progress_active_from_payload, register_from_payload
from task_config import load_task_system_config
from task_state import TaskStore
from watchdog_cycle import run_watchdog_cycle


@dataclass(frozen=True)
class AcceptanceStep:
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


def run_main_acceptance() -> dict[str, Any]:
    temp_dir = Path(tempfile.mkdtemp(prefix="task-system-main-acceptance."))
    data_dir = temp_dir / "data"
    config_path = temp_dir / "task_system.json"
    _write_config(config_path, data_dir)
    previous_env = _set_env(config_path)

    steps: list[AcceptanceStep] = []
    try:
        register_result = register_from_payload(
            {
                "agent_id": "main",
                "session_key": "feishu:main:acceptance:test",
                "channel": "feishu",
                "chat_id": "chat:acceptance",
                "user_id": "ou_acceptance",
                "user_request": "帮我排查这个问题、修复并验证结果，再同步阶段进展",
                "estimated_steps": 5,
                "needs_verification": True,
            },
            config_path=config_path,
        )
        task_id = register_result.get("task_id")
        steps.append(
            AcceptanceStep(
                step="register-main-task",
                ok=bool(register_result.get("should_register_task")) and task_id is not None,
                detail=json.dumps(register_result, ensure_ascii=False),
            )
        )

        progress_result = progress_active_from_payload(
            {
                "agent_id": "main",
                "session_key": "feishu:main:acceptance:test",
                "progress_note": "已完成关键文件检查，正在整理修复和验证方案。",
            },
            config_path=config_path,
        )
        steps.append(
            AcceptanceStep(
                step="sync-main-progress",
                ok=bool(progress_result.get("updated")),
                detail=json.dumps(progress_result, ensure_ascii=False),
            )
        )

        finalize_result = finalize_active_from_payload(
            {
                "agent_id": "main",
                "session_key": "feishu:main:acceptance:test",
                "success": True,
                "result_summary": "main 路径已完成修复并通过本地验证。",
            },
            config_path=config_path,
        )
        done_task = finalize_result.get("task", {})
        steps.append(
            AcceptanceStep(
                step="finalize-main-task",
                ok=bool(finalize_result.get("updated")) and done_task.get("status") == "done",
                detail=json.dumps(finalize_result, ensure_ascii=False),
            )
        )

        overdue_result = register_from_payload(
            {
                "agent_id": "main",
                "session_key": "feishu:main:watchdog:test",
                "channel": "feishu",
                "chat_id": "chat:watchdog",
                "user_id": "ou_watchdog",
                "user_request": "继续处理这个长任务并在完成后同步",
                "estimated_steps": 4,
            },
            config_path=config_path,
        )
        overdue_task_id = overdue_result.get("task_id")
        runtime_config = load_task_system_config(config_path=config_path)
        store = TaskStore(paths=runtime_config.build_paths())
        if overdue_task_id:
            overdue_task = store.load_task(str(overdue_task_id))
            overdue_task.last_user_visible_update_at = "2020-01-01T00:00:00+00:00"
            store.save_task(overdue_task)

        watchdog_result = run_watchdog_cycle(config_path=config_path)
        steps.append(
            AcceptanceStep(
                step="watchdog-fallback-cycle",
                ok=len(watchdog_result.get("findings", [])) == 1 and len(watchdog_result.get("send_instructions", [])) == 1,
                detail=json.dumps(watchdog_result, ensure_ascii=False),
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
    lines = ["# Main Acceptance", ""]
    lines.append(f"- ok: {payload['ok']}")
    for step in payload["steps"]:
        status = "ok" if step["ok"] else "failed"
        lines.append(f"- {step['step']}: {status}")
        lines.append(f"  detail: {step['detail']}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    payload = run_main_acceptance()
    if args and args[0] == "--json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(payload), end="")
