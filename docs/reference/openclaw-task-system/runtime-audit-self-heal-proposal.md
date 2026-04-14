[English](runtime-audit-self-heal-proposal.md) | [中文](runtime-audit-self-heal-proposal.zh-CN.md)

# Runtime Audit And Self-Heal Proposal

## Status

- Status: `proposal`
- Decision state: discussion draft only
- Milestone state: not an active roadmap milestone yet

This document describes a proposed next capability line for OpenClaw host-side operations.

It should not be treated as an already-approved milestone until the user explicitly confirms the direction.

## Why This Proposal Exists

The current repo already has strong repo-local verification:

- testsuite
- release gate
- main-ops acceptance
- stable acceptance

Those checks are still necessary, but they do not prove that the real OpenClaw host is healthy today.

Recent host-side evidence showed that real runtime issues can exist even while repo-local verification stays green:

- stale tasks remained marked as `running`
- delivery failures accumulated under `~/.openclaw/delivery-queue/failed/`
- cron jobs recorded real delivery errors
- at least one user-visible reply still contained an internal `<task_user_content>` marker

So the missing layer is a host-side audit and recovery loop that evaluates real runtime behavior from logs and task records, not just tests.

## Problem Statement

Today, host-side health is split across multiple truth sources:

- `~/.openclaw/tasks/runs.sqlite`
- `~/.openclaw/delivery-queue/failed/`
- `~/.openclaw/cron/runs/*.jsonl`
- `~/.openclaw/logs/config-health.json`
- recent delivered replies and task summaries

This causes four operational gaps:

1. it is too easy to conclude “system is healthy” from tests while the host still has stale runtime residue
2. user-visible quality problems are not elevated as first-class health failures
3. repair work is manual and ad hoc
4. there is no single command suitable for daily manual checks or a scheduled audit loop

## Goals

The proposed capability should provide one durable command that:

1. reads real OpenClaw host data from `~/.openclaw`
2. reports system health from an operator view
3. reports behavior quality from a user-visible view
4. classifies findings into `safe to auto-fix`, `needs review`, or `human-only`
5. supports a dry-run-first repair path
6. can later run on a schedule without polluting repo docs with host-specific noise

## Non-Goals

This proposal does not aim to:

- replace tests, acceptance, or release gates
- auto-edit business content or rewrite user history without an explicit policy
- assume that “no error log” means “good user experience”
- silently mutate host data without a dry-run and safety policy
- convert every host-side warning into an automatic fix

## Proposed Command Surface

Canonical audit command:

```bash
python3 scripts/runtime/openclaw_runtime_audit.py
python3 scripts/runtime/openclaw_runtime_audit.py --json
python3 scripts/runtime/openclaw_runtime_audit.py --lookback-hours 48 --recent-limit 20
```

Planned follow-up repair commands:

```bash
python3 scripts/runtime/openclaw_runtime_repair.py --dry-run
python3 scripts/runtime/openclaw_runtime_repair.py --apply-safe
python3 scripts/runtime/openclaw_runtime_repair.py --json --dry-run
```

The current repo now has the first read-only audit entrypoint.

It should be treated as Phase 0 bootstrap, not the finished self-heal system.

## Audit Model

The audit should always produce two views from the same host-side truth source.

### 1. Operator View

This view answers:

- is the host currently healthy enough to trust
- are there stale running tasks
- are failed deliveries accumulating
- are cron jobs succeeding or failing
- is host config health stable

Representative checks:

- stale running tasks beyond a configurable threshold
- failed delivery queue size, age, retry count, and channel distribution
- recent cron error count and latest error summaries
- config health missing or suspicious signatures
- recent task status and delivery status distribution

### 2. User View

This view answers:

- what users recently asked
- what the system actually replied
- whether recent replies look user-safe
- whether internal markers or obvious control-plane leakage escaped

Representative checks:

- recent request / reply summary pairs
- user-visible output still containing `<task_user_content>`
- internal runtime context or subagent noise appearing in user-facing history
- successful task with missing usable terminal summary
- repeated failures affecting the same user / channel / session

## Proposed Finding Classes

| Finding Class | Example | Severity | Auto-Fix Eligibility | Default Handling |
| --- | --- | --- | --- | --- |
| stale task state | task marked `running` for days with no fresh event | error | maybe later, not by default | inspect then resume / fail / purge |
| retryable delivery residue | transient transport failure with valid target | warn | yes, after safety checks | host retry path |
| invalid recipient / binding | Telegram slash target cannot resolve | warn or error | no | fix address / session binding first |
| config health drift | suspicious signature or missing health log | warn | no | inspect config source |
| cron delivery failure | scheduled run completes with delivery error | warn | maybe later | inspect job target and rerun |
| user-visible content leak | `<task_user_content>` appears in a delivered reply | error | no silent fix | raise immediately and repair content path |
| internal context leak | internal runtime/subagent text exposed to user view | error | no silent fix | inspect output boundary before reuse |

## Proposed Repair Policy

Auto-repair must be layered and conservative.

### Safe To Auto-Fix

These may become eligible for `--apply-safe` once the dry-run path proves reliable:

- retryable failed deliveries with valid recipient metadata
- stale delivery residue cleanup already proven by existing reconciliation rules
- duplicate or obviously superseded failed-delivery artifacts
- acknowledged transport outage retry after outage is cleared

### Dry-Run First, Human Review Before Apply

These should first emit a concrete repair plan:

- stale running task state
- cron failure with ambiguous destination or reply target
- partial config drift
- repeated failure bursts affecting one audience

### Human-Only

These should not be auto-fixed silently:

- user-visible content leaks
- internal marker leakage
- wrong recipient mapping
- destructive cleanup of active user task history
- any repair that changes the meaning of a business reply

## Proposed Architecture

### Layer 1. Host-Side Audit Reader

Inputs:

- `runs.sqlite`
- failed delivery queue
- cron run logs
- config health
- recent user-visible task summaries

Output:

- stable JSON payload
- human-readable markdown summary

### Layer 2. Rule Engine

This layer maps raw signals into:

- severity
- finding code
- count
- explanation
- remediation command
- repair eligibility

### Layer 3. Repair Planner

This layer converts findings into explicit actions:

- `retry-failed-deliveries`
- `reconcile-stale-delivery-artifacts`
- `inspect-stale-running-task`
- `inspect-user-visible-content-leak`
- `inspect-cron-binding`

The planner should support `--dry-run` before any host mutation.

### Layer 4. Repair Executor

This layer is only for actions already classified as safe.

It should:

- log exactly what it touched
- report before / after deltas
- never hide a failed repair attempt

### Layer 5. Scheduled Operation

Later, a scheduled run can do:

1. audit
2. classify
3. optionally apply safe fixes
4. emit a compact summary
5. keep a host-local audit history

Recommended storage for scheduled audit output:

- host-local under `~/.openclaw/logs/runtime-audit/`

Do not write host-specific daily audit artifacts back into repo docs by default.

## Proposed Phases

### Phase 0. Read-Only Audit Bootstrap

Goal:

- one reliable command to inspect real host-side runtime data

Scope:

- operator view
- user view
- stale tasks
- failed deliveries
- cron errors
- config health
- user-visible marker leakage

Current state:

- bootstrap command is now present as `openclaw_runtime_audit.py`

Exit condition:

- the audit output is stable enough to serve as the daily manual health entrypoint

### Phase 1. Repair Planning Contract

Goal:

- turn audit findings into explicit repair actions

Scope:

- action kind
- safety class
- dry-run preview
- recommended command

Exit condition:

- every major finding class has a consistent repair plan structure

### Phase 2. Safe Repair Dry-Run

Goal:

- simulate safe repair actions without mutating host state

Scope:

- retryable failed deliveries
- stale delivery cleanup
- bounded cron rerun suggestions

Exit condition:

- dry-run output is trustworthy enough to review before applying

### Phase 3. Safe Repair Apply

Goal:

- allow one explicit command to apply only the safe subset

Exit condition:

- safe repair paths are idempotent, observable, and reversible enough for daily operations

### Phase 4. Scheduled Daily Operation

Goal:

- run the audit automatically every day and optionally apply safe fixes

Scope:

- host-local log output
- non-zero exit on actionable problems
- compact summary for notifications or daily review

Exit condition:

- the system can self-check on a schedule without producing false confidence

## Operational Contract

Daily manual use:

```bash
python3 scripts/runtime/openclaw_runtime_audit.py
```

Daily machine-readable use:

```bash
python3 scripts/runtime/openclaw_runtime_audit.py --json
```

Future scheduled use:

```bash
python3 scripts/runtime/openclaw_runtime_audit.py --json && \
python3 scripts/runtime/openclaw_runtime_repair.py --dry-run --json
```

The audit command should keep a non-zero exit code when actionable problems exist.

That allows cron or other schedulers to treat audit failures as real events instead of decorative reports.

## Discussion Decisions Needed

Before promoting this proposal into an active milestone, these decisions should be made explicitly.

1. Should scheduled runs remain `audit-only`, or may they apply safe fixes automatically
2. Which channels are in initial self-heal scope: Feishu only, Telegram only, or both
3. How aggressive may stale-task recovery be before human review
4. Should user-visible content leaks trigger an immediate high-priority alert
5. Where should scheduled summaries be delivered: local logs only, OpenClaw message, or both

## Recommended Next Step

Do not start the full self-heal milestone yet.

Use this proposal as the discussion baseline, decide the auto-repair boundary first, and then promote the approved subset into a named roadmap candidate or active workstream.
