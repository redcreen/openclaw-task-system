#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


TASK_USER_CONTENT_BLOCK_RE = re.compile(r"<task_user_content>([\s\S]*?)</task_user_content>")
TASK_USER_CONTENT_OPEN = "<task_user_content>"
TASK_USER_CONTENT_CLOSE = "</task_user_content>"
DEFAULT_AGENTS_ROOT = Path.home() / ".openclaw" / "agents"
DEFAULT_SESSION_GLOB = "*.jsonl*"


@dataclass(frozen=True)
class ScrubChange:
    path: str
    markers_before: int
    markers_after: int
    changed: bool


def _normalize_inner_text(value: str) -> str:
    return " ".join(str(value or "").split())


def scrub_text(raw: str) -> tuple[str, bool]:
    text = str(raw or "")
    changed = False

    def replace_block(match: re.Match[str]) -> str:
        nonlocal changed
        changed = True
        return _normalize_inner_text(match.group(1))

    text = TASK_USER_CONTENT_BLOCK_RE.sub(replace_block, text)
    if TASK_USER_CONTENT_OPEN in text or TASK_USER_CONTENT_CLOSE in text:
        changed = True
        text = text.replace(TASK_USER_CONTENT_OPEN, "")
        text = text.replace(TASK_USER_CONTENT_CLOSE, "")
    return text, changed


def iter_session_files(agents_root: Path) -> list[Path]:
    if not agents_root.exists():
        return []
    files: list[Path] = []
    for session_dir in sorted(agents_root.glob("*/sessions")):
        files.extend(path for path in sorted(session_dir.glob(DEFAULT_SESSION_GLOB)) if path.is_file())
    return files


def run_scrub(*, agents_root: Path | None = None, apply: bool = False) -> dict[str, Any]:
    root = agents_root or DEFAULT_AGENTS_ROOT
    files = iter_session_files(root)
    changes: list[ScrubChange] = []

    for path in files:
        original = path.read_text(encoding="utf-8")
        markers_before = original.count(TASK_USER_CONTENT_OPEN) + original.count(TASK_USER_CONTENT_CLOSE)
        scrubbed, changed = scrub_text(original)
        markers_after = scrubbed.count(TASK_USER_CONTENT_OPEN) + scrubbed.count(TASK_USER_CONTENT_CLOSE)
        if changed and apply:
            path.write_text(scrubbed, encoding="utf-8")
        if changed:
            changes.append(
                ScrubChange(
                    path=str(path),
                    markers_before=markers_before,
                    markers_after=markers_after,
                    changed=True,
                )
            )

    return {
        "ok": True,
        "apply": apply,
        "agents_root": str(root),
        "scanned_files": len(files),
        "changed_files": len(changes),
        "changes": [asdict(change) for change in changes],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Task User Content History Scrub",
        "",
        f"- apply: {payload['apply']}",
        f"- agents_root: {payload['agents_root']}",
        f"- scanned_files: {payload['scanned_files']}",
        f"- changed_files: {payload['changed_files']}",
    ]
    if payload["changes"]:
        lines.extend(["", "## Changed Files", ""])
        for change in payload["changes"]:
            lines.append(
                f"- [{Path(change['path']).name}]({change['path']}): "
                f"markers_before={change['markers_before']}, markers_after={change['markers_after']}"
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrub historical <task_user_content> markers from agent session files.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of markdown.")
    parser.add_argument("--apply", action="store_true", help="Rewrite matching history files in place.")
    parser.add_argument("--agents-root", default=None, help="Override the OpenClaw agents root.")
    args = parser.parse_args()

    payload = run_scrub(
        agents_root=Path(args.agents_root).expanduser() if args.agents_root else None,
        apply=args.apply,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(payload), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
