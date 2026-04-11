#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

from prepare_planning_acceptance import prepare_acceptance


RUNTIME_DIR = Path(__file__).resolve().parent
MANIFEST_NAME = "capture_manifest.json"


@dataclass(frozen=True)
class CaptureCommand:
    label: str
    output_name: str
    command: list[str]


def build_capture_commands() -> list[CaptureCommand]:
    python = sys.executable or "python3"
    return [
        CaptureCommand("plugin-doctor", "plugin_doctor.txt", [python, str(RUNTIME_DIR / "plugin_doctor.py")]),
        CaptureCommand("plugin-smoke", "plugin_smoke.json", [python, str(RUNTIME_DIR / "plugin_smoke.py"), "--json"]),
        CaptureCommand(
            "planning-acceptance",
            "planning_acceptance.json",
            [python, str(RUNTIME_DIR / "planning_acceptance.py"), "--json"],
        ),
        CaptureCommand(
            "stable-acceptance",
            "stable_acceptance.json",
            [python, str(RUNTIME_DIR / "stable_acceptance.py"), "--json"],
        ),
        CaptureCommand("planning-ops", "planning_ops.json", [python, str(RUNTIME_DIR / "main_ops.py"), "planning", "--json"]),
        CaptureCommand(
            "continuity-ops",
            "continuity_ops.json",
            [python, str(RUNTIME_DIR / "main_ops.py"), "continuity", "--json"],
        ),
    ]


def run_capture_command(artifacts_dir: Path, command: CaptureCommand) -> dict[str, object]:
    completed = subprocess.run(command.command, capture_output=True, text=True, check=False)
    output_path = artifacts_dir / command.output_name
    content = completed.stdout if completed.stdout else completed.stderr
    output_path.write_text(content, encoding="utf-8")
    return {
        "label": command.label,
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "output_path": str(output_path),
        "command": command.command,
    }


def write_capture_manifest(artifacts_dir: Path, payload: dict[str, object]) -> str:
    manifest_path = artifacts_dir / MANIFEST_NAME
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(manifest_path)


def capture_artifacts(*, record_date: str, force: bool = False, labels: Iterable[str] | None = None) -> dict[str, object]:
    prepared = prepare_acceptance(record_date=record_date, force=force)
    artifacts_dir = Path(str(prepared["artifacts_dir"]))
    requested = set(labels or [])
    results = []
    for command in build_capture_commands():
        if requested and command.label not in requested:
            continue
        results.append(run_capture_command(artifacts_dir, command))
    payload = {
        "ok": all(bool(item["ok"]) for item in results),
        "record_date": record_date,
        "record_path": prepared["record_path"],
        "artifacts_dir": str(artifacts_dir),
        "results": results,
    }
    payload["manifest_path"] = write_capture_manifest(artifacts_dir, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture planning acceptance command outputs into an artifacts directory.")
    parser.add_argument("--date", dest="record_date", default=date.today().isoformat())
    parser.add_argument("--force", action="store_true", help="Overwrite the record file if it already exists.")
    parser.add_argument("--json", action="store_true", help="Print structured JSON output.")
    parser.add_argument("--label", action="append", dest="labels", help="Capture only the named label. May repeat.")
    args = parser.parse_args()

    payload = capture_artifacts(record_date=args.record_date, force=args.force, labels=args.labels)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for result in payload["results"]:
            print(f"{result['label']}: {result['output_path']}")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
