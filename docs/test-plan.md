# Test Plan

[English](test-plan.md) | [中文](test-plan.zh-CN.md)

## Scope and Risk

The release gate for `openclaw-task-system` is about runtime behavior, not isolated helper functions.

The core risks are:

- user-visible control-plane receipts drifting away from runtime truth
- planned follow-up and continuation becoming implicit or lossy
- same-session follow-up routing behaving differently from its runtime-owned contract
- installable plugin payload drifting away from the local installed runtime
- operator views hiding planning anomalies or recovery actions

## Acceptance Cases

| Case | Setup | Action | Expected Result |
| --- | --- | --- | --- |
| Core long task | OpenClaw task runtime enabled | Register a normal long task | runtime creates or reuses a task and returns a `[wd]` receipt |
| Same-session routing | active session with follow-up input | Send refinement, independent request, control command, or collect-more input | runtime selects `steering / queueing / control-plane / collect-more` and returns a runtime-owned receipt |
| Planning follow-up | planning-enabled runtime | Create structured follow-up plan and materialize it | follow-up becomes a real task with stable truth-source state |
| Future-first | request requiring delayed or scheduled work | inspect immediate output behavior | runtime enforces the structured `main_user_content_mode` contract |
| Recovery and continuity | task exists across restart or delayed wake | run continuity and watchdog flows | task state, continuation, and user-visible explanation remain coherent |
| Install drift observability | source repo and installed runtime both exist | run doctor and drift checks | drift is surfaced in doctor, ops views, and stable acceptance |

## Automation Coverage

Automated release confidence requires:

- `bash scripts/run_tests.sh`
- `python3 scripts/runtime/stable_acceptance.py --json`

The testsuite must cover:

- Python runtime and CLI regressions
- Node plugin and control-plane regressions
- plugin doctor
- plugin smoke
- planning acceptance helpers
- same-session routing acceptance

Detailed grouping lives in [testsuite.md](testsuite.md).

## Manual and Semi-Real Checks

Run these when touching real delivery behavior or planning contracts:

- `python3 scripts/runtime/planning_acceptance.py --json`
- `python3 scripts/runtime/planning_acceptance_suite.py --json`
- `python3 scripts/runtime/same_session_routing_acceptance.py --json`
- channel-specific real or semi-real checks from [planning_acceptance_runbook.md](planning_acceptance_runbook.md)

## Test Data and Fixtures

The main fixture sources are:

- runtime task state under `tests/`
- plugin control-plane fixtures under `plugin/tests/`
- temporary planning artifacts under `docs/artifacts/`

Historical acceptance records belong in [archive/README.md](archive/README.md), not in the active docs stack.

## Release Gate

A release or merge-ready change set should satisfy all of the following:

- `bash scripts/run_tests.sh` is green
- `python3 scripts/runtime/stable_acceptance.py --json` reports `ok: true`
- documentation matches shipped behavior and current entrypoints
- if runtime or plugin behavior changed, installable payload and local deployment steps are kept in sync
