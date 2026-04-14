[English](growware-pilot.md) | [中文](growware-pilot.zh-CN.md)

# Growware Pilot Integration Draft

## What This Is

This document explains how `openclaw-task-system` is onboarded as Growware `Project 1`, with `feishu6-chat` as the real human feedback, approval, and notification ingress.

It does not replace OpenClaw or the task-system runtime. It adds a project-local control layer plus safe host binding.

## Current Defaults

- `Project 1 = openclaw-task-system`
- `A channel = feishu6-chat`
- `A roles = feedback + approval + notification`
- `Telegram = fallback candidate`
- Every channel that already mounts `openclaw-task-system` is treated as the `B` runtime surface
- Durable project truth now lives under [`.growware/`](../../../.growware/README.md)

## Topology

```text
feishu6-chat
  -> OpenClaw binding
  -> growware agent
  -> openclaw-task-system repo workspace
  -> Codex edits / tests / local deploy

task-system runtime
  -> plugin/runtime logs
  -> Growware judge / deploy gate
  -> feishu6 notification
```

## Project-Local Truth

- [`.growware/project.json`](../../../.growware/project.json)
- [`.growware/channels.json`](../../../.growware/channels.json)
- [`.growware/contracts/feedback-event.v1.json`](../../../.growware/contracts/feedback-event.v1.json)
- [`.growware/contracts/incident-record.v1.json`](../../../.growware/contracts/incident-record.v1.json)
- [`.growware/ops/daemon-interface.v1.json`](../../../.growware/ops/daemon-interface.v1.json)
- [`.growware/policies/feedback-intake.v1.json`](../../../.growware/policies/feedback-intake.v1.json)
- [`.growware/policies/judge.v1.json`](../../../.growware/policies/judge.v1.json)
- [`.growware/policies/deploy-gate.v1.json`](../../../.growware/policies/deploy-gate.v1.json)
- [`docs/policy/README.md`](../../../docs/policy/README.md)
- [`.policy/manifest.json`](../../../.policy/manifest.json)
- [`.policy/index.json`](../../../.policy/index.json)
- [`.policy/rules/growware.feedback-intake.same-session.v1.json`](../../../.policy/rules/growware.feedback-intake.same-session.v1.json)
- [`.policy/rules/growware.project.local-deploy.v1.json`](../../../.policy/rules/growware.project.local-deploy.v1.json)

The current contract is layered like this:

- `docs/policy/*.md`: human-reviewed policy source
- `.policy/`: compiled machine execution layer that Growware runtime should consume
- `.growware/contracts/` and `.growware/ops/`: project-local control surface and executable wiring
- `.growware/policies/*.json`: compatibility inputs retained while the repo finishes migrating away from legacy policy JSON

## Current Baseline

- `growware` agent's same-session classifier is driven by the compiled `.policy/rules/growware.feedback-intake.same-session.v1.json`
- natural-language feedback on `feishu6-chat` first enters daemon-owned intake, then gets routed into the current task or a new task
- Growware close-out now requires an explicit execution source: `daemon-owned` or `terminal-takeover`
- for the `growware` agent, completion also flows back through the control-plane lane to `feishu6` instead of relying only on body text

## Session Hygiene

- `feishu6-chat` is a production feedback ingress, so its transcript cannot stay polluted by `terminal-takeover` work
- If the dedicated `growware` direct session has mixed in manual debugging context, rotate the session before accepting more real feedback
- Rotation archives the old transcript, issues a fresh session id, and can fail the stuck task with an explicit reason

Inspect the current production session:

```bash
python3 scripts/runtime/growware_session_hygiene.py \
  --session-key 'agent:growware:feishu:direct:ou_6bead7a2b071454aeed7239e9de15d62' \
  --json
```

Rotate the production session and archive the stuck task as failed:

```bash
python3 scripts/runtime/growware_session_hygiene.py \
  --session-key 'agent:growware:feishu:direct:ou_6bead7a2b071454aeed7239e9de15d62' \
  --fail-task-id task_487d4937033a4a2da97d6044e1b53af2 \
  --failure-reason session-polluted-by-terminal-takeover \
  --reset \
  --restart \
  --json
```

## Operational Commands

Preflight:

```bash
python3 scripts/runtime/growware_preflight.py --json
```

Preview the OpenClaw binding:

```bash
python3 scripts/runtime/growware_openclaw_binding.py --json
```

Apply the binding and restart safely:

```bash
python3 scripts/runtime/growware_openclaw_binding.py --write --restart --json
```

Run the local deploy path:

```bash
python3 scripts/runtime/growware_local_deploy.py --json
```

## Current Boundaries

- Proactive `feishu6-chat` notifications still depend on OpenClaw host delivery plus an active conversation context
- `Telegram` remains a fallback candidate, not the primary ingress
- The deploy gate still defaults to explicit human approval
- Code changes and plugin deployment are automated only within the local OpenClaw environment
- Runtime intake and deploy verification should read compiled `.policy/` rather than prose docs or legacy policy JSON
