#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = PROJECT_ROOT / "scripts" / "runtime"

RELEASE_GATE_SCHEMA = "openclaw.task-system.release-gate.v1"
RELEASE_GATE_VERSION = 1


@dataclass(frozen=True)
class ReleaseGateCommand:
    step: str
    command: list[str]
    expects_json: bool = False


def build_release_gate_commands() -> list[ReleaseGateCommand]:
    python = sys.executable or "python3"
    return [
        ReleaseGateCommand("testsuite", ["bash", str(PROJECT_ROOT / "scripts" / "run_tests.sh")]),
        ReleaseGateCommand(
            "main-ops-acceptance",
            [python, str(RUNTIME_DIR / "main_ops_acceptance.py"), "--json"],
            expects_json=True,
        ),
        ReleaseGateCommand(
            "stable-acceptance",
            [python, str(RUNTIME_DIR / "stable_acceptance.py"), "--json"],
            expects_json=True,
        ),
        ReleaseGateCommand(
            "runtime-mirror",
            [python, str(RUNTIME_DIR / "runtime_mirror.py"), "--check", "--json"],
            expects_json=True,
        ),
        ReleaseGateCommand(
            "plugin-install-drift",
            [python, str(RUNTIME_DIR / "plugin_install_drift.py"), "--json"],
            expects_json=True,
        ),
    ]


def _last_non_empty_line(*texts: str) -> str | None:
    for text in texts:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if lines:
            return lines[-1]
    return None


def _parse_json_payload(stdout: str) -> tuple[dict[str, Any] | None, str | None]:
    if not stdout.strip():
        return None, "empty-stdout"
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return None, f"invalid-json: {exc.msg}"
    if not isinstance(payload, dict):
        return None, "non-object-json"
    return payload, None


def _build_step_metrics(step: str, payload: dict[str, Any]) -> dict[str, object]:
    if step in {"main-ops-acceptance", "stable-acceptance"}:
        raw_steps = payload.get("steps")
        nested_steps = raw_steps if isinstance(raw_steps, list) else []
        failed_nested_steps = sum(1 for item in nested_steps if isinstance(item, dict) and not bool(item.get("ok")))
        return {
            "reported_ok": bool(payload.get("ok")),
            "step_count": len(nested_steps),
            "failed_step_count": failed_nested_steps,
        }
    if step == "runtime-mirror":
        missing = payload.get("missing_in_mirror") if isinstance(payload.get("missing_in_mirror"), list) else []
        extra = payload.get("extra_in_mirror") if isinstance(payload.get("extra_in_mirror"), list) else []
        changed = payload.get("changed_files") if isinstance(payload.get("changed_files"), list) else []
        return {
            "reported_ok": bool(payload.get("ok")),
            "missing_in_mirror_count": len(missing),
            "extra_in_mirror_count": len(extra),
            "changed_file_count": len(changed),
        }
    if step == "plugin-install-drift":
        missing = payload.get("missing_in_installed") if isinstance(payload.get("missing_in_installed"), list) else []
        extra = payload.get("extra_in_installed") if isinstance(payload.get("extra_in_installed"), list) else []
        return {
            "reported_ok": bool(payload.get("ok")),
            "missing_in_installed_count": len(missing),
            "extra_in_installed_count": len(extra),
        }
    return {"reported_ok": bool(payload.get("ok"))}


def _build_step_summary(
    step: str,
    *,
    returncode: int,
    stdout: str,
    stderr: str,
    payload: dict[str, Any] | None,
    parse_error: str | None,
) -> str:
    if parse_error:
        return parse_error
    if step == "testsuite":
        return _last_non_empty_line(stdout, stderr) or f"returncode={returncode}"
    if payload is None:
        return _last_non_empty_line(stderr, stdout) or f"returncode={returncode}"
    if step in {"main-ops-acceptance", "stable-acceptance"}:
        nested_steps = payload.get("steps") if isinstance(payload.get("steps"), list) else []
        failed_nested_steps = sum(1 for item in nested_steps if isinstance(item, dict) and not bool(item.get("ok")))
        return f"reported_ok={bool(payload.get('ok'))} steps={len(nested_steps)} failed={failed_nested_steps}"
    if step == "runtime-mirror":
        missing = payload.get("missing_in_mirror") if isinstance(payload.get("missing_in_mirror"), list) else []
        extra = payload.get("extra_in_mirror") if isinstance(payload.get("extra_in_mirror"), list) else []
        changed = payload.get("changed_files") if isinstance(payload.get("changed_files"), list) else []
        return f"reported_ok={bool(payload.get('ok'))} missing={len(missing)} extra={len(extra)} changed={len(changed)}"
    if step == "plugin-install-drift":
        missing = payload.get("missing_in_installed") if isinstance(payload.get("missing_in_installed"), list) else []
        extra = payload.get("extra_in_installed") if isinstance(payload.get("extra_in_installed"), list) else []
        return f"reported_ok={bool(payload.get('ok'))} missing={len(missing)} extra={len(extra)}"
    return _last_non_empty_line(stdout, stderr) or f"returncode={returncode}"


def run_release_gate() -> dict[str, Any]:
    steps: list[dict[str, object]] = []

    for command in build_release_gate_commands():
        completed = subprocess.run(
            command.command,
            capture_output=True,
            text=True,
            check=False,
            cwd=PROJECT_ROOT,
        )
        payload = None
        parse_error = None
        metrics: dict[str, object] = {}
        if command.expects_json:
            payload, parse_error = _parse_json_payload(completed.stdout)
            if payload is not None:
                metrics = _build_step_metrics(command.step, payload)
            if parse_error:
                metrics["parse_error"] = parse_error
        else:
            last_output_line = _last_non_empty_line(completed.stdout, completed.stderr)
            if last_output_line:
                metrics["last_output_line"] = last_output_line

        ok = completed.returncode == 0
        if command.expects_json:
            ok = ok and parse_error is None and payload is not None and bool(payload.get("ok"))

        steps.append(
            {
                "step": command.step,
                "ok": ok,
                "returncode": completed.returncode,
                "command": command.command,
                "summary": _build_step_summary(
                    command.step,
                    returncode=completed.returncode,
                    stdout=completed.stdout,
                    stderr=completed.stderr,
                    payload=payload,
                    parse_error=parse_error,
                ),
                "metrics": metrics,
            }
        )

    failed_step_count = sum(1 for step in steps if not bool(step["ok"]))
    return {
        "schema": RELEASE_GATE_SCHEMA,
        "version": RELEASE_GATE_VERSION,
        "project_root": str(PROJECT_ROOT),
        "ok": failed_step_count == 0,
        "step_count": len(steps),
        "failed_step_count": failed_step_count,
        "steps": steps,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = ["# Release Gate", ""]
    lines.append(f"- ok: {payload.get('ok')}")
    lines.append(f"- step_count: {payload.get('step_count')}")
    lines.append(f"- failed_step_count: {payload.get('failed_step_count')}")
    for step in payload.get("steps", []):
        status = "ok" if step.get("ok") else "failed"
        lines.append(f"- {step.get('step')}: {status}")
        lines.append(f"  summary: {step.get('summary')}")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = sys.argv[1:]
    payload = run_release_gate()
    if args and args[0] == "--json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(payload), end="")
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
