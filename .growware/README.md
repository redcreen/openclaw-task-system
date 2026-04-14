# Growware Control Surface

This directory is the durable project-local control surface for the Growware pilot on `openclaw-task-system`.

Tracked in Git:

- `project.json`
- `channels.json`
- `contracts/`
- `ops/`

Not tracked in Git:

- `runtime/`
- `logs/`

Current default:

- `Project 1 = openclaw-task-system`
- `A channel = feishu6-chat`
- `A roles = feedback + approval + notification`
- `Telegram = fallback candidate`
- `docs/policy/` is the human policy source for project-local intake and verification rules
- `.policy/` is the compiled machine execution layer for Growware, daemon, and terminal takeover
- `.growware/contracts/` and `.growware/ops/` remain the durable project-local control surface around that policy layer
- legacy `.growware/policies/*.json` has been retired from the live control surface; runtime and validation now read only the compiled `.policy/` layer
