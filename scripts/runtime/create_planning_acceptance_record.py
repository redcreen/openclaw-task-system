#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path


DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"
TEMPLATE_PATH = DOCS_DIR / "planning_acceptance_record_template.md"


def build_record_path(record_date: str) -> Path:
    return DOCS_DIR / f"planning_acceptance_record_{record_date}.md"


def build_record_content(record_date: str, template: str) -> str:
    lines = template.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    body = "\n".join(lines).rstrip() + "\n"
    return (
        f"# Planning Acceptance Record {record_date}\n\n"
        f"本记录由 `create_planning_acceptance_record.py` 基于模板生成，请按实际验收结果填写。\n\n"
        f"使用模板：\n\n"
        f"- [planning_acceptance_record_template.md](./planning_acceptance_record_template.md)\n\n"
        f"参考 runbook：\n\n"
        f"- [planning_acceptance_runbook.md](./planning_acceptance_runbook.md)\n\n"
        f"{body}"
    )


def create_record(*, record_date: str, force: bool = False) -> Path:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    target_path = build_record_path(record_date)
    if target_path.exists() and not force:
        raise FileExistsError(f"Record already exists: {target_path}")
    target_path.write_text(build_record_content(record_date, template), encoding="utf-8")
    return target_path


def build_next_steps(record_date: str) -> list[str]:
    return [
        f"Record: docs/planning_acceptance_record_{record_date}.md",
        "Run: python3 scripts/runtime/plugin_doctor.py",
        "Run: python3 scripts/runtime/plugin_smoke.py --json",
        "Run: python3 scripts/runtime/planning_acceptance.py --json",
        "Run: python3 scripts/runtime/stable_acceptance.py --json",
        "Run: python3 scripts/runtime/main_ops.py planning --json",
        "Run: python3 scripts/runtime/main_ops.py continuity --json",
        "Optional: python3 scripts/runtime/main_ops.py dashboard --json",
        "Optional: python3 scripts/runtime/main_ops.py triage --json",
    ]


def build_json_payload(record_date: str, target_path: Path, *, created: bool) -> dict[str, object]:
    return {
        "ok": True,
        "created": created,
        "record_date": record_date,
        "record_path": str(target_path),
        "next_steps": build_next_steps(record_date),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a dated planning acceptance record from the template.")
    parser.add_argument("--date", dest="record_date", default=date.today().isoformat())
    parser.add_argument("--force", action="store_true", help="Overwrite the target file if it already exists.")
    parser.add_argument("--print-next-steps", action="store_true", help="Print recommended follow-up commands.")
    parser.add_argument("--json", action="store_true", help="Print structured JSON output.")
    args = parser.parse_args()

    created = True
    try:
        target_path = create_record(record_date=args.record_date, force=args.force)
    except FileExistsError:
        target_path = build_record_path(args.record_date)
        created = False
    if args.json:
        print(json.dumps(build_json_payload(args.record_date, target_path, created=created), ensure_ascii=False, indent=2))
        return 0
    print(target_path)
    if args.print_next_steps:
        for line in build_next_steps(args.record_date):
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
