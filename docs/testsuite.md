[English](testsuite.md) | [中文](testsuite.zh-CN.md)

# Test Suite

## What This Document Covers

This is the detailed test inventory for `openclaw-task-system`.

It explains:

- what `bash scripts/run_tests.sh` actually runs
- which tests validate runtime behavior, control-plane evidence, and install wiring
- which checks remain semi-real or manual acceptance rather than mandatory green automation

## Automated Layers

### 1. Python Runtime and CLI Regression

Primary command:

```bash
python3 -m unittest discover -s tests -v
```

Covers:

- runtime hooks and bridge behavior
- task truth source and state projection
- main ops, health, continuity, and watchdog
- planning helpers and acceptance scripts
- task CLI and operator commands

### 2. Node Plugin and Control-Plane Regression

Primary command:

```bash
node --test plugin/tests/*.test.mjs
```

Covers:

- immediate ack and pre-register state
- queue receipts and same-session receipts
- control-plane lane scheduling, supersede, and preemption
- delivery runners and scheduler diagnostics
- plugin lifecycle and terminal control-plane behavior

### 3. Plugin Doctor

Command:

```bash
python3 scripts/runtime/plugin_doctor.py
```

Validates:

- plugin manifest and entrypoint wiring
- runtime hooks path
- local installed runtime sync visibility

### 4. Plugin Smoke

Command:

```bash
python3 scripts/runtime/plugin_smoke.py --json
```

Validates:

- a minimal end-to-end register, progress, resolve, and finalize flow
- control-plane message structure
- task truth-source integrity through a small lifecycle

## Key Acceptance Helpers

These are still automated, but they represent contract-level acceptance rather than narrow unit tests:

- `python3 scripts/runtime/planning_acceptance.py --json`
- `python3 scripts/runtime/planning_acceptance_suite.py --json`
- `python3 scripts/runtime/main_ops_acceptance.py --json`
- `python3 scripts/runtime/channel_acceptance.py --json`
- `python3 scripts/runtime/same_session_routing_acceptance.py --json`
- `python3 scripts/runtime/stable_acceptance.py --json`

For planning evidence rehearsal without repo-side writes:

- `python3 scripts/runtime/run_planning_acceptance_bundle.py --dry-run --json`
- `python3 scripts/runtime/planning_acceptance_suite.py --dry-run --json`

They currently verify contracts such as:

- future-first `main_user_content_mode`
- planning materialization and anomaly projection
- operator-facing recovery guidance and short snapshot views across `dashboard`, `triage`, and `continuity`
- channel rollout matrix, session focus, and fallback-channel boundaries
- same-session routing decisions and receipts
- installed-runtime sync and stable release expectations

## Broader Release Gate

Use this when a change needs the full release-facing line rather than just the base regression:

```bash
python3 scripts/runtime/release_gate.py --json
```

It runs:

- `bash scripts/run_tests.sh`
- `python3 scripts/runtime/main_ops_acceptance.py --json`
- `python3 scripts/runtime/stable_acceptance.py --json`
- `python3 scripts/runtime/runtime_mirror.py --check --json`
- `python3 scripts/runtime/plugin_install_drift.py --json`

## Real or Semi-Real Checks

These are important, but they are not part of the mandatory always-green automation layer:

- real Feishu or Telegram channel interaction
- `dashboard --compact`
- `dashboard --json`
- `triage --compact`
- `triage --json`
- `continuity --compact`
- `continuity --only-issues`
- `planning --json`
- `continuity --json`
- `queues --json`
- `lanes --json`

Use [planning_acceptance_runbook.md](planning_acceptance_runbook.md) when a change touches real channel behavior.

## Full Entry Point

The canonical one-command regression remains:

```bash
bash scripts/run_tests.sh
```

That command runs:

0. runtime mirror validation
1. Python runtime / CLI regression
2. Node plugin / control-plane regression
3. Plugin Doctor
4. Plugin Smoke

For release-facing runtime work, run `python3 scripts/runtime/release_gate.py --json` on top of the base testsuite.
