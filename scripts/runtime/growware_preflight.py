#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from growware_project import (
    load_channel_definition,
    load_project_definition,
    required_growware_files,
    resolve_project_root,
)


def _check(ok: bool, name: str, detail: str) -> dict[str, Any]:
    return {"check": name, "ok": ok, "detail": detail}


def build_preflight_report(project_root: Path | None = None) -> dict[str, Any]:
    root = resolve_project_root(project_root)
    checks: list[dict[str, Any]] = []

    required = required_growware_files(root)
    missing = [str(path.relative_to(root)) for path in required if not path.exists()]
    checks.append(
        _check(not missing, "required-files", "all required .growware files exist" if not missing else f"missing: {missing}")
    )

    project = load_project_definition(root)
    channels = load_channel_definition(root)
    daemon = ((project.get("growware") or {}).get("daemon") or {})
    feedback = channels.get("feedbackChannel") or {}

    checks.append(
        _check(
            Path(str(project.get("projectRoot") or "")).resolve() == root,
            "project-root",
            f"projectRoot={project.get('projectRoot')}",
        )
    )
    checks.append(
        _check(
            daemon.get("agentId") == "growware",
            "daemon-agent-id",
            f"agentId={daemon.get('agentId')}",
        )
    )
    checks.append(
        _check(
            feedback.get("provider") == "feishu" and feedback.get("accountId") == "feishu6-chat",
            "feedback-channel",
            f"provider={feedback.get('provider')} accountId={feedback.get('accountId')}",
        )
    )
    roles = tuple(feedback.get("roles") or [])
    checks.append(
        _check(
            all(role in roles for role in ("feedback", "approval", "notification")),
            "feedback-roles",
            f"roles={list(roles)}",
        )
    )

    ok = all(check["ok"] for check in checks)
    return {
        "ok": ok,
        "projectRoot": str(root),
        "checks": checks,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Growware project-local contracts and channel bindings.")
    parser.add_argument("--project-root", type=Path, default=resolve_project_root())
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def render_markdown(payload: dict[str, Any]) -> str:
    lines = ["# Growware Preflight", ""]
    lines.append(f"- ok: {str(payload['ok']).lower()}")
    lines.append(f"- project_root: `{payload['projectRoot']}`")
    lines.append("")
    for check in payload["checks"]:
        status = "ok" if check["ok"] else "failed"
        lines.append(f"- {check['check']}: `{status}`")
        lines.append(f"  detail: {check['detail']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    payload = build_preflight_report(args.project_root)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(payload), end="")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
