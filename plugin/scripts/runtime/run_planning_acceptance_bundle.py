#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Iterable

from capture_planning_acceptance_artifacts import capture_artifacts

BUNDLE_SUMMARY_NAME = "bundle_summary.json"


def write_bundle_summary(artifacts_dir: str | None, payload: dict[str, object]) -> str | None:
    if not artifacts_dir:
        return None
    summary_path = Path(artifacts_dir) / BUNDLE_SUMMARY_NAME
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(summary_path)


def run_bundle(*, record_date: str, force: bool = False, labels: Iterable[str] | None = None) -> dict[str, object]:
    captured = capture_artifacts(record_date=record_date, force=force, labels=labels)
    results = list(captured.get("results", []))
    failed_labels = [str(item.get("label")) for item in results if not bool(item.get("ok"))]
    payload = {
        "ok": bool(captured.get("ok")),
        "record_date": record_date,
        "record_path": captured.get("record_path"),
        "artifacts_dir": captured.get("artifacts_dir"),
        "capture_manifest_path": captured.get("manifest_path"),
        "captured_count": len(results),
        "failed_count": len(failed_labels),
        "failed_labels": failed_labels,
        "results": results,
    }
    payload["bundle_summary_path"] = write_bundle_summary(captured.get("artifacts_dir"), payload)
    return payload


def render_markdown(payload: dict[str, object]) -> str:
    lines = [
        "# Planning Acceptance Bundle",
        "",
        f"- ok: {payload.get('ok')}",
        f"- record_path: {payload.get('record_path')}",
        f"- artifacts_dir: {payload.get('artifacts_dir')}",
        f"- captured_count: {payload.get('captured_count')}",
        f"- failed_count: {payload.get('failed_count')}",
        f"- failed_labels: {', '.join(payload.get('failed_labels', [])) or 'none'}",
    ]
    for result in payload.get("results", []):
        lines.append(f"- {result['label']}: {'ok' if result['ok'] else 'failed'}")
        lines.append(f"  output: {result['output_path']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the planning acceptance bundle and summarize the captured outputs.")
    parser.add_argument("--date", dest="record_date", default=date.today().isoformat())
    parser.add_argument("--force", action="store_true", help="Overwrite the record file if it already exists.")
    parser.add_argument("--json", action="store_true", help="Print structured JSON output.")
    parser.add_argument("--label", action="append", dest="labels", help="Run only the named capture label. May repeat.")
    args = parser.parse_args()

    payload = run_bundle(record_date=args.record_date, force=args.force, labels=args.labels)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(payload), end="")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
