# Converge Broader Release Gate

## Problem

The repo already relied on a broader release-facing verification line than `bash scripts/run_tests.sh`, but that line only existed as an implicit command bundle spread across status notes and maintainer memory.

That created two maintenance risks:

- a release-facing change could pass the base testsuite while skipping stable acceptance, operator acceptance, or drift visibility
- docs could describe a "broader gate" without giving maintainers one canonical entrypoint to run

## Key Thinking

The right fix was not to fold everything into `run_tests.sh`.

`run_tests.sh` is still the fast, canonical regression entrypoint. The broader release-facing line is intentionally heavier and more targeted:

- base testsuite
- operator acceptance
- stable acceptance
- runtime mirror
- install drift

So the gap was not missing checks. The gap was execution ownership.

The maintainable fix is to keep the existing checks as-is, then add one runtime-owned wrapper that runs all of them, preserves per-step visibility, and reports which step failed.

## Solution

Added `scripts/runtime/release_gate.py` as the explicit broader release-gate entrypoint.

It now runs:

- `bash scripts/run_tests.sh`
- `python3 scripts/runtime/main_ops_acceptance.py --json`
- `python3 scripts/runtime/stable_acceptance.py --json`
- `python3 scripts/runtime/runtime_mirror.py --check --json`
- `python3 scripts/runtime/plugin_install_drift.py --json`

The wrapper keeps going after an individual failure so maintainers get a full report instead of only the first red step.

Also updated:

- test coverage for success, failure propagation, and markdown / JSON output
- usage, test-plan, testsuite, and installation docs
- `.codex/status.md` and `.codex/plan.md` so the control surface points to the same entrypoint

## Validation

- `python3 -m unittest discover -s tests -p 'test_release_gate.py' -v`
- `python3 scripts/runtime/release_gate.py --json`

## Follow-Up

The next post-hardening slice should move from gate convergence to evidence depth:

- real or semi-real Feishu / Telegram evidence capture
- or dry-run-friendly planning bundle convergence so broader evidence collection can run without repo-side side effects
