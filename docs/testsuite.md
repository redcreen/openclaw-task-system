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
- `python3 scripts/runtime/same_session_routing_acceptance.py --json`
- `python3 scripts/runtime/stable_acceptance.py --json`

They currently verify contracts such as:

- future-first `main_user_content_mode`
- planning materialization and anomaly projection
- same-session routing decisions and receipts
- installed-runtime sync and stable release expectations

## Real or Semi-Real Checks

These are important, but they are not part of the mandatory always-green automation layer:

- real Feishu or Telegram channel interaction
- `dashboard --json`
- `triage --json`
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

1. Python runtime / CLI regression
2. Node plugin / control-plane regression
3. Plugin Doctor
4. Plugin Smoke
