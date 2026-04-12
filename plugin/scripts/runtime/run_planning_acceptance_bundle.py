#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Iterable

from capture_planning_acceptance_artifacts import capture_artifacts
from create_planning_acceptance_record import build_record_path

BUNDLE_SUMMARY_NAME = "bundle_summary.json"

PROMOTION_STATUS_ALREADY_ARCHIVED = "already-archived"
PROMOTION_STATUS_BLOCKED = "blocked"
PROMOTION_STATUS_INSUFFICIENT_SIGNAL = "insufficient-signal"
PROMOTION_STATUS_READY_FOR_ARCHIVE = "ready-for-archive"


def write_bundle_summary(artifacts_dir: str | None, payload: dict[str, object]) -> str | None:
    if not artifacts_dir:
        return None
    summary_path = Path(artifacts_dir) / BUNDLE_SUMMARY_NAME
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(summary_path)


def build_archive_promotion_policy(
    *,
    record_date: str,
    dry_run: bool,
    ok: bool,
    labels: Iterable[str] | None = None,
) -> dict[str, object]:
    filtered_labels = [str(label) for label in labels or [] if str(label).strip()]
    archive_record_path = str(build_record_path(record_date))
    promotion_command = f"python3 scripts/runtime/run_planning_acceptance_bundle.py --json --date {record_date}"

    if not dry_run and ok:
        return {
            "status": PROMOTION_STATUS_ALREADY_ARCHIVED,
            "promotion_ready": False,
            "promotion_required_for_release_facing_changes": False,
            "archive_record_path": archive_record_path,
            "promotion_command": None,
            "reason": "This run already wrote repo-side evidence instead of a dry-run workspace.",
            "required_when": None,
        }
    if not ok:
        return {
            "status": PROMOTION_STATUS_BLOCKED,
            "promotion_ready": False,
            "promotion_required_for_release_facing_changes": False,
            "archive_record_path": archive_record_path,
            "promotion_command": None,
            "reason": "Promotion is blocked until the dry-run bundle is fully green.",
            "required_when": None,
        }
    if filtered_labels:
        return {
            "status": PROMOTION_STATUS_INSUFFICIENT_SIGNAL,
            "promotion_ready": False,
            "promotion_required_for_release_facing_changes": False,
            "archive_record_path": archive_record_path,
            "promotion_command": None,
            "reason": "Label-filtered dry-runs only cover part of the evidence set and cannot justify a dated archive refresh by themselves.",
            "required_when": None,
        }
    return {
        "status": PROMOTION_STATUS_READY_FOR_ARCHIVE,
        "promotion_ready": True,
        "promotion_required_for_release_facing_changes": True,
        "archive_record_path": archive_record_path,
        "promotion_command": promotion_command,
        "reason": "A full dry-run bundle is green and can now be promoted into a dated archive record.",
        "required_when": (
            "Promote before merge when the change touches planning/runtime contracts, "
            "release-facing acceptance coverage, or the planning evidence workflow itself."
        ),
    }


def run_bundle(
    *,
    record_date: str,
    force: bool = False,
    dry_run: bool = False,
    labels: Iterable[str] | None = None,
) -> dict[str, object]:
    captured = capture_artifacts(record_date=record_date, force=force, dry_run=dry_run, labels=labels)
    results = list(captured.get("results", []))
    failed_labels = [str(item.get("label")) for item in results if not bool(item.get("ok"))]
    payload = {
        "ok": bool(captured.get("ok")),
        "record_date": record_date,
        "dry_run": bool(captured.get("dry_run")),
        "workspace_root": captured.get("workspace_root"),
        "record_path": captured.get("record_path"),
        "artifacts_dir": captured.get("artifacts_dir"),
        "capture_manifest_path": captured.get("manifest_path"),
        "captured_count": len(results),
        "failed_count": len(failed_labels),
        "failed_labels": failed_labels,
        "results": results,
    }
    payload["promotion_policy"] = build_archive_promotion_policy(
        record_date=record_date,
        dry_run=bool(payload["dry_run"]),
        ok=bool(payload["ok"]),
        labels=labels,
    )
    payload["bundle_summary_path"] = write_bundle_summary(captured.get("artifacts_dir"), payload)
    return payload


def render_markdown(payload: dict[str, object]) -> str:
    promotion_policy = payload.get("promotion_policy", {})
    lines = [
        "# Planning Acceptance Bundle",
        "",
        f"- ok: {payload.get('ok')}",
        f"- dry_run: {payload.get('dry_run')}",
        f"- workspace_root: {payload.get('workspace_root')}",
        f"- record_path: {payload.get('record_path')}",
        f"- artifacts_dir: {payload.get('artifacts_dir')}",
        f"- captured_count: {payload.get('captured_count')}",
        f"- failed_count: {payload.get('failed_count')}",
        f"- failed_labels: {', '.join(payload.get('failed_labels', [])) or 'none'}",
        f"- promotion_status: {promotion_policy.get('status')}",
        f"- promotion_ready: {promotion_policy.get('promotion_ready')}",
        f"- archive_record_path: {promotion_policy.get('archive_record_path')}",
        f"- promotion_command: {promotion_policy.get('promotion_command') or 'none'}",
    ]
    for result in payload.get("results", []):
        lines.append(f"- {result['label']}: {'ok' if result['ok'] else 'failed'}")
        lines.append(f"  output: {result['output_path']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the planning acceptance bundle and summarize the captured outputs.")
    parser.add_argument("--date", dest="record_date", default=date.today().isoformat())
    parser.add_argument(
        "--force",
        action="store_true",
        help="Keep compatibility with older flows; existing repo archive records are preserved.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use a temporary planning-acceptance workspace instead of docs/.",
    )
    parser.add_argument("--json", action="store_true", help="Print structured JSON output.")
    parser.add_argument("--label", action="append", dest="labels", help="Run only the named capture label. May repeat.")
    args = parser.parse_args()

    payload = run_bundle(record_date=args.record_date, force=args.force, dry_run=args.dry_run, labels=args.labels)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(payload), end="")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
