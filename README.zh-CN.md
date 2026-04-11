[English](README.md) | [中文](README.zh-CN.md)

# OpenClaw Task System

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

在当前 OpenClaw 架构下，即使是简单请求，通常也还是会进入原来的 agent / LLM 路径。
这个插件的职责，是监督这条路径，而不是替代它。

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
- Phase 6 最小闭环：完成

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

`agents.main.planning.systemPromptContract` 现在是**用户可修改**的配置项。它用来明确告诉 LLM：

- 第一条 `[wd]` 归 runtime
- 固定的 30 秒进度消息归 runtime
- fallback / recovery 控制面文案归 runtime
- 其他 future-action planning 默认走 task-system tools

如果你要 review 或改写这段合同，直接编辑：

- [config/task_system.json](./config/task_system.json)
- 或 [config/task_system.example.json](./config/task_system.example.json)

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
python3 scripts/runtime/main_ops.py dashboard --only-issues
python3 scripts/runtime/main_ops.py planning
python3 scripts/runtime/main_ops.py planning --json
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
python3 scripts/runtime/check_task_user_content_leaks.py --json
python3 scripts/runtime/check_task_user_content_leaks.py --since 2026-04-11T12:18:34+08:00 --json
python3 scripts/runtime/scrub_task_user_content_history.py --json
python3 scripts/runtime/planning_acceptance.py --json
python3 scripts/runtime/create_planning_acceptance_record.py
python3 scripts/runtime/create_planning_acceptance_record.py --print-next-steps
python3 scripts/runtime/create_planning_acceptance_record.py --json
python3 scripts/runtime/prepare_planning_acceptance.py --json
python3 scripts/runtime/capture_planning_acceptance_artifacts.py --json
python3 scripts/runtime/run_planning_acceptance_bundle.py --json
python3 scripts/runtime/planning_acceptance_suite.py --json
python3 scripts/runtime/stable_acceptance.py --json
python3 scripts/runtime/main_ops.py planning --json
python3 scripts/runtime/main_ops.py plugin-install-drift --json
python3 scripts/runtime/main_ops.py dashboard --json
python3 scripts/runtime/main_ops.py dashboard --only-issues
python3 scripts/runtime/main_ops.py triage --json
python3 scripts/runtime/main_ops.py channel-acceptance --json
```

交接 / 提交整理参考：

- [`docs/planning_acceptance_handoff.md`](./docs/planning_acceptance_handoff.md)
- [`docs/planning_acceptance_commit_plan.md`](./docs/planning_acceptance_commit_plan.md)

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

## Documentation Map
- [Docs Home](docs/README.md)
- [Test Plan](docs/test-plan.md)

## Quick Start

See [docs/README.md](docs/README.md) for the full documentation map.
