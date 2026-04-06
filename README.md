# OpenClaw Task System

[English](#english) | [中文](#中文)

## English

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

### what you will see after installing it

After installation, the normal user-visible flow becomes:

1. you send a request
2. OpenClaw quickly replies with `[wd] ...`
3. the request is tracked as a task
4. if it takes longer, the system can send progress or follow-up
5. the task finishes with a final reply or a managed state such as `done`, `failed`, `blocked`, or `paused`

### quick install

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

The automated testsuite is also fully green.

One design boundary is intentionally recorded as open:

- delayed follow-up inside compound requests

See:

- [`docs/compound_followup_boundary.md`](./docs/compound_followup_boundary.md)
- [`docs/llm_tool_task_planning.md`](./docs/llm_tool_task_planning.md)

### repository layout

- Read in this order when starting fresh:
  - `README.md`
  - `docs/roadmap.md`
  - `docs/architecture.md`
  - `docs/testsuite.md`
  - `docs/usage_guide.md`
  - `docs/plugin_installation.md`
- [`docs/roadmap.md`](./docs/roadmap.md): official roadmap
- [`docs/architecture.md`](./docs/architecture.md): architecture and design model
- [`docs/testsuite.md`](./docs/testsuite.md): test layers and validation rules
- [`docs/usage_guide.md`](./docs/usage_guide.md): extended usage notes
- [`docs/plugin_installation.md`](./docs/plugin_installation.md): plugin installation details
- [`docs/todo.md`](./docs/todo.md): temporary notes only, not the mainline
- [`plugin/`](./plugin): OpenClaw plugin
- [`scripts/runtime/`](./scripts/runtime): runtime tools, truth sources, and CLI
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

## 中文

### 这是什么

OpenClaw Task System 是给 OpenClaw 补上的一层正式 task runtime。

它解决的不是“多发一条提示消息”，而是把：

- “收到一条消息顺手处理一下”

变成：

- “系统正式接收、跟踪、恢复并收口一个任务”

如果你的 OpenClaw 使用里存在这些场景：

- 请求会跑一段时间
- 有延迟回复
- 重启后任务不能丢
- 想看排队、取消、恢复、状态

那这个项目就是补这层能力的。

### `[wd]` 是什么

`[wd]` 是用户在最终结果之前先看到的那条确认消息。

它表示：

- 请求已经被系统接住了
- 系统已经创建或接管了对应 task
- 这条请求现在处于排队、执行、暂停或其它受控状态

也就是说，`[wd]` 不是普通聊天文案，而是“这条活已经进入任务系统”的可见信号。

### 它解决什么问题

没有这层 task system 时，用户最常见的困惑就是：

- “系统到底有没有真正收到我的请求？”
- “它现在是在执行，还是卡住了？”
- “为什么一重启，长任务状态就说不清了？”
- “为什么延迟回复、follow-up、恢复这些行为都不稳定？”

这个项目就是为了解决这些问题。

它补上的核心能力包括：

- 可见确认
- queue identity
- 生命周期状态
- 控制面反馈
- 中断后的恢复
- 用户和运维共享的一份任务真相源

同样重要的一点是：这个插件的职责是**监工**，不是替代原来的执行者。

它最核心的工作是：

- 告诉用户系统已经收到这件事
- 监督后续执行直到有结果
- 在用户空等时持续给出有价值的信息
- 在重启、恢复、超时、异常时，如实解释发生了什么

一句话说，它让 OpenClaw 更像“能正式接活并把活做完的系统”，而不只是“偶尔能完成工作的聊天流”。

### 装上后用户会看到什么

安装后，正常用户视角下的流程会变成：

1. 用户发出请求
2. OpenClaw 很快先回一条 `[wd] ...`
3. 这条请求被正式当成 task 跟踪
4. 如果任务比较长，系统会继续发进展或 follow-up
5. 最后返回正式结果，或者以 `done / failed / blocked / paused` 等状态收口

### 快速安装

如果你已经装好 OpenClaw 和 `python3`，推荐直接用稳定版远程一键安装：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/redcreen/openclaw-task-system/v0.1.0/scripts/install_remote.sh)
```

这条命令会自动完成：

- 下载 `v0.1.0` 稳定版源码包
- 安装插件到 OpenClaw
- 写入一份最小可用的插件配置到 `~/.openclaw/openclaw.json`
- 跑一轮安装后 smoke 检查

如果你是开发用户，想直接安装主干最新版：

```bash
OPENCLAW_TASK_SYSTEM_REF=main bash <(curl -fsSL https://raw.githubusercontent.com/redcreen/openclaw-task-system/main/scripts/install_remote.sh)
```

如果你更喜欢纯 OpenClaw 的远程安装方式，也可以直接：

```bash
openclaw plugins install git+https://github.com/redcreen/openclaw-task-system.git#v0.1.0
```

### 快速使用示例

用户发：

```text
整理一下这批问题，然后给我一个最终结论
```

用户先看到：

```text
[wd] 已收到，你的请求已进入队列；你现在排第 1 位。
```

之后再收到正式结果。

### 当前能力

当前已经落成的能力包括：

- 首条 `[wd]` 与控制面消息
- 统一任务登记、状态与 queue identity
- delayed reply / continuation
- watchdog 与 continuity 恢复链路
- 已接收但未完成任务的重启恢复
- 统一用户状态投影
- `dashboard`、`triage`、`queues`、`lanes`、`continuity` 等运维视图
- producer contract 与 channel acceptance 真相源

还有一个需要明确记录的当前边界：

- 单一意图、表达清晰的延迟回复已经支持
- “先做 A，再过几分钟回来继续” 这类复合请求，不是靠不断补规则就能长期解决的问题

详见：

- [`docs/compound_followup_boundary.md`](./docs/compound_followup_boundary.md)
- [`docs/llm_tool_task_planning.md`](./docs/llm_tool_task_planning.md)

### 当前状态

当前主线 roadmap 已全部完成：

- Phase 0：完成
- Phase 1：完成
- Phase 2：完成
- Phase 3：完成
- Phase 4：完成
- Phase 5：完成

完整自动化 testsuite 也已经全绿。

同时有一个刻意保留为开放设计问题的边界：

- 复合请求里的 delayed follow-up 语义

详见：

- [`docs/compound_followup_boundary.md`](./docs/compound_followup_boundary.md)
- [`docs/llm_tool_task_planning.md`](./docs/llm_tool_task_planning.md)

### 仓库结构

- 如果是全新接手，建议按这个顺序阅读：
  - `README.md`
  - `docs/roadmap.md`
  - `docs/architecture.md`
  - `docs/testsuite.md`
  - `docs/usage_guide.md`
  - `docs/plugin_installation.md`
- [docs/roadmap.md](./docs/roadmap.md)：正式 roadmap
- [docs/architecture.md](./docs/architecture.md)：架构设计
- [docs/testsuite.md](./docs/testsuite.md)：测试体系
- [docs/usage_guide.md](./docs/usage_guide.md)：扩展使用说明
- [docs/plugin_installation.md](./docs/plugin_installation.md)：插件安装说明
- [docs/todo.md](./docs/todo.md)：临时记录，不是正式主线
- [plugin/](./plugin)：OpenClaw 插件
- [scripts/runtime/](./scripts/runtime)：运行时、truth source 与 CLI
- [config/](./config)：配置样例

### 安装方式

#### 前提

- 本机已安装 OpenClaw
- 本机可用 `python3`

#### 源码目录与安装目录

- 仓库源码目录是开发目录。
- `~/.openclaw/extensions/openclaw-task-system` 是 OpenClaw 实际加载的安装态插件目录。
- 运行时生成数据应落在安装态插件目录下的 `data/`，而不是源码仓库里。
- 真正用于安装和发布的是 `plugin/` 目录；如果你改了会进入安装包的 runtime/plugin 文件，安装前需要保持 `plugin/` 内容同步。

#### 1. 安装前自检

```bash
python3 scripts/runtime/plugin_doctor.py
python3 scripts/runtime/plugin_smoke.py
```

#### 2. 正式安装插件

推荐普通用户直接安装稳定版 tag：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/redcreen/openclaw-task-system/v0.1.0/scripts/install_remote.sh)
```

开发用户如果要安装主干最新版：

```bash
OPENCLAW_TASK_SYSTEM_REF=main bash <(curl -fsSL https://raw.githubusercontent.com/redcreen/openclaw-task-system/main/scripts/install_remote.sh)
```

如果你已经在源码目录里，也可以继续用本地正式安装方式：

```bash
openclaw plugins install ./plugin
```

如果你修改了安装态 payload，需要重新安装一次插件：

```bash
openclaw plugins install ./plugin
```

#### 3. 准备 runtime 配置

远程安装脚本会自动写入一份最小可用配置到：

- `~/.openclaw/openclaw.json`

如果你想先预览或重写这份最小配置：

```bash
python3 scripts/runtime/configure_openclaw_plugin.py
python3 scripts/runtime/configure_openclaw_plugin.py --write
```

可以直接使用：

- [config/task_system.json](./config/task_system.json)

或者从样例开始：

- [config/task_system.example.json](./config/task_system.example.json)

示例：

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

#### 4. 配置 OpenClaw 插件入口

从这里开始：

- [config/openclaw_plugin.example.json](./config/openclaw_plugin.example.json)

示例：

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

### 如何使用

#### 如果你是从零接手这个项目

建议按这个顺序：

1. 先读本 `README.md`，了解项目目标、安装、配置和常用命令
2. 再读 `docs/roadmap.md`，确认正式主线、已完成阶段和后续边界
3. 再读 `docs/architecture.md`，建立 producer / truth source / lane 的架构心智
4. 再读 `docs/testsuite.md`，确认 testsuite 入口和通过标准
5. 需要更深的运维细节时再看 `docs/usage_guide.md`
6. 只在安装和配置时再看 `docs/plugin_installation.md`

如果你要继续开发，建议流程是：

1. 在仓库源码里修改
2. 保持可安装的 `plugin/` payload 同步
3. 如果安装态 runtime 变了，就重新安装插件
4. 跑 `bash scripts/run_tests.sh`
5. 再跑 `python3 scripts/runtime/plugin_doctor.py`

#### 用户侧预期流程

当请求进入 task system 管理范围时，推荐和预期的流程是：

1. 任务登记
2. 首条 `[wd]`
3. 开始真实执行
4. 在合适时同步用户可见进展
5. 以 `done / failed / blocked / paused / recovered` 等终态收口

#### 常用运维命令

健康与总览：

```bash
python3 scripts/runtime/main_ops.py health
python3 scripts/runtime/main_ops.py dashboard
python3 scripts/runtime/main_ops.py dashboard --json
python3 scripts/runtime/main_ops.py triage
python3 scripts/runtime/main_ops.py triage --json
```

队列与 lane：

```bash
python3 scripts/runtime/main_ops.py queues
python3 scripts/runtime/main_ops.py queues --json
python3 scripts/runtime/main_ops.py lanes
python3 scripts/runtime/main_ops.py lanes --json
```

continuity 与恢复：

```bash
python3 scripts/runtime/main_ops.py continuity
python3 scripts/runtime/main_ops.py continuity --json
python3 scripts/runtime/main_ops.py continuity --auto-resume-if-safe --dry-run --json
python3 scripts/runtime/main_ops.py continuity --resume-watchdog-blocked --dry-run
```

producer 与 channel contract：

```bash
python3 scripts/runtime/main_ops.py producer --json
python3 scripts/runtime/main_ops.py channel-acceptance --json
```

任务控制：

```bash
python3 scripts/runtime/main_ops.py list
python3 scripts/runtime/main_ops.py show <task_id>
python3 scripts/runtime/main_ops.py cancel --task-id <task_id>
python3 scripts/runtime/main_ops.py stop
python3 scripts/runtime/main_ops.py stop-all
python3 scripts/runtime/main_ops.py purge --session-key '<session_key>'
```

### Channel 当前状态

当前正式接受的 channel contract：

- Feishu：`receive-side-producer`，已验证
- Telegram：`dispatch-side-priority-only`，带边界验收通过
- WebChat：`dispatch-side-priority-only`，带边界验收通过

这表示：

- Feishu 在当前边界下拥有最强的早期 control-plane 路径
- Telegram 和 WebChat 当前是 dispatch-side contract，不等于完全 receive-side 对齐

### 如何验证

运行完整自动化 testsuite：

```bash
bash scripts/run_tests.sh
```

常用定向检查：

```bash
python3 scripts/runtime/plugin_doctor.py --json
python3 scripts/runtime/plugin_smoke.py --json
python3 scripts/runtime/stable_acceptance.py --json
python3 scripts/runtime/main_ops.py dashboard --json
python3 scripts/runtime/main_ops.py channel-acceptance --json
```

### 已经解决的核心问题

当前项目已经解决了这些核心问题：

- delayed reply / continuation 已经是正式任务，不再是聊天层临时行为
- `[wd]`、follow-up、watchdog、continuity、状态视图共享同一份任务真相源
- 已接收但未完成任务支持重启恢复
- 关机期间错过的 delayed reply 到点后，启动可以补发
- 用户侧与运维侧状态已经统一投影
- producer contract 与 channel acceptance 已经正式落成到代码，不再只靠文档口头说明

### 相近系统与差异

这个项目不是凭空设计出来的，前面参考过几类相近系统，但目标并不是把它做成那些系统中的任何一个。

| 参考对象 | 借鉴了什么 | 没有照搬什么 |
| --- | --- | --- |
| `humanlayer/agentcontrolplane` | control-plane 必须独立成层 | 不把项目带偏成分布式 orchestrator |
| `hzxbzp/llama-agents` | queue、worker、control-plane 要有清晰边界 | 不先把重点放成通用多 agent 编排框架 |
| `docker/cagent` | runtime 组件边界应该明确 | 不把项目做成通用 agent runtime 产品 |
| GitHub Copilot steering / queueing | steering、queueing、control-plane、reply 是不同消息类型 | 不把产品文档当成完整 runtime 架构 |

最后落到本项目上的结论很简单：

- 这是一个 OpenClaw-native 的系统
- 它首先是 task runtime，不是 orchestrator
- `[wd]`、follow-up、watchdog、恢复这些控制面消息，本身就是正式产品能力，不是附属副作用

### 边界说明

以下边界是刻意保持的：

- 不修改 OpenClaw core
- 不修改宿主代码
- 不把“修改其他插件代码”当成项目前提
- 所有能力都通过本仓库的 plugin、runtime、state 与 docs 落地

### 主线完成后的 roadmap 候选

当前主线已经完成。后续工作如果继续做，应视为新 roadmap，而不是旧主线欠账。

候选方向包括：

- 更强的 auto-recovery 与 auto-resume 闭环
- 更多 channel 的 receive-side producer 支持
- 更完整的用户控制面、批量操作与更强的任务视图
- 在现有 contract 模型下继续清理 Feishu queue 与 task queue 的边界
- 用 LLM-assisted task planning 处理复合 delayed follow-up
