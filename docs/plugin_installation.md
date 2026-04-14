[English](plugin_installation.md) | [中文](plugin_installation.zh-CN.md)

# Plugin Installation Guide

This guide covers:

- install prerequisites
- plugin install paths
- minimal OpenClaw configuration
- post-install validation

For project scope and shipped boundaries, see:

- [../README.md](../README.md)
- [roadmap.md](roadmap.md)
- [archive/local_install_validation_2026-04-09.md](archive/local_install_validation_2026-04-09.md)

## Prerequisites

You should already have:

- OpenClaw installed
- `python3` available locally
- consistent source payload under `plugin/`, `scripts/runtime/`, and `config/`
- `scripts/runtime/` treated as the canonical runtime source, with `plugin/scripts/runtime/` as the install mirror

## Install Options

Stable remote install:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/redcreen/openclaw-task-system/v0.2.0/scripts/install_remote.sh)
```

Latest main branch install:

```bash
OPENCLAW_TASK_SYSTEM_REF=main bash <(curl -fsSL https://raw.githubusercontent.com/redcreen/openclaw-task-system/main/scripts/install_remote.sh)
```

Pure OpenClaw install:

```bash
openclaw plugins install git+https://github.com/redcreen/openclaw-task-system.git#v0.2.0
```

Local source install:

```bash
openclaw plugins install ./plugin
```

## Current Local Install Boundary

There is a practical local-install boundary in current OpenClaw builds:

- this plugin runtime invokes Python hooks through `child_process.spawn(...)`
- OpenClaw 2026.4.2 may classify that as a dangerous code pattern
- even with force flags, local reinstall may still be rejected

Treat `openclaw plugins install ./plugin` as conditional rather than guaranteed.

When local install is blocked, the current recommended approach is:

1. keep the installable `plugin/` payload correct
2. validate from source with `plugin_doctor.py`, `plugin_smoke.py`, and `stable_acceptance.py`
3. use install-drift visibility to confirm whether source and installed runtime have diverged

## Pre-Install Checks

```bash
python3 scripts/runtime/growware_policy_sync.py --check --json
python3 scripts/runtime/runtime_mirror.py --check
python3 scripts/runtime/plugin_doctor.py
python3 scripts/runtime/plugin_smoke.py
```

Machine-readable output:

```bash
python3 scripts/runtime/plugin_doctor.py --json
python3 scripts/runtime/plugin_smoke.py --json
```

## Minimal Configuration

The remote installer writes a minimal plugin entry into:

- `~/.openclaw/openclaw.json`

To preview or rewrite that minimal entry:

```bash
python3 scripts/runtime/configure_openclaw_plugin.py
python3 scripts/runtime/configure_openclaw_plugin.py --write
```

The most common runtime config sources are:

- [`../config/task_system.json`](../config/task_system.json)
- [`../config/task_system.example.json`](../config/task_system.example.json)
- [`../config/openclaw_plugin.example.json`](../config/openclaw_plugin.example.json)

## Post-Install Validation

Recommended order:

1. `growware_policy_sync.py`
2. `plugin_doctor.py`
3. `plugin_smoke.py`
4. `main_ops.py dashboard --json`
5. `stable_acceptance.py --json`
6. `release_gate.py --json` for broader release-facing verification
7. `planning_acceptance_suite.py --json` when planning behavior changed
8. `planning_acceptance_suite.py --dry-run --json` when you want to rehearse the planning evidence flow without writing repo docs

Example:

```bash
python3 scripts/runtime/main_ops.py dashboard --json
python3 scripts/runtime/stable_acceptance.py --json
python3 scripts/runtime/release_gate.py --json
python3 scripts/runtime/planning_acceptance_suite.py --json
python3 scripts/runtime/main_ops.py plugin-install-drift --json
```

## Install Drift Visibility

To confirm whether source and installed runtime have diverged:

```bash
python3 scripts/runtime/main_ops.py dashboard --only-issues
python3 scripts/runtime/main_ops.py triage --json
python3 scripts/runtime/main_ops.py plugin-install-drift --json
```

`dashboard` and `triage` now project install drift directly rather than leaving it as a hidden standalone script concern.

## Source and Install Ownership

Current ownership is:

- `scripts/runtime/`: canonical runtime source
- `plugin/scripts/runtime/`: install mirror bundled into the plugin payload
- local installed runtime: deployed copy under the OpenClaw extensions directory

When runtime code changes, validate the repo mirror before packaging or running the full testsuite:

```bash
python3 scripts/runtime/runtime_mirror.py --check
```
