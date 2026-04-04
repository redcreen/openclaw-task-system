# OpenClaw Task System

Language: [English](#english) | [中文](#中文)

## English

### Overview

OpenClaw Task System is a task-lifecycle layer for OpenClaw.
It turns raw chat requests into tracked tasks, keeps users updated with visible status messages, recovers interrupted work, and delivers delayed or resumed results back to the original channel.

The project exists for one reason:

`turn chat requests into recoverable, user-visible task flows`

### Why This Project Exists

Without a task layer, long-running or delayed tasks are easy to lose, duplicate, or leave without visible progress.
This system makes those flows explicit and recoverable.

It is designed to solve problems like:

- a user sends a request but cannot tell whether the system received it
- long tasks look “stuck” because no visible progress is returned
- delayed replies get lost, overlap, or finish incorrectly
- after an OpenClaw restart, interrupted tasks fail to return the final result

### What It Does

Current capabilities include:

- queueing incoming chat requests and replying with visible `[wd]` acknowledgements
- short-task follow-up messages when work is still in progress
- watchdog-based monitoring for long-running tasks
- delayed reply / continuation registration and delivery
- restart recovery for interrupted `main` tasks
- overdue delayed-reply catch-up after restart
- operator tooling for queues, lanes, continuity, dashboard, triage, and taskmonitor

### Project Status

- Project completion: about `99%+`
- Mainline status: usable end-to-end and already validated with real channel tests
- Remaining work is mostly:
  - deeper automation
  - productized operator experience
  - a few UX tail issues

#### Mainline Scenarios Already Validated

- `Delayed Reply / Continuation`
  - `1分钟后回复我111`
  - `2分钟后回复我222`
  - `3分钟后回复我333`
  Verified: independently registered, delivered on time, completed in order.

- `Restart Recovery for Running Main Tasks`
  - a normal `main` task that was already received but not finished
  - after OpenClaw restart, it is resumed automatically
  - the final result is sent back to the original channel
  - verified on `Feishu direct session`

- `Overdue Delayed Reply After Restart`
  - if OpenClaw is offline when a delayed reply becomes due, it is not sent immediately
  - after restart, the overdue continuation is detected and delivered
  - verified on `Feishu delayed reply`

#### Deferred Item

- `Feishu offline missed-message backfill`
  Deferred for now.
  Reason: current app permissions do not include `im:message.history:readonly`, so missed messages cannot be replayed reliably after downtime.

### Architecture

Current mainline:

1. Register incoming requests as visible tasks or continuations.
2. Send immediate `[wd]` acknowledgement when appropriate.
3. Track running work with queue state, watchdog, and follow-up logic.
4. Deliver delayed replies through continuation polling and due-time claiming.
5. Persist task state on disk so interrupted work can be recovered.
6. Resume interrupted `main` tasks after restart and route results back to the original channel.
7. Expose runtime/operator state through `dashboard`, `continuity`, `queues`, `lanes`, `triage`, and `taskmonitor`.

### Installation

This system lives as a local OpenClaw workspace project plus plugin.

Main plugin entry:

- `workspace/openclaw-task-system/plugin/index.ts`

Useful validation and runtime commands:

```bash
python3 workspace/openclaw-task-system/scripts/runtime/plugin_doctor.py
python3 workspace/openclaw-task-system/scripts/runtime/plugin_smoke.py
python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py dashboard
```

For OpenClaw gateway control:

```bash
openclaw gateway status
openclaw gateway restart
```

### Normal Usage

#### User-facing capabilities

- queue incoming chat requests and reply with visible `[wd]` acknowledgements
- keep users informed when a short task or long task is still in progress
- register delayed replies as continuations and deliver them when due
- track long-running tasks with watchdog-based progress and recovery logic
- recover after OpenClaw restart:
  - normal `main` running tasks
  - overdue delayed replies / continuations

#### Operator-facing capabilities

- `dashboard`
- `queues`
- `lanes`
- `continuity`
- `taskmonitor`
- `triage`

These entry points all support:

- human-readable text
- structured `--json`
- `primary_action`
- `runbook`
- `focus_session_key`
- `requires_action`

The `continuity / dashboard / triage` path also supports:

- `guarded auto-resume`
- `closure_state`
- `closure_complete`
- `next_followup_summary`
- `auto_resume_ready / auto_resume_safe_to_apply / auto_resume_blockers`

Typical day-to-day commands:

```bash
python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py dashboard --compact
python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --json
python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py queues --json
python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py lanes --json
```

### Validation

Recommended maintainer checks:

```bash
bash workspace/openclaw-task-system/scripts/run_tests.sh
python3 workspace/openclaw-task-system/scripts/runtime/plugin_doctor.py
python3 workspace/openclaw-task-system/scripts/runtime/plugin_smoke.py
python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py dashboard --json
python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --json
```

Mainline validations already passed in real usage:

- delayed reply ordering
- delayed reply delivery after restart
- normal running `main` task resume after restart
- final result delivery back to original Feishu channel

### Problems Already Solved

- delayed reply no longer stops after a single reminder
- multiple delayed replies no longer reuse the same old task
- continuations now deliver final output directly and only complete afterward
- `[wd]` acknowledgements are now per-task instead of overwriting each other
- the major false follow-up issue after final output has been fixed
- duplicate or mixed agent/task-system replies have been eliminated
- `ChatGPT Plus / Pro` profile mixing has been constrained
- running `main` tasks now survive restart and continue
- restarted tasks now deliver the final result back to the original channel

### Roadmap

The roadmap has shifted from “make the mainline work” to “make it more automatic and more productized”.

#### 1. Automation Deepening

- push recovery further after the first successful resume
- make final closure detection more automatic
- continue moving watchdog + long-task continuation from strong runbook guidance toward a more automatic loop

#### 2. Productization

- lower-friction daily entry points for `dashboard / taskmonitor / continuity`
- better control surfaces such as panels or lightweight widgets
- cleaner user-facing controls and status presentation

#### 3. UX Tail Work

- continue improving `[wd]` first-response latency
- the current bottleneck is now primarily channel delivery latency, not task-system local logic

## 中文

### 项目概览

OpenClaw Task System 是 OpenClaw 之上的任务生命周期层。
它把聊天请求转换成可跟踪任务，并负责：

- 任务登记
- 队列与可见状态回写
- watchdog 静默检测
- delayed reply / continuation
- 重启后的自动恢复
- 最终结果回原 channel

这个项目的核心目标只有一个：

`把聊天请求变成可恢复、可观察、可收口的任务流`

### 为什么要做这个项目

没有 task layer 时，长任务、延迟任务、被重启打断的任务，最容易出现这些问题：

- 用户发了消息，但不知道系统是否收到
- 长任务没有阶段性状态，体感像“卡住”
- 延迟回复会丢、会串、会假完成
- OpenClaw 重启后，任务断掉但用户收不到最终结果

这个系统的目标就是把这些流程显式化、可恢复、可观测。

### 当前能力

当前版本已经具备：

- 普通消息入队并返回 `[wd]` 状态回执
- 短任务超时 follow-up
- 长任务 watchdog 跟踪与恢复判断
- delayed reply / continuation 登记与到点发送
- `main` 普通任务的重启恢复
- 重启后 overdue delayed reply 补发
- queue / lane / continuity / dashboard / triage / taskmonitor 运维能力

### 项目状态

- 项目整体完成度：约 `99%+`
- 主线状态：已形成可用闭环，并已完成关键真实验收
- 当前重点已不再是“主链路能不能跑通”，而是：
  - 自动化继续深化
  - 产品化入口继续收口
  - 少量体验尾巴继续优化

#### 已验收通过的主线场景

- `Delayed Reply / Continuation`
  - `1分钟后回复我111`
  - `2分钟后回复我222`
  - `3分钟后回复我333`
  已完成真实验证：独立登记、到点发送、按顺序完成。

- `OpenClaw 重启后的恢复`
  - 已接收但未完成的普通 `main` 任务
  - OpenClaw 重启后会自动恢复、继续执行，并把最终结果回到原 channel
  - 已完成真实验证：`Feishu direct session`

- `关机期间错过到点的 delayed reply`
  - OpenClaw 关闭期间不会发送
  - 重启后会识别 overdue continuation，并补发最终回复
  - 已完成真实验证：`Feishu delayed reply`

#### 暂缓项

- `Feishu 离线期间新消息补收`
  当前暂缓，不作为当前主线继续推进。
  原因：当前缺少 `im:message.history:readonly`，无法可靠补拉 OpenClaw 关闭期间错过的历史消息。

### 架构思路

当前主链路是：

1. 把聊天请求登记为可见任务或 continuation。
2. 在合适的时候立即发送 `[wd]` 回执。
3. 用队列状态、watchdog、follow-up 持续跟踪执行进度。
4. 用 continuation runner 轮询并 claim 到点任务。
5. 把任务状态持久化到磁盘，保证重启后可恢复。
6. OpenClaw 重启后自动恢复被打断的 `main` 任务，并把结果回原 channel。
7. 通过 `dashboard / continuity / queues / lanes / triage / taskmonitor` 暴露运维状态。

### 安装方式

这个系统目前以本地 OpenClaw workspace + plugin 方式运行。

主要插件入口：

- `workspace/openclaw-task-system/plugin/index.ts`

常用自检和运行命令：

```bash
python3 workspace/openclaw-task-system/scripts/runtime/plugin_doctor.py
python3 workspace/openclaw-task-system/scripts/runtime/plugin_smoke.py
python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py dashboard
```

OpenClaw gateway 常用控制命令：

```bash
openclaw gateway status
openclaw gateway restart
```

### 日常使用

#### 用户侧能力

- 普通消息进入 task-system 队列并给出 `[wd]` 回执
- 短消息超过阈值时给出后续 follow-up 状态
- 长任务由 watchdog 持续跟踪、补状态、做恢复判断
- delayed reply 类消息登记为 continuation，并在到点后主动回复
- OpenClaw 重启后自动恢复：
  - 普通 `main` running 任务
  - 已到点或过点的 delayed reply

#### 运维与排障能力

- `dashboard`
- `queues`
- `lanes`
- `continuity`
- `taskmonitor`
- `triage`

这些入口现在都已支持：

- 文本输出
- 结构化 `--json`
- `primary_action`
- `runbook`
- `focus_session_key`
- `requires_action`

其中 continuity / dashboard / triage 这一条线，已经统一接入：

- `guarded auto-resume`
- `closure_state`
- `closure_complete`
- `next_followup_summary`
- `auto_resume_ready / auto_resume_safe_to_apply / auto_resume_blockers`

日常最常用命令：

```bash
python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py dashboard --compact
python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --json
python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py queues --json
python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py lanes --json
```

### 如何验证

推荐维护者验证方式：

```bash
bash workspace/openclaw-task-system/scripts/run_tests.sh
python3 workspace/openclaw-task-system/scripts/runtime/plugin_doctor.py
python3 workspace/openclaw-task-system/scripts/runtime/plugin_smoke.py
python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py dashboard --json
```

已经完成的真实主线验收包括：

- delayed reply 顺序正确
- delayed reply 在重启后可补发
- 普通 running `main` 任务在重启后可恢复
- 最终结果可回原 Feishu channel

### 已解决的核心问题

- `Delayed reply` 不再“提醒一次后就不继续”
- 连续 delayed reply 不再复用旧任务，不再互相覆盖
- continuation 到点后直接送达最终回复，并在成功后完成收口
- `[wd]` 已统一前缀并按 task 粒度发送，不再互相覆盖
- “正式结果已经发出后，又补一条仍在处理中”的主要误发问题已解决
- `agent` 与 task-system 的混乱双重回复已解决
- `ChatGPT Plus / Pro auth profile` 混用已收敛，`main` 已锁到指定 `Pro` profile
- `OpenClaw 重启后普通 running main 任务无法继续` 已解决
- `OpenClaw 重启后恢复结果未回原 channel` 已解决

### Roadmap

当前 roadmap 已从“主链路打通”切换到“自动化深化 + 产品化收尾”。

#### 1. 自动化深化

- 恢复后的进一步自动推进
- 恢复后的最终自动收口判定继续自动化
- watchdog 与长任务续跑策略继续从“强 runbook + guarded auto-resume”向更自动闭环推进

#### 2. 产品化收尾

- dashboard / taskmonitor / continuity 的更低心智负担入口
- 更适合日常使用的面板 / 小组件 / 控制入口
- 普通用户视角的提示与控制收口

#### 3. 体验尾巴

- `[wd]` 首响继续优化
- 当前瓶颈已定位主要在通道发送侧，尤其是 Telegram / Feishu 外发时延
- 不再是 task-system 本地热路径阻塞

## 定位

这个目录是独立系统根目录。

后续与“OpenClaw 可配置任务管理系统”相关的工作，默认都在这里完成：

- 系统文档
- 设计方案
- 验证方案
- 使用说明
- 开发任务拆解
- 脚本实现
- OpenClaw 插件实现
- 测试代码
- 配置样例
- 本系统运行数据目录约定

除非明确需要接入 OpenClaw 主配置或主程序入口，否则不再继续把新工作散落到其他目录。

## 目标

本系统是一个全新的任务管理系统项目。

它负责长任务的完整生命周期管理：

- 任务创建
- 任务状态管理
- 用户可见进展回写
- 静默检测
- 通知兜底
- 终态收口
- 后续恢复与续跑

## 目录规划

### `docs/`

系统文档统一放这里，包括：

- 总体方案
- 验证方案
- 使用说明
- 开发任务拆解
- 后续设计文档

当前文件：

- `docs/SYSTEM_PLAN.md`
- `docs/VALIDATION_PLAN.md`
- `docs/USAGE_GUIDE.md`
- `docs/IMPLEMENTATION_TASKS.md`
- `docs/OPENCLAW_INTEGRATION_PLAN.md`
- `docs/PLUGIN_INSTALLATION.md`

### `scripts/`

系统脚本与运行时实现统一放这里。

当前已有：

- `scripts/runtime/`
  当前任务运行时实现目录，后续状态管理、静默检测、通知、发送、归档等能力都在这里继续发展

- `plugin/`
  OpenClaw 插件目录。后续宿主接入默认优先通过插件完成，而不是修改 OpenClaw 主程序

当前核心模块包括：

- `scripts/runtime/task_state.py`
- `scripts/runtime/task_config.py`
- `scripts/runtime/task_policy.py`
- `scripts/runtime/main_task_adapter.py`
- `scripts/runtime/openclaw_bridge.py`
- `scripts/runtime/openclaw_hooks.py`
- `scripts/runtime/task_status.py`
- `scripts/runtime/silence_monitor.py`
- `plugin/src/plugin/index.ts`

当前关键说明文档还包括：

- `docs/OPENCLAW_INTEGRATION_PLAN.md`
- `docs/OPENCLAW_INTEGRATION_EXAMPLE.md`

当前插件默认支持的长任务交互节奏是：

- 所有消息先立即回复“已收到，开始处理”
- 短任务如果超过设定时间还没返回，会自动补一条“仍在处理中”
- 长任务如果 30 秒内还没有新的阶段结果，watchdog 自动补一条“仍在处理中”
- 像“5分钟后回复我ok”这类延迟续跑任务，会先登记成计划任务，到点后再由 continuation runner 主动继续执行
- 有真实阶段结果时继续回写，直到最终收口

### `tests/`

本系统的自动化测试统一放这里。

当前阶段可以为空，但后续所有新增测试应尽量收敛到这里，避免继续散落。

### `config/`

本系统自己的配置样例、配置 schema、接入示例统一放这里。

后续可放：

- 配置示例 json
- schema 文档
- OpenClaw 接入样例

当前文件：

- `config/task_system.json`
- `config/task_system.example.json`
- `config/openclaw_plugin.example.json`

### `data/`

本系统运行时的数据目录约定。

后续正式实现时，任务状态、归档、outbox、发送中间态等都应优先归入这里。

## 工作约定

后续在这个系统里推进时，默认遵循以下规则：

1. 新文档优先写到 `docs/`
2. 新脚本优先写到 `scripts/`
3. 新测试优先写到 `tests/`
4. 新配置样例优先写到 `config/`
5. 新运行数据路径优先设计在 `data/`
6. OpenClaw 集成优先走 `plugin/`，避免修改 OpenClaw 主程序
7. 除非确有必要，不再把本系统的新逻辑写回其他旧目录

## 当前阶段

当前阶段仍是“系统定义优先”：

1. 把系统要做什么定义清楚
2. 把验证与验收方案定义清楚
3. 把使用方式和接入方式定义清楚
4. 把开发任务拆成可独立执行的小任务
5. 然后再进入正式实现

## 当前入口

如果要继续推进，建议优先阅读：

1. `docs/SYSTEM_PLAN.md`
2. `docs/VALIDATION_PLAN.md`
3. `docs/USAGE_GUIDE.md`
4. `docs/IMPLEMENTATION_TASKS.md`

## 当前可直接执行的命令

- 运行测试：
  `bash workspace/openclaw-task-system/scripts/run_tests.sh`

- 查看某个任务状态：
  `python3 workspace/openclaw-task-system/scripts/runtime/task_status.py <task_id>`

- 查看当前进行中的任务：
  `python3 workspace/openclaw-task-system/scripts/runtime/task_status.py --list`

- 查看系统健康总览：
  `python3 workspace/openclaw-task-system/scripts/runtime/health_report.py`

- OpenClaw 插件入口：
  `workspace/openclaw-task-system/plugin/index.ts`

- 插件安装自检：
  `python3 workspace/openclaw-task-system/scripts/runtime/plugin_doctor.py`

- 插件联调 smoke：
  `python3 workspace/openclaw-task-system/scripts/runtime/plugin_smoke.py`

- 运行完整 watchdog 周期：
  `python3 workspace/openclaw-task-system/scripts/runtime/watchdog_cycle.py`

- dry-run 发送指令执行器：
  `python3 workspace/openclaw-task-system/scripts/runtime/instruction_executor.py`

- 真正执行可外发通道：
  `python3 workspace/openclaw-task-system/scripts/runtime/instruction_executor.py --execute`

- 给执行结果显式标记上下文：
  `python3 workspace/openclaw-task-system/scripts/runtime/instruction_executor.py --execute --execution-context host`

- 只跑 watchdog 产物生成，不做真实外发：
  `python3 workspace/openclaw-task-system/scripts/runtime/watchdog_cycle.py workspace/openclaw-task-system/config/task_system.json --no-execute`

- 让 watchdog 结果显式标记为宿主实发：
  `python3 workspace/openclaw-task-system/scripts/runtime/watchdog_cycle.py workspace/openclaw-task-system/config/task_system.json --execution-context host`

- 生成一条测试外发指令：
  `python3 workspace/openclaw-task-system/scripts/runtime/enqueue_test_instruction.py --channel telegram --chat-id @example --message "task system test"`

- 运行 `main` 第一阶段总验收：
  `python3 workspace/openclaw-task-system/scripts/runtime/main_acceptance.py`

- 运行稳定使用总验收：
  `python3 workspace/openclaw-task-system/scripts/runtime/stable_acceptance.py`

- `main` 运维入口：
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py list`

- 统一状态总览：
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py dashboard`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py dashboard --compact`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py dashboard --only-issues`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py dashboard --json`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py dashboard --session-key '<session_key>'`
  会把 `health / queues / lanes / continuity / taskmonitor` 收成一个统一入口
  `dashboard --json` 也会直接给出 `top_followup_session`，方便快速定位当前最该优先跟进的 session
  `dashboard` / `dashboard --compact` / `dashboard --json` 现在也会附带 `action_hint`，直接提示下一步更推荐先看什么
  `action_hint_command` 会直接给出首选命令，并排在 `suggested_next_commands` 的第一位
  `dashboard` 也会附带统一结构的 `primary_action`
  `dashboard` / `continuity` / `resume result` 也会直接给出顶层 `primary_action_kind / primary_action_command`
  `dashboard` / `continuity` / `resume result` 也会直接给出顶层 `runbook_status`
  `dashboard` / `continuity` / `resume result` 也会直接给出顶层 `requires_action`
  `dashboard` / `continuity` / `resume result` 也会直接给出顶层 `focus_session_key`
  `dashboard --only-issues --json` 的 `issue_summary` 现在也会给出同样的顶层别名字段
  `dashboard --json` 还会附带 `runbook`，把首选动作和后续命令收成一组可直接消费的步骤
  文本版 `dashboard` 现在也会渲染 `Runbook` 段落
  `dashboard --only-issues` 会只保留非 OK 项，更适合日常巡检

- 当前队列拓扑：
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py queues`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py queues --json`
  输出会显式标出当前哪些 session 正在共享同一个 agent queue
  并会解释为什么当前 queue 被判断为 `shared` / `single-session`
  同时会给出当前更适合的执行建议：`serial` / `serial-per-session` / `parallel-safe`

- 当前 lane 摘要：
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py lanes`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py lanes --json`
  输出会显式标出当前 lane 是 `shared` 还是 `single-session`
  并会标出当前共享 lane 中是否已经存在 running lane
  同时会给出当前更适合的执行建议：`serial` / `serial-per-session` / `parallel-safe`

- 当前持续执行 / watchdog 风险摘要：
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --session-key '<session_key>'`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --json`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --resume-watchdog-blocked --session-key '<session_key>' --limit 1`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --resume-watchdog-blocked --respect-execution-advice`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --resume-watchdog-blocked --dry-run`
  文本输出会把恢复结果按 `Needs Follow-up` / `Settled` 分组显示
  文本输出会额外给出 `Follow-up Priorities`，帮助先盯最值得关注的 session
  恢复结果会附带 `post_resume_summary`，用于快速确认恢复后任务是否已进入 `running/queued/...`
  `post_resume_summary.sessions` 会继续给出每个恢复 session 的后续状态摘要，减少恢复后再手动追查一轮
  `post_resume_summary` 还会标出哪些恢复 session 已经 `settled`、哪些仍然 `needs-followup`
  `post_resume_summary.closure_state` 会直接标出本次恢复整体是否已收口：`no-resume-targets / settled / needs-followup`
  恢复结果顶层和 `post_resume_summary` 也会直接给出布尔值 `closure_complete`
  恢复结果顶层也会直接给出 `closure_state / closure_hint`，方便脚本和面板直接消费
  `post_resume_summary` 也会直接给出 `closure_hint / closure_hint_command`，提示恢复后下一步最推荐先做什么
  恢复结果顶层和 `post_resume_summary` 都会附带统一结构的 `primary_action`
  恢复结果顶层和 `post_resume_summary.runbook` 都会把恢复后的首选动作和后续命令收成一组可直接消费的步骤
  如果恢复后仍需继续 follow-up，恢复结果还会直接附带 `next_followup_summary`
  这样恢复后就不必立刻再跑第二条 continuity 命令才能看到该 session 的风险快照
  文本版 `continuity --resume-watchdog-blocked` 也会渲染 `Runbook` 段落
  已完成真实验收：
  OpenClaw 重启后，`main` 下已接收但未完成的普通 running 主任务，会被启动恢复链路自动提升并恢复，继续执行后把最终结果回到原 channel（已验证 Feishu direct session）
  当前实现还包含一层启动恢复重试兜底：
  插件启动时立即跑一次 `startupRecovery`，并在 10 秒后补跑一次，降低插件/网关启动时序导致的漏恢复概率
  每个 resumed session 还会带 `followup_state_reason`，直接说明为什么当前被判成 settled 或 needs-followup
  `post_resume_summary.top_followup_session` 会直接给出当前最值得优先跟进的 session，方便脚本和面板直接消费
  `continuity` / `continuity --json` 也会直接给出 `top_risk_session`，方便先从风险最高的 session 开始排
  `continuity` / `continuity --json` 同样会附带统一结构的 `primary_action`
  `continuity` / `continuity --json` 现在也会附带 `runbook`
  `continuity --json` 现在也会直接给出 `auto_resume_ready / auto_resume_mode / auto_resume_preview_command / auto_resume_apply_command`
  当存在 auto-resumable 任务时，`continuity` 的默认 `primary_action` 会优先指向 `preview-auto-resume`
  当不存在额外 blocker 时，`continuity` 的默认 `primary_action` 会进一步升级成 `apply-auto-resume`
  `continuity --auto-resume-if-safe` 现在会在 `safe_to_apply=true` 时直接执行自动恢复，否则返回受保护的 `noop / skipped` 结果
  `dashboard` 在 continuity 风险场景下也会继承这条 `primary_action`，优先指向 guarded auto-resume 入口
  `continuity --auto-resume-if-safe --json` 也已直接提供顶层 `closure_complete / primary_action / runbook`
  `continuity --auto-resume-if-safe --json` 现在还会统一给出顶层 `closure_state / closure_hint / next_followup_summary`
  文本版 `continuity --auto-resume-if-safe` 现在也会渲染 `Next Follow-up / Suggested Commands / Runbook`
  插件现在也支持启动时与轮询式 `watchdog-auto-recover`，用于把重启后卡住的长任务推进到 guarded auto-resume 链路
  `dashboard --json` / `dashboard --json --only-issues` 现在也会直接给出 `auto_resume_ready / auto_resume_safe_to_apply / auto_resume_blockers / auto_resume_command`
  `dashboard --only-issues` 文本视图现在也会直接显示 `auto_resume_ready / auto_resume_safe_to_apply / auto_resume_command`
  `triage` 在识别到 watchdog-blocked 主任务且满足条件时，也会优先提示 guarded auto-resume，而不是裸 `resume task_id`
  文本输出和 JSON 输出都会附带推荐的下一步命令，方便继续检查对应 session 的连续执行状态
  同时会直接给出当前建议执行方式：`serial` / `serial-per-session` / `parallel-safe`
  并会附带一份 `execution_plan`，把 dry-run、尊重 advice、后续检查命令收成一份更像 runbook 的输出
  输出会分成：
  - `Auto-Resumable`
  - `Needs Manual Review`
  - `Not Recommended For Auto Resume`
  - `By Session`

- 恢复 watchdog 卡住的主任务：
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --resume-watchdog-blocked --limit 1`

- `main` 健康检查：
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py health`

- 查看或切换某个会话的 taskmonitor：
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py taskmonitor --session-key '<session_key>' --action status`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py taskmonitor --session-key '<session_key>' --action status --json`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py taskmonitor --session-key '<session_key>' --action off`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py taskmonitor --action list`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py taskmonitor --action list --json`

- 健康问题统一修复入口：
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py repair`

- 当前问题分诊入口：
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py triage`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py triage --json`
  `triage --json` 现在也会直接给出 `auto_resume_ready / auto_resume_safe_to_apply / auto_resume_blockers / auto_resume_command`

- 陈旧 blocked 任务批处理入口：
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py sweep`

- 失败指令收口入口：
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py resolve-failures`

- 外发故障诊断入口：
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py diagnose-delivery`

## 下一步建议

下一阶段建议直接在这个目录内继续推进：

1. 继续增强 `scripts/runtime/` 作为宿主无关核心
2. 继续增强 `plugin/` 作为 OpenClaw 插件接入层
3. 保持插件接入优先，不回退到修改 OpenClaw 主程序

从这一刻开始，这里应当被视为这个系统的唯一主工作区。
