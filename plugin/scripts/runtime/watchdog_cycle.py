#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from consume_outbox import consume_once
from delivery_dispatch import dispatch_all
from instruction_executor import execute_all
from prepare_delivery import prepare_all
from silence_monitor import process_overdue_tasks
from task_config import load_task_system_config


def run_watchdog_cycle(
    *,
    config_path: Optional[Path] = None,
    execute_instructions: Optional[bool] = None,
    retry_failed: Optional[bool] = None,
    execution_context: Optional[str] = None,
) -> dict[str, Any]:
    runtime_config = load_task_system_config(config_path=config_path)
    paths = runtime_config.build_paths()
    findings = process_overdue_tasks(paths=paths, config=runtime_config, config_path=config_path)
    sent = consume_once(paths=paths)
    delivery_ready = prepare_all(paths=paths)
    instructions = dispatch_all(paths=paths)
    should_execute = (
        runtime_config.delivery.auto_execute_instructions
        if execute_instructions is None
        else execute_instructions
    )
    should_retry_failed = (
        runtime_config.delivery.retry_failed_instructions
        if retry_failed is None
        else retry_failed
    )
    resolved_execution_context = execution_context or runtime_config.delivery.execution_context
    execution_results = execute_all(
        paths=paths,
        execute=should_execute,
        openclaw_bin=runtime_config.delivery.openclaw_bin,
        retry_failed=should_retry_failed,
        execution_context=resolved_execution_context,
    )
    return {
        "findings": findings,
        "sent": sent,
        "delivery_ready": delivery_ready,
        "send_instructions": instructions,
        "execution_results": execution_results,
        "execute_instructions": should_execute,
        "retry_failed": should_retry_failed,
        "execution_context": resolved_execution_context,
    }


if __name__ == "__main__":
    import sys

    from argparse import ArgumentParser

    parser = ArgumentParser(description="Run one watchdog scan + delivery cycle.")
    parser.add_argument("config", nargs="?", help="Task system config path.")
    parser.add_argument(
        "--no-execute",
        action="store_true",
        help="Build delivery artifacts but skip real send-instruction execution.",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Retry recent failed instructions in addition to pending ones.",
    )
    parser.add_argument(
        "--execution-context",
        help="Label written into dispatch-results, e.g. dry-run/local/host.",
    )
    parsed = parser.parse_args()

    config_path = Path(parsed.config).expanduser().resolve() if parsed.config else None
    print(
        json.dumps(
            run_watchdog_cycle(
                config_path=config_path,
                execute_instructions=not parsed.no_execute,
                retry_failed=parsed.retry_failed,
                execution_context=parsed.execution_context,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
