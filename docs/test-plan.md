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
| Channel rollout boundary | producer contract is loaded | Inspect channel acceptance samples for matrix, focus, and fallback cases | each channel stays validated or bounded under the current rollout contract |
| Operator recovery projection | dashboard, triage, and continuity entrypoints are available | Inspect operator acceptance samples for planning recovery, watchdog risk, and snapshot views | operator views suggest coherent next actions, short duty snapshots, and runbooks from the same truth source |
| Future-first | request requiring delayed or scheduled work | inspect immediate output behavior | runtime enforces the structured `main_user_content_mode` contract |
| Recovery and continuity | task exists across restart or delayed wake | run continuity and watchdog flows | task state, continuation, and user-visible explanation remain coherent |
| Install drift observability | source repo and installed runtime both exist | run doctor and drift checks | drift is surfaced in doctor, ops views, and stable acceptance |

## Automation Coverage

Automated release confidence requires:

- `bash scripts/run_tests.sh`
- `python3 scripts/runtime/release_gate.py --json`

`release_gate.py` keeps the broader release-facing line explicit by running the base testsuite together with main-ops acceptance, stable acceptance, runtime mirror, and plugin install-drift checks.

The testsuite must cover:

- Python runtime and CLI regressions
- Node plugin and control-plane regressions
- plugin doctor
- plugin smoke
- main ops acceptance helpers
- channel acceptance helpers
- planning acceptance helpers
- same-session routing acceptance

Current release-facing sample depth explicitly includes:

- scheduled follow-up summaries staying in control-plane projection
- bounded-focus coverage for `webchat`
- `followup-task-missing` operator recovery projection

Detailed grouping lives in [testsuite.md](testsuite.md).

## Manual Checks

Run these when touching real delivery behavior or planning contracts:

- `python3 scripts/runtime/planning_acceptance.py --json`
- `python3 scripts/runtime/planning_acceptance_suite.py --json`
- `python3 scripts/runtime/planning_acceptance_suite.py --dry-run --json`
- `python3 scripts/runtime/run_planning_acceptance_bundle.py --dry-run --json`
- `python3 scripts/runtime/main_ops_acceptance.py --json`
- `python3 scripts/runtime/channel_acceptance.py --json`
- `python3 scripts/runtime/same_session_routing_acceptance.py --json`
- `python3 scripts/runtime/main_ops.py continuity --compact`
- `python3 scripts/runtime/main_ops.py continuity --only-issues`
- `python3 scripts/runtime/main_ops.py triage --compact`
- channel-specific real or semi-real checks from [planning_acceptance_runbook.md](planning_acceptance_runbook.md)

## Test Data and Fixtures

The main fixture sources are:

- runtime task state under `tests/`
- plugin control-plane fixtures under `plugin/tests/`
- temporary planning artifacts under `docs/artifacts/`

Historical acceptance records belong in [archive/README.md](archive/README.md), not in the active docs stack.

## Release Gate

A release or merge-ready change set should satisfy all of the following:

- `python3 scripts/runtime/release_gate.py --json` reports `ok: true`
- documentation matches shipped behavior and current entrypoints
- if runtime or plugin behavior changed, installable payload and local deployment steps are kept in sync
