# OpenClaw Task System Agent Guide

This repository is the source of truth for the `openclaw-task-system` runtime.

## Growware Pilot

- Treat this repository as `Project 1` for Growware.
- The durable project control surface lives under [`.growware/`](./.growware/).
- `feishu6-chat` is the human feedback / approval / notification channel.
- All runtime code changes happen in [`scripts/runtime/`](./scripts/runtime/), never in the installed extension directory.
- After changing runtime code, sync the plugin mirror with `python3 scripts/runtime/runtime_mirror.py --write`.

## Required Verification

Before claiming the task is done:

1. Run `python3 scripts/runtime/growware_preflight.py --json`
2. Run targeted tests for the files you changed
3. Run `python3 scripts/runtime/runtime_mirror.py --write`
4. Run `python3 scripts/runtime/plugin_doctor.py --json`
5. Run `python3 scripts/runtime/plugin_smoke.py --json`
6. If the change is meant to be locally deployed into OpenClaw, run `python3 scripts/runtime/growware_local_deploy.py --json`

## OpenClaw Binding

- The dedicated OpenClaw coding agent for this repo is `growware`.
- The binding source of truth is `.growware/channels.json`.
- Use `python3 scripts/runtime/growware_openclaw_binding.py --json` for preview.
- Use `python3 scripts/runtime/growware_openclaw_binding.py --write --restart --json` only after the preview and tests are clean.

## Safety Rules

- Do not edit `~/.openclaw/extensions/openclaw-task-system` directly.
- Do not bypass `.growware/` contracts when interpreting feedback or deciding deploy actions.
- Default to local-first verification before any host restart or plugin reinstall.
