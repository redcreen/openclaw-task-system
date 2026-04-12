[English](README.md) | [中文](README.zh-CN.md)

# OpenClaw Task System

## What This Is

OpenClaw Task System adds a formal task runtime on top of OpenClaw.

It turns OpenClaw from "a chat that sometimes finishes work" into "a system that accepts, tracks, recovers, and closes work under one runtime-owned truth source".

Use it when your OpenClaw usage includes:

- work that takes time
- delayed replies or scheduled follow-up
- queueing, cancel, resume, or recovery
- restart-safe task continuity
- user-visible control-plane acknowledgements

## What `[wd]` Means

`[wd]` is the runtime-owned acknowledgement users see before the final answer.

It tells the user:

- the request was accepted
- a task was created or reused
- the request is now under managed task-system control

`[wd]` is not free-form chat text. It is the first visible control-plane receipt.

## Shipped Capability Map

Current shipped capabilities include:

- immediate runtime-owned `[wd]` acknowledgements and control-plane messages
- unified task registration, queue identity, and user-visible task state
- same-session follow-up routing across `steering / queueing / control-plane / collect-more`
- delayed reply and continuation tasks
- future-first planning with structured `main_user_content_mode`
- watchdog and continuity recovery flows
- planning anomaly projection and recovery hints in ops views
- operator surfaces such as `dashboard`, `triage`, `queues`, `lanes`, `continuity`, and `planning`
- short task CLI entrypoints for task and session lookup
- producer contract and channel acceptance truth sources

Same-session routing is part of the shipped runtime behavior:

- later messages in the same session can merge into the current task before start
- safe running-stage updates can trigger `interrupt-and-restart`
- clearly independent requests still queue as separate tasks
- every automatic routing decision returns a runtime-owned `[wd]` receipt

The main deliberate boundary remains:

- clear single-intent delayed replies are supported
- broader compound requests still require structured planning rather than larger regex or phrase lists

See:

- [`docs/compound_followup_boundary.md`](./docs/compound_followup_boundary.md)
- [`docs/llm_tool_task_planning.md`](./docs/llm_tool_task_planning.md)

## Project Status

The mainline roadmap is complete:

- Phase 0: complete
- Phase 1: complete
- Phase 2: complete
- Phase 3: complete
- Phase 4: complete
- Phase 5: complete
- Phase 6 minimum closure: complete

The remaining work is extension work, not unfinished mainline debt.

## Quick Start

Stable remote install:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/redcreen/openclaw-task-system/v0.1.0/scripts/install_remote.sh)
```

Latest main branch install:

```bash
OPENCLAW_TASK_SYSTEM_REF=main bash <(curl -fsSL https://raw.githubusercontent.com/redcreen/openclaw-task-system/main/scripts/install_remote.sh)
```

Pure OpenClaw install:

```bash
openclaw plugins install git+https://github.com/redcreen/openclaw-task-system.git#v0.1.0
```

## Documentation Map

Read in this order:

- [`docs/roadmap.md`](./docs/roadmap.md): main delivery line, milestones, and shipped boundaries
- [`docs/architecture.md`](./docs/architecture.md): runtime layers, truth sources, and contracts
- [`docs/test-plan.md`](./docs/test-plan.md): release gates and acceptance expectations
- [`docs/README.md`](./docs/README.md): documentation map and secondary entrypoints

Useful secondary docs:

- [`docs/plugin_installation.md`](./docs/plugin_installation.md): install paths, config, and install drift notes
- [`docs/usage_guide.md`](./docs/usage_guide.md): daily operations and runtime commands
- [`docs/testsuite.md`](./docs/testsuite.md): detailed automation and acceptance inventory
- [`docs/reference/session_message_routing/README.md`](./docs/reference/session_message_routing/README.md): shipped same-session routing contract
- [`docs/reference/README.md`](./docs/reference/README.md): durable reference notes
- [`docs/archive/README.md`](./docs/archive/README.md): historical records and superseded docs

## Runtime and Source Layout

- [`plugin/`](./plugin): installable OpenClaw plugin payload
- [`scripts/runtime/`](./scripts/runtime): the canonical editable runtime source tree
- [`plugin/scripts/runtime/`](./plugin/scripts/runtime): strict synchronized mirror used by the installable plugin payload
- [`config/`](./config): example runtime and plugin configuration

Canonical source rule:

- edit runtime code under [`scripts/runtime/`](./scripts/runtime)
- keep [`plugin/scripts/runtime/`](./plugin/scripts/runtime) synchronized through `python3 scripts/runtime/runtime_mirror.py --write`
- treat `runtime_mirror.py --check`, `plugin_doctor.py`, `scripts/install_remote.sh`, and `scripts/run_tests.sh` as the enforcement path for that rule

## Validation Entry Points

Full automated regression:

```bash
bash scripts/run_tests.sh
```

Stable acceptance:

```bash
python3 scripts/runtime/stable_acceptance.py --json
```

Same-session routing acceptance:

```bash
python3 scripts/runtime/same_session_routing_acceptance.py --json
```

Planning acceptance:

```bash
python3 scripts/runtime/planning_acceptance.py --json
python3 scripts/runtime/planning_acceptance_suite.py --json
```

Runtime mirror sync:

```bash
python3 scripts/runtime/runtime_mirror.py --check
python3 scripts/runtime/runtime_mirror.py --write
```
