#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from typing import Iterable

from run_planning_acceptance_bundle import run_bundle


def run_suite(*, record_date: str, force: bool = False, labels: Iterable[str] | None = None) -> dict[str, object]:
    test_command = [sys.executable or "python3", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*planning_acceptance*.py", "-v"]
    tests_completed = subprocess.run(test_command, capture_output=True, text=True, check=False)
    bundle_payload = run_bundle(record_date=record_date, force=force, labels=labels)
    tests_output = tests_completed.stdout if tests_completed.stdout else tests_completed.stderr
    return {
        "ok": tests_completed.returncode == 0 and bool(bundle_payload.get("ok")),
        "record_date": record_date,
        "tests_ok": tests_completed.returncode == 0,
        "tests_returncode": tests_completed.returncode,
        "tests_output": tests_output,
        "tests_stdout": tests_completed.stdout,
        "tests_stderr": tests_completed.stderr,
        "bundle": bundle_payload,
    }


def render_markdown(payload: dict[str, object]) -> str:
    bundle = payload.get("bundle", {})
    lines = [
        "# Planning Acceptance Suite",
        "",
        f"- ok: {payload.get('ok')}",
        f"- tests_ok: {payload.get('tests_ok')}",
        f"- tests_returncode: {payload.get('tests_returncode')}",
        f"- bundle_ok: {bundle.get('ok')}",
        f"- record_path: {bundle.get('record_path')}",
        f"- artifacts_dir: {bundle.get('artifacts_dir')}",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run planning acceptance helper tests and the bundle in one command.")
    parser.add_argument("--date", dest="record_date", default=date.today().isoformat())
    parser.add_argument("--force", action="store_true", help="Overwrite the record file if it already exists.")
    parser.add_argument("--json", action="store_true", help="Print structured JSON output.")
    parser.add_argument("--label", action="append", dest="labels", help="Run only the named capture label. May repeat.")
    args = parser.parse_args()

    payload = run_suite(record_date=args.record_date, force=args.force, labels=args.labels)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(payload), end="")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
