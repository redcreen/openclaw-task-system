#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from create_planning_acceptance_record import create_record


DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"


def build_artifacts_dir(record_date: str) -> Path:
    return DOCS_DIR / "artifacts" / f"planning_acceptance_{record_date}"


def build_record_path(record_date: str) -> Path:
    return DOCS_DIR / "archive" / f"planning_acceptance_record_{record_date}.md"


def prepare_acceptance(*, record_date: str, force: bool = False) -> dict[str, object]:
    reused_existing_record = False
    try:
        record_path = create_record(record_date=record_date, force=force)
    except FileExistsError:
        record_path = build_record_path(record_date)
        reused_existing_record = True
    artifacts_dir = build_artifacts_dir(record_date)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    return {
        "ok": True,
        "record_date": record_date,
        "record_path": str(record_path),
        "artifacts_dir": str(artifacts_dir),
        "reused_existing_record": reused_existing_record,
        "capture_targets": [
            str(artifacts_dir / "plugin_doctor.txt"),
            str(artifacts_dir / "plugin_smoke.json"),
            str(artifacts_dir / "planning_acceptance.json"),
            str(artifacts_dir / "stable_acceptance.json"),
            str(artifacts_dir / "planning_ops.json"),
            str(artifacts_dir / "continuity_ops.json"),
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a dated planning acceptance workspace.")
    parser.add_argument("--date", dest="record_date", default=date.today().isoformat())
    parser.add_argument("--force", action="store_true", help="Overwrite the record file if it already exists.")
    parser.add_argument("--json", action="store_true", help="Print structured JSON output.")
    args = parser.parse_args()

    payload = prepare_acceptance(record_date=args.record_date, force=args.force)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(payload["record_path"])
        print(payload["artifacts_dir"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
