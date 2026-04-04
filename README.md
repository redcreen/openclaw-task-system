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

## Repository Layout

This repository is the main working tree for the OpenClaw Task System.
System docs, runtime scripts, plugin code, tests, config samples, and runtime data conventions are all kept here.

推荐把这个目录视为 task-system 的唯一主工作区。
除非明确需要修改 OpenClaw 主配置或主程序入口，否则不要再把新逻辑分散到别的目录。

### Key Directories

- `docs/`
  - system plans
  - validation plans
  - usage guides
  - implementation tasks
  - integration and plugin installation notes
- `scripts/runtime/`
  - runtime logic, queue state, continuity, watchdog, health, and operator tools
- `plugin/`
  - OpenClaw plugin integration layer
- `tests/`
  - automated tests for runtime and plugin behavior
- `config/`
  - config samples and integration examples
- `data/`
  - runtime tasks, archives, debug logs, and operational state

### Core Runtime Modules

- `scripts/runtime/main_task_adapter.py`
- `scripts/runtime/openclaw_bridge.py`
- `scripts/runtime/openclaw_hooks.py`
- `scripts/runtime/task_status.py`
- `scripts/runtime/silence_monitor.py`
- `scripts/runtime/main_ops.py`
- `plugin/src/plugin/index.ts`

## Maintainer Notes

### Working Rules

1. Put new docs in `docs/`
2. Put runtime logic in `scripts/`
3. Put automated tests in `tests/`
4. Put config samples in `config/`
5. Keep runtime state in `data/`
6. Prefer OpenClaw plugin integration through `plugin/`
7. Avoid scattering new task-system logic into unrelated repos or old directories

### Recommended Reading Order

If you are continuing work on this system, read these first:

1. `docs/SYSTEM_PLAN.md`
2. `docs/VALIDATION_PLAN.md`
3. `docs/USAGE_GUIDE.md`
4. `docs/IMPLEMENTATION_TASKS.md`

## Operations Reference

### Test and Validation

- Run the full test suite:
  `bash workspace/openclaw-task-system/scripts/run_tests.sh`
- Plugin installation doctor:
  `python3 workspace/openclaw-task-system/scripts/runtime/plugin_doctor.py`
- Plugin smoke:
  `python3 workspace/openclaw-task-system/scripts/runtime/plugin_smoke.py`
- Mainline acceptance:
  `python3 workspace/openclaw-task-system/scripts/runtime/main_acceptance.py`
- Stable-usage acceptance:
  `python3 workspace/openclaw-task-system/scripts/runtime/stable_acceptance.py`

### Task and Health

- Task status:
  `python3 workspace/openclaw-task-system/scripts/runtime/task_status.py <task_id>`
- List active tasks:
  `python3 workspace/openclaw-task-system/scripts/runtime/task_status.py --list`
- System health:
  `python3 workspace/openclaw-task-system/scripts/runtime/health_report.py`
- Main health:
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py health`

### Dashboard and Queue Inspection

- Unified dashboard:
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py dashboard`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py dashboard --compact`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py dashboard --only-issues`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py dashboard --json`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py dashboard --session-key '<session_key>'`

- Queue topology:
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py queues`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py queues --json`

- Lane summary:
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py lanes`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py lanes --json`

### Continuity and Recovery

- Continuity summary:
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --session-key '<session_key>'`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --json`

- Resume watchdog-blocked tasks:
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --resume-watchdog-blocked --session-key '<session_key>' --limit 1`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --resume-watchdog-blocked --respect-execution-advice`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --resume-watchdog-blocked --dry-run`

- Guarded auto-resume:
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --auto-resume-if-safe --dry-run --json`

### Taskmonitor and Triage

- Taskmonitor:
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py taskmonitor --session-key '<session_key>' --action status`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py taskmonitor --session-key '<session_key>' --action status --json`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py taskmonitor --action list`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py taskmonitor --action list --json`

- Triage:
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py triage`
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py triage --json`

### Repair and Delivery Diagnostics

- Repair:
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py repair`
- Sweep stale blocked tasks:
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py sweep`
- Resolve failed instructions:
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py resolve-failures`
- Diagnose delivery:
  `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py diagnose-delivery`

### Other Runtime Utilities

- Run watchdog cycle:
  `python3 workspace/openclaw-task-system/scripts/runtime/watchdog_cycle.py`
- Instruction executor dry-run:
  `python3 workspace/openclaw-task-system/scripts/runtime/instruction_executor.py`
- Instruction executor with real sends:
  `python3 workspace/openclaw-task-system/scripts/runtime/instruction_executor.py --execute`
- Watchdog cycle without real sends:
  `python3 workspace/openclaw-task-system/scripts/runtime/watchdog_cycle.py workspace/openclaw-task-system/config/task_system.json --no-execute`
- Enqueue test instruction:
  `python3 workspace/openclaw-task-system/scripts/runtime/enqueue_test_instruction.py --channel telegram --chat-id @example --message "task system test"`

## Additional Notes

- The plugin layer remains the preferred OpenClaw integration point.
- Runtime logic should stay host-agnostic where possible.
- New task-system work should continue to land in this repository rather than unrelated legacy directories.
