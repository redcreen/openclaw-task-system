#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from datetime import date
from pathlib import Path

from create_planning_acceptance_record import create_record


DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"
DRY_RUN_REFERENCE_DOCS = ("planning_acceptance_record_template.md", "planning_acceptance_runbook.md")

def build_artifacts_dir(record_date: str, *, docs_dir: Path | None = None) -> Path:
    root = docs_dir or DOCS_DIR
    return root / "artifacts" / f"planning_acceptance_{record_date}"


def build_record_path(record_date: str, *, docs_dir: Path | None = None) -> Path:
    root = docs_dir or DOCS_DIR
    return root / "archive" / f"planning_acceptance_record_{record_date}.md"


def build_dry_run_workspace_root(record_date: str) -> Path:
    return Path(tempfile.mkdtemp(prefix=f"planning-acceptance-{record_date}."))


def seed_dry_run_workspace(workspace_root: Path) -> None:
    workspace_root.mkdir(parents=True, exist_ok=True)
    for name in DRY_RUN_REFERENCE_DOCS:
        source = DOCS_DIR / name
        if not source.exists():
            continue
        target = workspace_root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def prepare_acceptance(*, record_date: str, force: bool = False, dry_run: bool = False) -> dict[str, object]:
    reused_existing_record = False
    workspace_root = build_dry_run_workspace_root(record_date) if dry_run else DOCS_DIR
    if dry_run:
        seed_dry_run_workspace(workspace_root)
        record_path = create_record(
            record_date=record_date,
            force=True,
            docs_dir=workspace_root,
            template_path=workspace_root / "planning_acceptance_record_template.md",
        )
    else:
        existing_record_path = build_record_path(record_date)
        if existing_record_path.exists():
            record_path = build_record_path(record_date)
            reused_existing_record = True
        else:
            record_path = create_record(record_date=record_date, force=force)
    artifacts_dir = build_artifacts_dir(record_date, docs_dir=workspace_root)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    return {
        "ok": True,
        "record_date": record_date,
        "dry_run": dry_run,
        "workspace_root": str(workspace_root),
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
    parser.add_argument(
        "--force",
        action="store_true",
        help="Keep compatibility with older flows; existing repo archive records are preserved.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Create the planning acceptance workspace in a temporary location instead of docs/.",
    )
    parser.add_argument("--json", action="store_true", help="Print structured JSON output.")
    args = parser.parse_args()

    payload = prepare_acceptance(record_date=args.record_date, force=args.force, dry_run=args.dry_run)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(payload["record_path"])
        print(payload["artifacts_dir"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
