# OpenClaw Task System

[English](#english) | [中文](#中文)

## English

### overview

OpenClaw Task System is a task runtime and control plane for OpenClaw.

It upgrades plain chat requests into managed tasks with:

- registration
- status
- queueing
- control-plane feedback
- recovery
- completion handling
- a shared truth source for both users and operators

In short, this project turns OpenClaw from a message-only flow into a message flow plus a task flow.

### what you get as a user

After installing it, OpenClaw stops behaving like a chat stream that sometimes "forgets" task state.
Instead, users get a predictable task experience:

- a request is acknowledged immediately with `[wd]`
- long tasks and delayed replies are tracked as real tasks
- queue position and wait state can be inspected instead of guessed
- restart recovery keeps accepted work from being silently lost
- watchdog, continuity, follow-up, cancel, and resume stop being ad-hoc behaviors

### what problem it solves

OpenClaw is naturally message-driven, but real usage needs task-driven behavior.

Without a task system, these problems appear quickly:

- users do not know whether the system actually received a request
- long tasks, delayed replies, and cross-turn work do not share one task object
- `[wd]`, follow-up, watchdog, continuity, cancel, and resume are treated like normal replies
- the same task shows different truths in different places
- different channels drift into different ad-hoc behavior

This project exists to provide one control plane for those concerns.

### quick start

If you want the shortest path to a working install:

1. verify the runtime

```bash
python3 scripts/runtime/plugin_doctor.py
python3 scripts/runtime/plugin_smoke.py
```

2. install the plugin

```bash
openclaw plugins install ./plugin
```

3. use the bundled defaults or copy from:

- [`./config/task_system.json`](./config/task_system.json)
- [`./config/openclaw_plugin.example.json`](./config/openclaw_plugin.example.json)

4. run a quick health check

```bash
python3 scripts/runtime/main_ops.py dashboard --json
python3 scripts/runtime/stable_acceptance.py --json
```

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

### project status

The current mainline roadmap is complete.

- Phase 0: complete
- Phase 1: complete
- Phase 2: complete
- Phase 3: complete
- Phase 4: complete
- Phase 5: complete

The automated testsuite is also fully green.

### what users will actually see

In normal use, the expected user-visible flow is:

1. a message is accepted into task management
2. the user sees an immediate `[wd]`
3. the task is queued or activated
4. follow-up or progress can appear if the task runs long enough
5. the task finishes as `done`, `failed`, `blocked`, `paused`, or recovered

This is the key shift:

- before: OpenClaw mainly exposed message flow
- after: OpenClaw exposes message flow plus task flow

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

```bash
python3 scripts/runtime/plugin_doctor.py
python3 scripts/runtime/plugin_smoke.py
```

#### 2. install the plugin

```bash
openclaw plugins install ./plugin
```

Reinstall the plugin after changing the installable payload:

```bash
openclaw plugins install ./plugin
```

#### 3. prepare runtime config

Use:

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
          "estimatedStepsThreshold": 3,
          "keywords": ["继续", "处理", "排查", "修复", "整理", "实现", "测试", "验证"]
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

### 项目概览

OpenClaw Task System 是 OpenClaw 之上的统一任务运行时和控制面。

它做的事情，不是单纯补几个 `[wd]` 或几个队列脚本，而是把原本只是聊天流里的请求，提升成真正可管理的任务流，具备：

- 登记
- 状态
- 排队
- 控制面反馈
- 恢复
- 收口
- 用户与运维共享的一份真相源

一句话说，这个项目是在把 OpenClaw 从“只有消息流”补成“消息流 + 任务流”。

### 用户实际会得到什么

装上以后，OpenClaw 不再像一个偶尔“忘记状态”的聊天流，而会更像一个稳定的任务系统：

- 用户发出请求后，会先收到 `[wd]`
- 长任务和延迟任务会作为真实 task 被跟踪
- 排队状态和等待状态可查看，不再只能靠猜
- 重启后，已接收但未完成的任务可以恢复
- watchdog、continuity、follow-up、cancel、resume 都进入统一控制面

### 这个项目解决什么问题

OpenClaw 天然更像消息驱动系统，但真实使用需要的是任务驱动行为。

如果没有 task system，很快就会出现这些问题：

- 用户发出消息后，不知道系统是否真的收到了
- 长任务、延迟任务、跨轮次任务没有统一任务对象
- `[wd]`、follow-up、watchdog、continuity、cancel、resume 被当成普通 reply 对待
- 同一任务在不同入口里显示的是不同真相
- 不同 channel 会逐渐长成不同的临时行为

所以这个项目要补的，不是某一个 feature，而是一层统一控制面。

### 快速开始

如果你只想最快装起来，走这 4 步：

1. 先做 runtime 自检

```bash
python3 scripts/runtime/plugin_doctor.py
python3 scripts/runtime/plugin_smoke.py
```

2. 安装插件

```bash
openclaw plugins install ./plugin
```

3. 直接使用默认配置，或者从下面两个文件开始：

- [./config/task_system.json](./config/task_system.json)
- [./config/openclaw_plugin.example.json](./config/openclaw_plugin.example.json)

4. 跑一轮最小健康检查

```bash
python3 scripts/runtime/main_ops.py dashboard --json
python3 scripts/runtime/stable_acceptance.py --json
```

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

### 当前状态

当前主线 roadmap 已全部完成：

- Phase 0：完成
- Phase 1：完成
- Phase 2：完成
- Phase 3：完成
- Phase 4：完成
- Phase 5：完成

完整自动化 testsuite 也已经全绿。

### 用户实际会看到什么

正常用户视角下，预期流程是：

1. 消息进入 task system 管理范围
2. 用户先看到一条 `[wd]`
3. 任务进入排队或激活
4. 如果任务较长，可能收到 follow-up 或进展同步
5. 最后以 `done / failed / blocked / paused / recovered` 等终态收口

这也是这个项目最核心的变化：

- 之前：OpenClaw 主要暴露消息流
- 现在：OpenClaw 同时暴露消息流 + 任务流

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

```bash
openclaw plugins install ./plugin
```

如果你修改了安装态 payload，需要重新安装一次插件：

```bash
openclaw plugins install ./plugin
```

#### 3. 准备 runtime 配置

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
          "estimatedStepsThreshold": 3,
          "keywords": ["继续", "处理", "排查", "修复", "整理", "实现", "测试", "验证"]
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
