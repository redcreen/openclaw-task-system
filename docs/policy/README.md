[English](README.md) | [中文](README.zh-CN.md)

# Policy Source

## Purpose

This directory is the human-readable policy source for the Growware pilot on `openclaw-task-system`.

The repo now uses a two-layer policy model:

- `docs/policy/*.md` is the human source of truth
- `.policy/` is the compiled machine execution layer

Growware, daemon, and terminal takeover should read `.policy/` at runtime.

## Current Policy Set

- [interaction-contracts.md](interaction-contracts.md): Growware feedback intake and same-session routing contract
- [verification-rules.md](verification-rules.md): project-local verification and deploy gate contract

## Compile and Validate

Compile or refresh the machine layer:

```bash
python3 scripts/runtime/growware_policy_sync.py --write --json
```

Validate without writing:

```bash
python3 scripts/runtime/growware_policy_sync.py --check --json
```

When policy docs change, refresh `.policy/` before relying on runtime intake or deploy behavior.
