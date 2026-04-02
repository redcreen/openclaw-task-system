#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from task_config import load_task_system_config
from task_state import TaskPaths, atomic_write_json, default_paths

EXECUTION_RESULT_SCHEMA = "openclaw.task-system.dispatch-result.v1"
SUPPORTED_MESSAGE_CHANNELS = {
    "telegram",
    "discord",
    "slack",
    "signal",
    "whatsapp",
    "imessage",
    "line",
    "irc",
    "googlechat",
}


@dataclass(frozen=True)
class DispatchDecision:
    action: str
    reason: str
    command: list[str]


def instruction_dir(paths: TaskPaths) -> Path:
    return paths.data_dir / "send-instructions"


def result_dir(paths: TaskPaths) -> Path:
    return paths.data_dir / "dispatch-results"


def processed_dir(paths: TaskPaths) -> Path:
    return paths.data_dir / "processed-instructions"


def failed_dir(paths: TaskPaths) -> Path:
    return paths.data_dir / "failed-instructions"


def ensure_dirs(paths: TaskPaths) -> None:
    result_dir(paths).mkdir(parents=True, exist_ok=True)
    processed_dir(paths).mkdir(parents=True, exist_ok=True)
    failed_dir(paths).mkdir(parents=True, exist_ok=True)


def load_instruction(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_dispatch_decision(
    instruction: dict[str, Any],
    *,
    openclaw_bin: str = "/Users/redcreen/.local/bin/openclaw",
) -> DispatchDecision:
    channel = str(instruction.get("channel") or "").strip()
    chat_id = str(instruction.get("chat_id") or "").strip()
    message = str(instruction.get("message") or "").strip()
    account_id = str(instruction.get("account_id") or "").strip()

    if not message:
        return DispatchDecision(action="skip", reason="empty-message", command=[])
    if channel == "agent":
        return DispatchDecision(action="skip", reason="internal-agent-channel", command=[])
    if channel not in SUPPORTED_MESSAGE_CHANNELS:
        return DispatchDecision(action="skip", reason=f"unsupported-channel:{channel or 'unknown'}", command=[])
    if not chat_id:
        return DispatchDecision(action="skip", reason="missing-chat-id", command=[])

    command = [
        openclaw_bin,
        "message",
        "send",
        "--channel",
        channel,
    ]
    if account_id:
        command.extend(["--account", account_id])
    command.extend(["--target", chat_id, "--message", message])
    return DispatchDecision(action="send", reason="supported", command=command)


def write_dispatch_result(
    instruction: dict[str, Any],
    decision: DispatchDecision,
    *,
    name: str,
    paths: TaskPaths,
    executed: bool,
    execution_context: str,
    exit_code: Optional[int] = None,
    stdout: Optional[str] = None,
    stderr: Optional[str] = None,
) -> Path:
    ensure_dirs(paths)
    payload = {
        "schema": EXECUTION_RESULT_SCHEMA,
        "task_id": instruction.get("task_id"),
        "agent_id": instruction.get("agent_id"),
        "session_key": instruction.get("session_key"),
        "channel": instruction.get("channel"),
        "account_id": instruction.get("account_id"),
        "chat_id": instruction.get("chat_id"),
        "message": instruction.get("message"),
        "action": decision.action,
        "reason": decision.reason,
        "execution_context": execution_context,
        "command": decision.command,
        "executed": executed,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
    }
    out = result_dir(paths) / name
    atomic_write_json(out, payload)
    return out


def archive_instruction(
    source: Path,
    *,
    name: str,
    paths: TaskPaths,
    succeeded: bool,
) -> Path:
    ensure_dirs(paths)
    target_dir = processed_dir(paths) if succeeded else failed_dir(paths)
    target = target_dir / name
    source.replace(target)
    return target


def execute_instruction(
    instruction: dict[str, Any],
    *,
    name: str,
    source_path: Optional[Path],
    paths: TaskPaths,
    execute: bool = False,
    openclaw_bin: str = "/Users/redcreen/.local/bin/openclaw",
    max_retries: int = 2,
    retry_delay_seconds: float = 1.0,
    execution_context: str = "local",
) -> dict[str, Any]:
    import time

    decision = build_dispatch_decision(instruction, openclaw_bin=openclaw_bin)
    if not execute or decision.action != "send":
        result_execution_context = "dry-run" if not execute else execution_context
        result_path = write_dispatch_result(
            instruction,
            decision,
            name=name,
            paths=paths,
            executed=False,
            execution_context=result_execution_context,
        )
        return {
            "decision": decision.__dict__,
            "result_path": str(result_path),
            "execution_context": result_execution_context,
        }

    archived_instruction_path: Optional[str] = None
    last_exit_code = -1
    last_stdout = ""
    last_stderr = ""
    attempt = 0

    while attempt <= max_retries:
        if attempt > 0:
            time.sleep(retry_delay_seconds * attempt)  # Exponential backoff

        completed = subprocess.run(decision.command, capture_output=True, text=True, check=False)
        last_exit_code = completed.returncode
        last_stdout = completed.stdout
        last_stderr = completed.stderr

        # Success case
        if completed.returncode == 0:
            break

        # Check if it's a retryable network error
        stderr_lower = completed.stderr.lower()
        is_network_error = any(
            err in stderr_lower
            for err in ["network request", "timeout", "connection", "econnreset", "etimedout"]
        )

        if not is_network_error:
            break  # Non-retryable error, exit loop

        attempt += 1
        if attempt <= max_retries:
            last_stderr = f"[Retry {attempt}/{max_retries}] {last_stderr}"

    result_path = write_dispatch_result(
        instruction,
        decision,
        name=name,
        paths=paths,
        executed=True,
        execution_context=execution_context,
        exit_code=last_exit_code,
        stdout=last_stdout,
        stderr=last_stderr,
    )
    if source_path is not None:
        archived_path = archive_instruction(
            source_path,
            name=name,
            paths=paths,
            succeeded=(decision.action == "skip" or last_exit_code == 0),
        )
        archived_instruction_path = str(archived_path)
    return {
        "decision": decision.__dict__,
        "result_path": str(result_path),
        "exit_code": last_exit_code,
        "archived_instruction_path": archived_instruction_path,
        "retries": attempt,
        "execution_context": execution_context,
    }


def execute_all(
    *,
    paths: Optional[TaskPaths] = None,
    execute: bool = False,
    openclaw_bin: str = "/Users/redcreen/.local/bin/openclaw",
    retry_failed: bool = False,
    execution_context: str = "local",
) -> list[dict[str, Any]]:
    resolved_paths = paths or default_paths()
    ensure_dirs(resolved_paths)
    results: list[dict[str, Any]] = []

    # Process new instructions
    for path in sorted(instruction_dir(resolved_paths).glob("*.json")):
        instruction = load_instruction(path)
        result = execute_instruction(
            instruction,
            name=path.name,
            source_path=path,
            paths=resolved_paths,
            execute=execute,
            openclaw_bin=openclaw_bin,
            execution_context=execution_context,
        )
        results.append(result)

    # Retry failed instructions (only when execute=True and retry_failed=True)
    if execute and retry_failed:
        failed_results = retry_failed_instructions(
            paths=resolved_paths,
            openclaw_bin=openclaw_bin,
            execution_context=execution_context,
        )
        results.extend(failed_results)

    return results


def retry_failed_instructions(
    *,
    paths: TaskPaths,
    openclaw_bin: str = "/Users/redcreen/.local/bin/openclaw",
    max_age_hours: int = 24,
    execution_context: str = "local",
) -> list[dict[str, Any]]:
    """Retry failed instructions that are younger than max_age_hours."""
    import time

    results: list[dict[str, Any]] = []
    failed_dir_path = failed_dir(paths)

    if not failed_dir_path.exists():
        return results

    now = time.time()
    max_age_seconds = max_age_hours * 3600

    for path in sorted(failed_dir_path.glob("*.json")):
        # Check if file is too old
        stat = path.stat()
        if now - stat.st_mtime > max_age_seconds:
            continue

        # Move back to instruction dir for retry
        instruction = load_instruction(path)
        target_path = instruction_dir(paths) / path.name

        try:
            path.replace(target_path)
            result = execute_instruction(
                instruction,
                name=path.name,
                source_path=target_path,
                paths=paths,
                execute=True,
                openclaw_bin=openclaw_bin,
                execution_context=execution_context,
            )
            result["retry_from_failed"] = True
            results.append(result)
        except Exception as e:
            # If move fails, log but don't crash
            results.append({
                "error": str(e),
                "name": path.name,
                "retry_from_failed": True,
            })

    return results


if __name__ == "__main__":
    parser = ArgumentParser(description="Execute or dry-run send instructions.")
    parser.add_argument("--execute", action="store_true", help="Run real openclaw message send commands.")
    parser.add_argument("--config", help="Task system config path.")
    parser.add_argument("--openclaw-bin", help="Override openclaw binary path.")
    parser.add_argument(
        "--execution-context",
        help="Label written into dispatch-results, e.g. dry-run/local/host.",
    )
    args = parser.parse_args()

    config = load_task_system_config(config_path=Path(args.config).expanduser() if args.config else None)
    execution_context = args.execution_context or os.environ.get("OPENCLAW_TASK_SYSTEM_EXECUTION_CONTEXT") or "local"
    print(
        json.dumps(
            execute_all(
                paths=config.build_paths(),
                execute=args.execute,
                openclaw_bin=args.openclaw_bin or config.delivery.openclaw_bin,
                execution_context=execution_context,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
