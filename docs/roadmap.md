[English](roadmap.md) | [中文](roadmap.zh-CN.md)

# OpenClaw Task System Roadmap

> 最后更新：2026-04-11
> 角色：这是本项目的正式 roadmap。以后默认按这份 roadmap 推进；`docs/todo.md` 只作为临时记录和新增事项收集。

## 1. 项目是做什么的

`openclaw-task-system` 本质上是在给 OpenClaw 补一层“任务运行时 + 控制面”。

如果用一句话概括，这个项目要做的是：

> 把原本只是聊天流里的请求，提升成有状态、可排队、可恢复、可解释、对用户可见的任务流。

它不是单一功能插件，也不是只修某个 channel 的 `[wd]` 延迟。
它更像是 OpenClaw 上的一层统一任务基础设施，负责把下面这些原本分散的能力收回来：

- 消息到来后的任务登记与 admission
- `[wd]`、follow-up、watchdog、continuity 这类控制面消息
- 排队、开始、暂停、恢复、取消、失败、完成
- delayed reply / continuation 这类跨时间任务
- `/tasks`、`queues`、`dashboard` 这类用户视角与运维视角投影

所以这个项目存在的真正原因不是“加一个回执”，而是：

- OpenClaw 目前天然更像消息驱动系统
- 但用户感知和任务管理需要的是任务驱动系统

`openclaw-task-system` 要补上的，就是这层从“消息”到“任务”的运行时。

## 2. 主要解决什么问题

从已经做成的功能和接下来要做的事情反推，这个项目主要在解决 5 类根问题：

1. OpenClaw 里“消息”与“任务”是混在一起的
   - 用户发了一条消息，不代表系统里就有一个可管理的任务对象
   - 所以排队、继续执行、恢复、取消、终态都容易退化成临时行为

2. 用户视角缺少第一时间可见的控制面
   - 用户发出消息后，不知道系统是否真的收到了
   - `[wd]`、30 秒 follow-up、watchdog 提示、cancel/resume 结果，本质上都属于控制面
   - 但原本它们没有被当成独立、高优先级通道来对待

3. 长任务和跨轮次任务缺少统一真相源
   - delayed reply / continuation
   - restart recovery
   - watchdog / continuity
   - 这些能力如果没有统一 task truth source，就只能靠聊天记录和局部状态拼接

4. 同一任务在不同入口看到的是不同真相
   - `[wd]`
   - `/tasks`
   - `queues / lanes / dashboard`
   - watchdog / continuity

5. 多 channel 行为不一致
   - Feishu、Telegram 等 channel 的能力边界不同
   - 需要一套 channel-neutral contract，而不是继续堆 channel-specific 硬编码

换句话说，这个项目在做的，不是“聊天系统上的几个补丁”，而是：

> 给 OpenClaw 建一层统一的任务控制平面，让任务的创建、反馈、排队、恢复和收口都变成系统能力。

## 3. 北极星目标

最终目标固定为：

- `[wd]` 必须在用户视角第一时间可见
- 所有 task 管理消息都必须是最高优先级
- 控制面消息不能被普通 reply 排队
- 这件事必须适用于所有 channel

这里的控制面消息包括：

- 首条 `[wd]`
- 30 秒 follow-up / 进展同步
- queue position / 排队状态
- cancel / resume
- watchdog / continuity
- completed / failed / cancelled / paused
- `/tasks` 面向用户的状态投影

## 4. 总体思路怎么做

总体思路不是“继续补 if/else”，而是建立一条统一主链：

1. `receive-time producer`
   - 尽量在消息真正到达时拿到 arrival truth
   - 对能做到的 channel，前移到 receive 时刻
   - 对当前边界下做不到的 channel，先把 dispatch 后第一优先级链路做扎实

2. `control-plane lane`
   - 把 `[wd]`、follow-up、task 管理消息从普通 reply 里拆出来
   - 单独定义优先级、冲突规则、终态拦截规则

3. `task-system truth source`
   - 用统一的 queue identity、snapshot、admission、task status 作为真相源
   - 不让不同入口自己再各算一遍

4. `projection layer`
   - `[wd]`、`/tasks`、`queues`、`dashboard`、watchdog 文案都读同一份 truth source

一句话总结：

> 用统一任务真相源 + 高优先级控制面通道，逐步把用户第一时间可见反馈、任务管理和多 channel 一致性收回来。

## 4.1 重要约束：task-system 的主要职责是监督，不是替代执行

后续所有设计都应遵守这条约束：

- task-system 负责接单、控制面反馈、监督执行、恢复、投影状态
- 真正任务执行仍然在原有执行架构上完成
- task-system 的价值在于让聊天驱动任务变透明，而不是把自身做成新的执行中心

所以它最核心的职责是：

1. 告诉用户系统已经收到任务
2. 监督任务持续执行，直到拿到结果
3. 在用户空等时提供有价值的控制面信息
4. 在重启、恢复、超时、异常时，如实告诉用户发生了什么
5. 让用户和运维看到同一份透明状态，而不是黑盒

这也意味着：

- `[wd]`、follow-up、watchdog、continuity、dashboard、triage 是主职责
- 替 LLM 长期判断复杂复合语义，不是主职责
- 对复杂 follow-up 的长期方向，应该是：
  - LLM 做 planning
  - task-system 做监督、验证、持久化与兜底
- 鉴于当前 OpenClaw 连简单请求也默认会进入 agent / LLM，task-system 不应再额外演化成前置 simple/complex 主分类器
- tool 链路产生的内部调度状态，不应直接作为用户输出；它们必须先进入 task-system truth source，再由 runtime 统一投影成 `[wd]` 控制面消息或真正的后续业务结果

## 4.2 外部借鉴原则

这条 roadmap 不以“照搬现成 agent framework”为前提，而是只吸收那些真正对当前问题有帮助的设计原则。

对外部项目的正式对比见：

- [external_comparison.md](./external_comparison.md)

目前确定要吸收进本 roadmap 的借鉴点有 4 个：

1. `control-plane` 必须独立成层
   - 借鉴自 `agentcontrolplane`
   - 对应到本项目，就是 `[wd]`、follow-up、queue/cancel/resume/watchdog/continuity/terminal 都不能继续混在普通 reply 里

2. `queue / control plane / worker` 需要明确分工
   - 借鉴自 `llama-agents`
   - 对应到本项目，就是 `receive-time producer / control-plane lane / task execution` 三层边界要持续收紧

3. 用户追加消息需要正式的 `steering / queueing` 语义
   - 借鉴自 GitHub Copilot SDK 的 steering / queueing 设计
   - 对应到本项目，就是同一 session 的后续消息，不能继续只靠局部特判决定是插队、排队还是管理命令

4. 不把项目带偏成通用 orchestrator
   - 对 `agentcontrolplane / llama-agents / cagent` 的共同反向约束
   - 对应到本项目，就是始终优先解决：
     - receive-time ack
     - control-plane 优先级
     - channel queue 与 task queue 边界
     - 用户可见状态一致性

## 5. 实施边界

边界固定，不再反复摇摆：

- 只改本项目自身代码
- 不改 OpenClaw core
- 不改宿主代码
- 不改其它插件代码
- 只通过现有扩展点、本项目 plugin/runtime、以及本项目可控状态层工作

这意味着：

- 不走改宿主 dispatch / channel / queue 的路线
- 不走加 core 新 hook 的路线
- 不靠其它插件内部改造来“假装全 channel 已解决”

## 6. 验证机制

本项目的验证机制分 4 层：

### 6.1 自动化回归

- Python runtime / CLI 测试
- Node plugin 测试
- Plugin Doctor / Plugin Smoke
- `bash scripts/run_tests.sh` 作为全量回归入口

正式说明见：

- [testsuite.md](./testsuite.md)
- [compound_followup_boundary.md](./compound_followup_boundary.md)
- [llm_tool_task_planning.md](./llm_tool_task_planning.md)

### 6.2 协议与日志证据

- control-plane lane 的 `enqueued / passed / dropped / skipped / sent / error`
- blocker 元信息
- terminal phase
- audience / enqueue token / sequence

这层的目标是：

- 不只是“功能能跑”
- 还要能解释“为什么发了 / 为什么没发 / 被谁拦了 / 在哪一步失败了”

### 6.3 插件/运行时冒烟

- plugin smoke
- doctor / runtime wrapper / bridge side checks

### 6.4 真实或半真实通道验收

- Telegram / Feishu 等真实交互体验
- 核心看用户视角：
  - `[wd]` 是否第一时间可见
  - 控制面消息是否被普通回复堵住
  - 是否出现残留 / 重复 / 失序

## 7. 当前已知边界

有一类问题已经明确记录下来，不再假装它可以靠继续补规则彻底解决：

- 复合请求里的 delayed follow-up 语义
  - 例如：`先做 A，然后 5 分钟后回来继续`

正式说明见：

- [compound_followup_boundary.md](./compound_followup_boundary.md)
- [llm_tool_task_planning.md](./llm_tool_task_planning.md)

当前原则：

- clear single-intent delayed replies: shipped and supported
- simple compound follow-up phrases: design boundary / compatibility discussion only, not a silent runtime materialization path
- long-term solution: structured planning or tool-assisted task decomposition
- task-system should remain supervisor-first, not planner-first
- scheduling state should be projected only through runtime-owned `[wd]`
- future-first requests should default to control-plane-only immediate output unless structured planning explicitly asks for immediate business content
- scheduling confirmations must include a meaningful follow-up summary, not only a raw time delta

推荐设计稿见：

- [llm_tool_task_planning.md](./llm_tool_task_planning.md)

## 8. 正式 Roadmap

## Phase 0. 项目定义与边界固定

目标：

- 说清楚项目是什么
- 说清楚北极星目标
- 固定实施边界
- 明确“临时记录只是收集区，roadmap 才是正式主线”

状态：已完成

## Phase 1. 协议与真相源统一

目标：

- 把任务真相源和控制面协议先定稳

子步骤：

1. `QueueIdentity / queueKey` 统一
2. `PreRegisterSnapshot` 统一
3. `registerDecision / BridgeDecision` 对齐
4. `AdmissionState` 与用户状态语义拆开
5. `ControlPlaneMessage` 基础 schema、priority rules、delivery path、conflict rules 定义
6. runtime hook 开始输出结构化 control-plane payload

状态：大部分已完成

已完成结果：

- canonical queue identity / snapshot consumption 已落地
- runtime hook 已能吐结构化 control-plane payload
- plugin 已能消费多类结构化 payload

## Phase 2. 最小 control-plane lane / scheduler

目标：

- 让控制面消息开始真正独立于普通 reply
- 建立稳定的调度证据链

子步骤：

1. 建立最小 control-plane lane
2. 落基本优先级规则
3. 落 terminal / preempt / supersede 冲突规则
4. 统一 skip / drop / send / error 诊断字段
5. 统一 continuation / host delivery / fulfilled shortcut 诊断
6. 统一基础生命周期 entered 日志
7. 清点剩余裸日志出口，并继续收口

   - `7A` startup / watchdog lifecycle 语义统一
   - `7B` plugin 顶层 hook / gateway / load warn/info 出口分类
   - `7C` continuation / host delivery runner vocabulary 再统一
   - `7D` testsuite / docs 对齐并收口残留

状态：已完成

当前已完成：

- lane 已存在
- `p0/p1` 对 `p2/p3` 预抢占已落地
- 低优先级之间 supersede 已落地
- terminal 拦截已落地
- sent / skipped / error / adapter-unavailable 已统一到证据链
- continuation / host / fulfilled shortcut 已接入证据链
- 基础生命周期 `entered` 日志已开始统一

当前已补齐：

- `Phase 2 / Step 7`
- `Step 7A` 已完成
  - startup / watchdog recovery 的 kickoff / dispatch 事件已补齐为稳定 lifecycle 语义
- `Step 7B` 已完成
  - plugin 顶层 hook / gateway / load warn/info 出口已全部补 operator-visible 结构化字段
- `Step 7C` 已完成
  - continuation / host delivery runner 已补统一 `runner / lifecycleStage / deliveryPath / reason` 字段
- `Step 7D` 已完成
  - testsuite / docs 已同步对齐，完整自动化 testsuite 全绿

Phase 2 收口结论：

- control-plane lane 的优先级与冲突规则已经具备稳定证据链
- 关键控制面路径都能从结构化日志解释
- 剩余宿主 `api.logger` 文本已退到 operator-visible 辅助日志，不再是唯一真相来源
- 后续默认进入 `Phase 3`

Phase 2 退出条件：

- 关键控制面路径都能从日志完整解释
- 剩余裸日志出口很少，且都已明确分类
- control-plane lane 的优先级和冲突规则不再靠“猜”

## Phase 3. 统一用户状态投影

目标：

- 让用户侧和运维侧看到的是同一份状态真相

子步骤：

1. `/tasks` 读统一 truth source
2. `queues / lanes` 带统一 `user_facing_status`
3. `dashboard / continuity / watchdog` 带统一用户状态标签
4. follow-up / `[wd]` 文案继续往统一语义收

状态：已完成

已完成结果：

- `/tasks`、`task_status.py` 已统一输出稳定的用户状态投影
- `queues / lanes / dashboard / continuity / watchdog` 已统一读取同一份用户状态真相
- 统一状态不再只靠中文文案传递，已经补上稳定的：
  - `user_facing_status_code`
  - `user_facing_status`
  - `user_facing_status_family`
  - `user_facing_status_code_counts`
  - `user_facing_status_counts`
- follow-up / `[wd]` 已开始直接基于统一状态 code 判断，而不是继续写死中文标签比较

结论：

- 用户侧与运维侧已经能读到同一套状态投影
- `Phase 3` 不再作为当前默认主线残留
- 后续如果还要继续收口，只会放到 `Phase 4/5` 与 producer contract 结合后再做语义强化，而不是继续停在本阶段

## Phase 4. channel-neutral producer contract

目标：

- 建立可被不同 channel 复用的 producer contract

子步骤：

1. 明确 receive-time producer contract
2. 明确哪些 channel 在当前边界下能提供 receive-side producer
3. 明确哪些 channel 当前只能做到 dispatch 后第一优先级
4. 把 producer 和 consumer contract 真正对齐
5. 明确同一 session 中后续消息的 `steering / queueing / control-plane` 语义

状态：已完成

已完成结果：

- channel-neutral producer contract 已正式落成到代码与运维输出里
- 已明确当前边界下的 channel 能力矩阵：
  - `feishu`: `receive-side-producer`
  - `telegram / webchat`: `dispatch-side-priority-only`
- `dashboard / triage / producer` 已统一输出同一份 producer contract 真相
- producer 与 consumer 已通过同一套 `queue identity / pre-register snapshot / early ack` 语义对齐
- 同一 session 的 `steering / queueing / control-plane` 语义已固定成正式 contract：
  - `same-session-steering`
  - `agent-scoped-task-queue`
  - `highest-priority-lane`

这一阶段额外约束：

- 借鉴 GitHub Copilot SDK 的 steering / queueing 思路，但不照搬其产品语义
- 最终要形成适合本项目的正式 contract：
  - 哪些消息是 steering
  - 哪些消息是 queueing
  - 哪些消息只属于 control-plane

## Phase 5. 按 channel 落地与真实验收

目标：

- 逐 channel 逼近北极星目标

子步骤：

1. Feishu：继续闭合 receive-side early ack / pre-register / queue 语义
2. Telegram：在当前边界内继续把 dispatch 后第一优先级链路做满，并明确 receive-time 限制
3. 其它 channel：按 contract 评估接入能力
4. 做真实/半真实通道验收
5. 复盘各 channel 是否已经满足“control-plane 独立成层”的借鉴原则

状态：已完成

已完成结果：

- channel rollout / acceptance 已正式落成到代码与 acceptance 脚本里
- 已明确当前支持 channel 的正式验收结论：
  - `feishu`: 已按 `receive-side-producer` contract 落地并验收
  - `telegram / webchat`: 已按 `dispatch-side-priority-only` contract 落地并验收
- `channel-acceptance` 真相源已经与 producer contract 对齐，不再只靠文档口头说明
- `stable_acceptance` 已纳入 `channel-acceptance` 步骤，完整自动化 testsuite 会持续验证该矩阵没有退化
- 各 channel 的当前边界也已显式写入 acceptance 输出：
  - 哪些 channel 满足 receive-side contract
  - 哪些 channel 是 bounded dispatch-side contract

Phase 5 收口结论：

- “按 channel 落地” 已经不再只是 roadmap 意图，而是代码里的正式 truth source
- “真实验收” 在当前边界下已转化成稳定的 channel acceptance matrix + stable acceptance 脚本
- 后续如果还要继续提升，只属于未来 roadmap 的能力增强，不再阻塞当前主线收口

## 8. 当前进展总结

如果只看全局，不看细枝末节，当前状态可以概括成：

1. 项目的主问题、边界、协议和路线已经清楚
2. Phase 1 基本打底完成
3. Phase 2 已完成
4. Phase 3 已完成
5. Phase 4 已完成
6. Phase 5 已完成

## 9. 后续工作方式

从现在开始默认采用以下工作方式：

- 正式主线以本文件为准
- `docs/todo.md` 只作为临时记录
- 当明确要求“处理临时记录”时：
  1. 读取 `docs/todo.md`
  2. 提炼新增事项
  3. 合并回本 roadmap
  4. 再按 roadmap 顺序推进

也就是说：

- roadmap 负责“我们为什么做、做什么、先后顺序是什么”
- 临时记录负责“最近出现了什么、需要记下来什么”

## 10. 当前默认下一步

如果没有新的更高优先级指令，默认下一步是：

- 保持完整 testsuite 与 channel acceptance matrix 持续全绿
- 新增事项先进入 `docs/todo.md`
- 等新的正式主线成熟后，再合并回下一版 roadmap

## 11. 主线完成后的候选方向

当前 `Phase 0 ~ Phase 5` 已经完成。下面这些方向可以继续做，但它们都属于新一轮 roadmap 候选，而不是当前主线欠账：

1. 更强的 auto-recovery / auto-resume 闭环
   - 在现有 guarded auto-resume 与 continuity 基础上继续往更自动推进

2. 更多 channel 的 receive-side producer 支持
   - 在当前 `feishu validated / telegram-webchat accepted-with-boundary` 的基础上继续缩小边界差异

3. 更完整的用户控制面
   - 更强的 `/tasks`
   - 批量操作
   - 更丰富的 session / agent 视图

4. Feishu queue 与 task queue 边界继续收口
   - 在现有 contract 模型下继续减少 channel queue 对用户可见 control-plane 的影响

5. LLM-assisted task planning for compound follow-up
   - 用显式 task-system tools + runtime verification 处理复合 delayed follow-up
   - 设计稿见：
     - [llm_tool_task_planning.md](./llm_tool_task_planning.md)

## 12. Phase 6：LLM-assisted planning with supervisor-first runtime

状态：最小闭环已完成

当前已落地的最小闭环包括：

- planning tools 已接入：
  - `ts_create_followup_plan`
  - `ts_schedule_followup_from_plan`
  - `ts_attach_promise_guard`
  - `ts_finalize_planned_followup`
- tool-created follow-up plan 会落到 truth source，并能物化成真实 paused follow-up task
- finalize 已能稳定抓到 `promise-without-task`
- overdue planned follow-up 已有 continuation 侧自动化验证
- `planning health` / `promise-without-task` / overdue follow-up 已进入：
  - task status truth source
  - health report
  - dashboard / triage / continuity 投影
- installable payload 与本地 OpenClaw 安装态 runtime 的 drift 已进入：
  - `plugin_install_drift.py`
  - `main_ops.py plugin-install-drift`
  - `dashboard / dashboard --only-issues / triage` 投影
- 首条 `[wd]`、30 秒 follow-up、fallback / recovery 仍保持 runtime-owned

这一轮已经不再只是“实施准备”，而是最小可工作的 Phase 6 runtime 已经落地。

核心原则不变：

1. task-system 仍然是 supervisor-first
2. 第一条 `[wd]` 仍然由 runtime 负责
3. 30 秒进度消息仍然由 runtime 负责
4. fallback / recovery 文案仍然由 runtime 负责
5. 除上述控制面例外外，其余涉及 future-action planning 的部分默认走 tool-assisted planning
6. 不允许把 regex / 句式表 / 关键词过滤 / 文本清洗扩张成长期主方案

### 12.1 目标

Phase 6 要解决的是：

- 不再继续扩张 regex / stopgap 规则来猜复杂复合 delayed follow-up
- 让原 agent / LLM 继续理解请求
- 让 task-system 提供显式工具、监控、promise guard、truth source 与恢复机制
- 以最低成本，尽快把“工具化 planning + 运行时监督”先跑通一个最小闭环
- 明确拒绝走“先让模型说，再靠硬编码文本规则清洗”的方向
- 把“业务内容通道”和“调度状态通道”正式拆开

一句话总结：

> 第一条确认与固定控制面仍然由 runtime 兜底，其余 future-action planning 默认交给 tool path；task-system 负责监督、验证、持久化和恢复。

### 12.2 最小落地切片

为了低成本快速实现，这一轮不要试图一次做完整 planner，而是先落一个最小可工作的切片：

1. 保留现有：
   - 首条 `[wd]`
   - 30 秒 follow-up
   - fallback / recovery 提示
   都由 runtime 负责

2. 新增最小 planning tool 链路，只覆盖：
   - 创建 follow-up plan
   - 物化 follow-up task
   - promise guard

3. 只要求支持一种最小闭环：
   - 原 agent / LLM 在执行过程中决定创建 future action
   - 通过 task-system tool 建立真实 plan
   - finalize 时验证 plan 已物化
   - 到点后由 task-system continuation runner 执行

4. 先不尝试：
   - 复杂多阶段 planner
   - 全 channel 同时 rollout
   - 把所有 follow-up 文案都工具化

### 12.3 建议工作拆分

#### Step 6A. contract 固定

目标：

- 固定 tool contract
- 固定 absolute due time 语义
- 固定 promise guard 语义

输出：

- `followup_due_at` 成为权威字段
- “逾期也必须执行并告知用户” 成为固定 contract
- “未建 task 不得口头承诺 future action” 成为固定 contract

#### Step 6B. 最小 tool truth source

目标：

- 落最小工具接口与真相源字段

范围：

- `ts_create_followup_plan`
- `ts_schedule_followup_from_plan`
- `ts_attach_promise_guard`

输出：

- plan 能落盘
- plan 能被物化成 paused follow-up task
- guard 能在 finalize 阶段被校验

#### Step 6C. 最小监控闭环

目标：

- 先把最关键的 anomaly 看住

范围：

- planning health
- promise-without-task
- tool expectation guard
- overdue follow-up execution

输出：

- anomaly 能进入 truth source
- dashboard / triage / continuity 能看见
- 用户文案能如实说明 planning 超时、未建 task、逾期补执行

#### Step 6D. 最小接线

目标：

- 让原 agent / LLM 能走最小 tool path

范围：

- 首条 `[wd]` 仍由 runtime 处理
- 原 agent / LLM 执行主请求
- future-action planning 通过 tools 落 plan
- finalize / continuation runner 完成后半段闭环

输出：

- 一个最小真实路径可以跑通：
  - 用户请求
  - runtime `[wd]`
  - agent / LLM 正常执行
  - tool 建 plan
  - finalize 校验
  - continuation runner 到点执行

#### Step 6E. 最小真实验收

目标：

- 先验一个最关键用户价值，而不是一次性铺满

首要验收例子：

- `先做 A，再在明确绝对时间点或相对时间点后回来继续`

重点不看“模型回答多聪明”，而看：

- 有没有真实 task
- due time 是否落盘
- promise 是否被 guard
- 逾期后是否仍执行并如实告知

### 12.4 最小先跑通测试集

Phase 6 不应该一上来把全量 testsuite 都绑进来。

建议先定义一个最小 starter suite，只跑最关键闭环：

1. tool plan 能创建并落 truth source
2. plan 能被物化成 paused follow-up task
3. finalize 能抓住 promise-without-task
4. overdue follow-up 仍会执行
5. 首条 `[wd]`、30 秒 follow-up、fallback / recovery 仍保持 runtime-owned

等这 5 条稳定后，再把 coverage 扩到：

- 更多 channel
- 更多 planning anomaly
- 更多 UI / projection 输出

### 12.5 Phase 6 退出条件

只有同时满足下面几条，才能说 Phase 6 最小闭环成立：

1. 至少一条 tool-assisted future-action 路径在自动化测试里全绿
2. promise-without-task 有稳定 anomaly 证据链
3. overdue follow-up 有自动化验证
4. 首条 `[wd]`、30 秒 follow-up、fallback / recovery 仍然不依赖 LLM
5. roadmap、testsuite、architecture、planning design 文档都已同步

### 12.7 Local install observability

虽然当前 `openclaw plugins install ./plugin` 仍可能被 OpenClaw 的 dangerous-code 检测拦住，
但这条现实边界已经不再是“文档里提一下”的状态，而是正式进入运维视图：

- `plugin_install_drift.py --json` 是源码 payload 与本地安装态 runtime 的 truth source
- `dashboard --only-issues` 会直接显示 drift 计数
- `triage --json` 在没有更高优先级 blocked/planning 动作时，会把 install drift 升成主建议动作

这意味着：

- Phase 6 的最小闭环不再只覆盖 planning runtime 本身
- 也覆盖了“安装态是否真的跟上这轮 runtime 演进”的可观察性

### 12.6 Continuation lane constraints

For planned delayed follow-ups, the accepted runtime contract is now:

- continuation claiming is ordered by absolute `due_at`
- main-lane activity must not block due continuations
- one due continuation must not block another continuation in the same session
- the user-facing session context stays shared, but continuation scheduling uses task-system continuation-lane semantics rather than main-lane busy locks

## 13. 已交付子项目：same-session message routing

状态：已完成

这条已交付能力解决的是：

- 同一 session 内连续输入多条消息时
- 哪些应该并入当前 task
- 哪些应该单独排队
- 哪些应该等待后续消息补齐
- 哪些属于控制面

已明确避免的方向：

- 继续扩张 regex / phrase list
- 或把决定权交给主对话 LLM 自己顺手判断

当前已交付形态：

1. runtime 先按当前 task state 做快速判定
2. 只在歧义场景触发 runtime-owned structured LLM classifier
3. runtime 再结合执行阶段决定：
   - `merge-before-start`
   - `interrupt-and-restart`
   - `append-as-next-step`
   - `queue-as-new-task`
   - `enter-collecting-window`
4. 每一次自动判定都必须给用户返回 runtime-owned `[wd]` 回执，并简短说明原因

当前交付与验收入口：

- [session_message_routing/README.md](reference/session_message_routing/README.md)
- [session_message_routing/decision_contract.md](reference/session_message_routing/decision_contract.md)
- [session_message_routing/test_cases.md](reference/session_message_routing/test_cases.md)
- [session_message_routing/development_plan.md](reference/session_message_routing/development_plan.md)
- `python3 scripts/runtime/same_session_routing_acceptance.py --json`
- `python3 scripts/runtime/stable_acceptance.py --json`
