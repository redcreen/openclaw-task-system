[English](README.md) | [中文](README.zh-CN.md)

# OpenClaw Task System

### what this is

OpenClaw Task System turns OpenClaw from "a chat that replies" into "a system that accepts, tracks, and completes tasks".

If your OpenClaw usage includes:

- requests that may take time
- delayed replies
- work that should survive restart
- queueing, cancel, resume, or recovery

then this plugin gives you that missing task layer.

### what `[wd]` means

`[wd]` is the immediate acknowledgement message users see before the final answer.

It means:

- the request was accepted
- the system created or attached to a task
- the task is now queued, running, paused, or otherwise managed

In other words, `[wd]` is the first visible "your work is now under task management" signal.

### what problem this solves

Without this task system, users often run into the same confusion:

- "Did OpenClaw actually receive my request?"
- "Is it still working, or did it get stuck?"
- "Why did a long task disappear after restart?"
- "Why do delayed replies, follow-up, and recovery all feel inconsistent?"

This project solves that by giving OpenClaw:

- immediate task acknowledgement with `[wd]`
- visible task state and queue state
- delayed reply / continuation support
- restart recovery for accepted-but-not-finished work
- one shared truth source for both users and operators

Just as important, this plugin is meant to supervise execution, not replace the original executor.

Its job is to:

- confirm the system received the work
- supervise progress until a result exists
- keep users informed when work is still running
- explain restart, recovery, timeout, or failure truthfully

In the current OpenClaw architecture, even simple requests normally still go through the original agent / LLM path.
This plugin is meant to supervise that path, not replace it.

### what you will see after installing it

After installation, the normal user-visible flow becomes:

1. you send a request
2. OpenClaw quickly replies with `[wd] ...`
3. the request is tracked as a task
4. if it takes longer, the system can send progress or follow-up
5. the task finishes with a final reply or a managed state such as `done`, `failed`, `blocked`, or `paused`

## Quick Start

If you already have OpenClaw and `python3`, the fastest stable install is:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/redcreen/openclaw-task-system/v0.1.0/scripts/install_remote.sh)
```

That command will:

- download the `v0.1.0` release bundle
- install the plugin into OpenClaw
- write a minimal plugin entry into `~/.openclaw/openclaw.json`
- run a post-install smoke check

For development installs from the latest main branch:

```bash
OPENCLAW_TASK_SYSTEM_REF=main bash <(curl -fsSL https://raw.githubusercontent.com/redcreen/openclaw-task-system/main/scripts/install_remote.sh)
```

If you prefer pure OpenClaw remote install without the helper script:

```bash
openclaw plugins install git+https://github.com/redcreen/openclaw-task-system.git#v0.1.0
```

### quick example

User sends:

```text
整理一下这批问题，然后给我一个最终结论
```

User first sees:

```text
[wd] 已收到，你的请求已进入队列；你现在排第 1 位。
```

Later, the user gets the final answer.

### what it does

Current shipped capabilities include:

- immediate `[wd]` acknowledgements and control-plane messages
- unified task registration, status, and queue identity
- delayed reply / continuation tasks
- watchdog and continuity recovery flows
- restart recovery for accepted-but-not-finished tasks
- unified user-facing status projection
- operator views such as `dashboard`, `triage`, `queues`, `lanes`, and `continuity`
- producer contract and channel acceptance truth sources

There is one important current boundary:

- clear single-intent delayed replies are supported
- compound requests like "do A now, then come back later" are not something regex growth can solve correctly forever

See:

- [`docs/compound_followup_boundary.md`](./docs/compound_followup_boundary.md)
- [`docs/llm_tool_task_planning.md`](./docs/llm_tool_task_planning.md)

### project status

The current mainline roadmap is complete.

- Phase 0: complete
- Phase 1: complete
- Phase 2: complete
- Phase 3: complete
- Phase 4: complete
- Phase 5: complete
- Phase 6 minimum closure: complete

The automated testsuite is also fully green.

One design boundary is intentionally recorded as open:

- broader compound-request planning beyond the minimum tool-assisted follow-up closure

See:

- [`docs/compound_followup_boundary.md`](./docs/compound_followup_boundary.md)
- [`docs/llm_tool_task_planning.md`](./docs/llm_tool_task_planning.md)

## Documentation Map

Start with these canonical docs:

- [`docs/roadmap.md`](./docs/roadmap.md): current delivery line, milestones, and boundaries
- [`docs/architecture.md`](./docs/architecture.md): runtime layers, truth sources, and contracts
- [`docs/test-plan.md`](./docs/test-plan.md): release gates and acceptance coverage
- [`docs/README.md`](./docs/README.md): documentation map and secondary references

Useful secondary references:

- [`docs/plugin_installation.md`](./docs/plugin_installation.md): install and configuration details
- [`docs/usage_guide.md`](./docs/usage_guide.md): operator commands and runtime workflows
- [`docs/testsuite.md`](./docs/testsuite.md): detailed test inventory
- [`docs/archive/README.md`](./docs/archive/README.md): historical planning, acceptance, and temporary notes

Runtime and source directories:

- [`plugin/`](./plugin): installable OpenClaw plugin payload
- [`scripts/runtime/`](./scripts/runtime): runtime tools, diagnostics, and acceptance helpers
- [`config/`](./config): example configs

### installation

#### prerequisites

- OpenClaw installed locally
- Python 3 available as `python3`

#### source tree vs installed plugin

- The source repository is where development happens.
- The installed plugin directory under `~/.openclaw/extensions/openclaw-task-system` is what OpenClaw actually loads at runtime.
- Runtime-generated state is expected to live under the installed plugin `data/` directory, not in the source repository.
- The installable payload is the `plugin/` directory. When changing plugin runtime payload files, keep the installable `plugin/` tree in sync before reinstalling or releasing.

#### 1. validate the plugin and runtime

If you are developing from source:

```bash
python3 scripts/runtime/plugin_doctor.py
python3 scripts/runtime/plugin_smoke.py
```

#### 2. install the plugin

Recommended stable release install:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/redcreen/openclaw-task-system/v0.1.0/scripts/install_remote.sh)
```

Development install from the latest main branch:

```bash
OPENCLAW_TASK_SYSTEM_REF=main bash <(curl -fsSL https://raw.githubusercontent.com/redcreen/openclaw-task-system/main/scripts/install_remote.sh)
```

Local source install:

```bash
openclaw plugins install ./plugin
```

Reinstall the plugin after changing the installable payload:

```bash
openclaw plugins install ./plugin
```

#### 3. prepare runtime config

The remote installer already writes a minimal working plugin entry into:

- `~/.openclaw/openclaw.json`

If you want to preview or rewrite that minimal entry from source:

```bash
python3 scripts/runtime/configure_openclaw_plugin.py
python3 scripts/runtime/configure_openclaw_plugin.py --write
```

If you want the full runtime config file, use:

- [`config/task_system.json`](./config/task_system.json)

or start from:

- [`config/task_system.example.json`](./config/task_system.example.json)

Example:

```json
{
  "taskSystem": {
    "enabled": true,
    "storageDir": "./data",
    "agents": {
      "main": {
        "enabled": true,
        "autoStart": true,
        "classification": {
          "minRequestLength": 24,
          "minReasonCount": 2,
          "estimatedStepsThreshold": 3
        },
        "planning": {
          "enabled": true,
          "mode": "tool-first-after-first-ack",
          "systemPromptContract": "You are the normal request executor. task-system runtime is the supervisor and the owner of the task truth source. ..."
        },
        "silenceMonitor": {
          "enabled": true,
          "silentTimeoutSeconds": 30,
          "resendIntervalSeconds": 30
        }
      }
    },
    "delivery": {
      "mode": "session-aware",
      "openclawBin": "openclaw",
      "autoExecuteInstructions": true,
      "retryFailedInstructions": false,
      "executionContext": "local"
    }
  }
}
```

`agents.main.planning.systemPromptContract` is user-editable. This is the prompt contract
that tells the LLM:

- the first `[wd]` is runtime-owned
- the fixed 30-second progress message is runtime-owned
- fallback and recovery control-plane messages are runtime-owned
- all other future-action planning should default to task-system tools

If you want to review or customize that contract, edit:

- [`config/task_system.json`](./config/task_system.json)
- or [`config/task_system.example.json`](./config/task_system.example.json)

#### 4. configure the plugin entry in OpenClaw

Start from:

- [`config/openclaw_plugin.example.json`](./config/openclaw_plugin.example.json)

Example:

```json
{
  "plugins": {
    "entries": {
      "openclaw-task-system": {
        "enabled": true,
        "config": {
          "enabled": true,
          "taskMessagePrefix": "[wd] ",
          "pythonBin": "python3",
          "defaultAgentId": "main",
          "registerOnBeforeDispatch": true,
          "sendImmediateAckOnRegister": true,
          "sendImmediateAckForShortTasks": true,
          "shortTaskFollowupTimeoutMs": 30000,
          "syncProgressOnMessageSending": true,
          "finalizeOnAgentEnd": true,
          "enableHostFeishuDelivery": true,
          "enableContinuationRunner": true,
          "enableWatchdogRecoveryRunner": true
        }
      }
    }
  }
}
```

The plugin can now use its bundled runtime/config by default. You only need to override
`runtimeRoot`, `configPath`, or `debugLogPath` when you want a non-default layout.

### how to use

#### if you are taking over this project fresh

Use this sequence:

1. read this `README.md` for scope, setup, and operator commands
2. read `docs/roadmap.md` for the official project state and next-phase boundaries
3. read `docs/architecture.md` for the producer / truth source / lane model
4. read `docs/testsuite.md` for pass criteria and validation layers
5. use `docs/usage_guide.md` for deeper operator workflows
6. use `docs/plugin_installation.md` for install and config details

When changing code:

1. edit source under the repository
2. keep the installable `plugin/` payload aligned
3. reinstall the plugin if the installed runtime payload changed
4. run `bash scripts/run_tests.sh`
5. verify with `python3 scripts/runtime/plugin_doctor.py`

#### normal user-facing behavior

When a request enters task management, the expected flow is:

1. register the task
2. send an immediate `[wd]`
3. start actual execution
4. sync user-visible progress when appropriate
5. finish as `done`, `failed`, `blocked`, `paused`, or recovered

#### common operator commands

Health and summary:

```bash
python3 scripts/runtime/main_ops.py health
python3 scripts/runtime/main_ops.py dashboard
python3 scripts/runtime/main_ops.py dashboard --json
python3 scripts/runtime/main_ops.py triage
python3 scripts/runtime/main_ops.py triage --json
```

Queue and lane views:

```bash
python3 scripts/runtime/main_ops.py queues
python3 scripts/runtime/main_ops.py queues --json
python3 scripts/runtime/main_ops.py lanes
python3 scripts/runtime/main_ops.py lanes --json
```

Continuity and recovery:

```bash
python3 scripts/runtime/main_ops.py continuity
python3 scripts/runtime/main_ops.py continuity --json
python3 scripts/runtime/main_ops.py continuity --auto-resume-if-safe --dry-run --json
python3 scripts/runtime/main_ops.py continuity --resume-watchdog-blocked --dry-run
```

Producer and channel contract:

```bash
python3 scripts/runtime/main_ops.py producer --json
python3 scripts/runtime/main_ops.py channel-acceptance --json
```

Task control:

```bash
python3 scripts/runtime/task_cli.py tasks
python3 scripts/runtime/task_cli.py task <task_id>
python3 scripts/runtime/task_cli.py session '<session_key>'
python3 scripts/runtime/main_ops.py list
python3 scripts/runtime/main_ops.py show <task_id>
python3 scripts/runtime/main_ops.py cancel --task-id <task_id>
python3 scripts/runtime/main_ops.py stop
python3 scripts/runtime/main_ops.py stop-all
python3 scripts/runtime/main_ops.py purge --session-key '<session_key>'
```

### channel status

Current accepted channel contracts:

- Feishu: `receive-side-producer`, validated
- Telegram: `dispatch-side-priority-only`, accepted with boundary
- WebChat: `dispatch-side-priority-only`, accepted with boundary

This means:

- Feishu has the strongest early control-plane path in the current boundary
- Telegram and WebChat are accepted under a dispatch-side contract, not full receive-side parity

### validation

Run the full automated testsuite:

```bash
bash scripts/run_tests.sh
```

Useful targeted checks:

```bash
python3 scripts/runtime/plugin_doctor.py --json
python3 scripts/runtime/plugin_smoke.py --json
python3 scripts/runtime/stable_acceptance.py --json
python3 scripts/runtime/main_ops.py dashboard --json
python3 scripts/runtime/main_ops.py channel-acceptance --json
```

### problems already solved

The current project already solves these core problems:

- delayed reply / continuation tasks are registered and completed as real tasks
- `[wd]`, follow-up, watchdog, continuity, and status views share one task truth source
- restart recovery works for accepted-but-not-finished tasks
- missed delayed replies are delivered after restart
- user-facing status is projected consistently across runtime views
- producer contract and channel acceptance are formalized in code, not only in prose

### similar systems and how this project differs

This project was informed by several adjacent systems, but it is not trying to become any of them.

| reference | what we borrowed | what we did not copy |
| --- | --- | --- |
| `humanlayer/agentcontrolplane` | control-plane should be a real layer | not turning this project into a distributed orchestrator |
| `hzxbzp/llama-agents` | queue, worker, and control-plane should have clear boundaries | not optimizing for general multi-agent orchestration first |
| `docker/cagent` | runtime modules should have explicit boundaries | not turning the project into a generic agent runtime product |
| GitHub Copilot steering / queueing | steering, queueing, control-plane, and reply are different message types | not treating product docs as a complete runtime architecture |

The practical conclusion is simple:

- this project is OpenClaw-native
- it is task-runtime first, not orchestrator first
- it treats control-plane messages such as `[wd]`, follow-up, watchdog, and recovery as product features, not as side effects

### boundaries

These boundaries are intentional:

- no changes to OpenClaw core
- no host code changes
- no modifications to other plugins as a project requirement
- all behavior is built through this repo's plugin, runtime, state, and docs

### roadmap after the mainline

The current mainline is complete. Future work is optional and should be treated as a new roadmap, not as unfinished mainline debt.

Candidate directions:

- stronger auto-recovery and auto-resume loops
- more complete receive-side producer support across channels
- richer user-facing control-plane views and bulk task operations
- Feishu queue and task queue boundary cleanup under the existing contract model
