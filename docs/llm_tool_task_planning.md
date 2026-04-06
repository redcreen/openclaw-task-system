# LLM-assisted task planning and follow-up tools

[English](#english) | [中文](#中文)

## English

> Status: design draft
> Scope: compound requests, delayed follow-up planning, and tool-assisted task decomposition

### problem

Some user requests contain more than one task intent in a single message:

- do something now
- then come back later
- maybe come back only after the first part finishes

Examples:

- `你先查一下天气，然后5分钟后回复我信息`
- `先整理这个问题，10分钟后再提醒我看结果`
- `先跑一轮检查，半小时后回来告诉我是否还报错`

Regex can catch some low-ambiguity phrases, but it is not the right long-term mechanism for this class of request.

### goals

This design should:

1. keep the current fast control-plane path intact
2. avoid turning every user request into an LLM planning round
3. let the LLM explicitly create structured follow-up tasks when needed
4. detect cases where the LLM promised a future action but failed to schedule one
5. preserve the task-system runtime as the final source of truth

### non-goals

This design should not:

1. move `[wd]` generation into the LLM
2. make every request depend on tool calls before the first acknowledgement
3. trust free-form model output as proof that a delayed task exists
4. replace deterministic delayed-reply parsing for simple, low-risk phrases

### recommended model: hybrid, not tool-only

The recommended direction is a hybrid model:

1. deterministic runtime fast path
2. tool-assisted planning path
3. runtime verification and fallback

That is better than either extreme:

- regex-only growth is too brittle
- LLM-only task creation is too unreliable

### why `[wd]` must stay outside the LLM

`[wd]` is a control-plane acknowledgement, not a planning artifact.

It must stay outside the LLM because:

1. it must remain first-visible and low-latency
2. it must not wait for model planning or tool latency
3. it must still work if the model times out or skips tool calls

So the order should remain:

```text
message received
  -> register / pre-register
  -> send [wd]
  -> choose execution path
       - deterministic runtime fast path
       - or LLM-assisted planning path
```

### when the LLM should be involved

The LLM should only be involved when the runtime detects that the message is likely compound or ambiguous.

Suggested routing rule:

- keep deterministic handling for:
  - simple immediate tasks
  - simple single-intent delayed replies
- invoke LLM planning for:
  - immediate work + delayed follow-up
  - dependent follow-up after prior work
  - multi-step requests where delayed intent is plausible but not exact

In short:

```text
simple request -> runtime handles directly
compound or ambiguous request -> runtime asks LLM to plan with tools
```

### proposed tools

The LLM should not directly mutate raw task files. It should call explicit task-system tools.

#### tool: `ts_get_task_planning_context`

Purpose:

- fetch the task/session context the planner needs

Input:

```json
{
  "session_key": "agent:main:feishu:direct:...",
  "message_text": "你先查一下天气，然后5分钟后回复我信息"
}
```

Output:

```json
{
  "session_key": "agent:main:feishu:direct:...",
  "agent_id": "main",
  "channel": "feishu",
  "current_queue_state": {
    "position": 2,
    "active_task_id": "task_abc"
  },
  "message_text": "你先查一下天气，然后5分钟后回复我信息"
}
```

#### tool: `ts_create_followup_plan`

Purpose:

- record a structured plan for compound requests

Input:

```json
{
  "source_task_id": "task_main_123",
  "immediate_work": "查一下天气",
  "followup_kind": "delayed-reply",
  "followup_delay_seconds": 300,
  "followup_message": "回来继续汇报天气结果",
  "dependency": "after-source-task-finalized"
}
```

Output:

```json
{
  "plan_id": "plan_xyz",
  "source_task_id": "task_main_123",
  "accepted": true,
  "runtime_contract": {
    "followup_kind": "delayed-reply",
    "dependency": "after-source-task-finalized"
  }
}
```

#### tool: `ts_schedule_followup_from_plan`

Purpose:

- turn a saved plan into a real scheduled follow-up task

Input:

```json
{
  "plan_id": "plan_xyz"
}
```

Output:

```json
{
  "task_id": "task_followup_456",
  "status": "paused",
  "due_at": "2026-04-06T11:30:00+08:00",
  "scheduled": true
}
```

#### tool: `ts_attach_promise_guard`

Purpose:

- tell the runtime that the model intends to promise a future action
- create an explicit guard expectation even before scheduling completes

Input:

```json
{
  "source_task_id": "task_main_123",
  "promise_type": "delayed-followup",
  "expected_by_finalize": true
}
```

Output:

```json
{
  "guard_id": "guard_789",
  "armed": true
}
```

#### tool: `ts_finalize_planned_followup`

Purpose:

- confirm that the planned follow-up has actually been materialized

Input:

```json
{
  "source_task_id": "task_main_123",
  "guard_id": "guard_789",
  "followup_task_id": "task_followup_456"
}
```

Output:

```json
{
  "ok": true,
  "promise_fulfilled": true
}
```

### what the LLM prompt should require

The model needs explicit rules. Without them, tool availability alone is not enough.

Suggested prompt additions:

1. if the request contains only immediate work, do not create delayed follow-up tasks
2. if the request clearly asks for delayed follow-up, create a real follow-up plan or task through the task-system tools
3. never promise a future reply in natural language unless a corresponding task-system tool call succeeded
4. if the user request is ambiguous, ask a clarification question rather than silently guessing a delayed follow-up
5. if tool scheduling fails, say so explicitly instead of pretending the future follow-up exists

The most important hard rule:

> Do not say "I will come back in 5 minutes" unless the runtime has accepted a real scheduled follow-up.

### monitoring and fallback

The runtime must assume the LLM may:

- time out
- skip the tool
- choose the wrong tool
- promise future work in plain text without creating a scheduled task

So monitoring must exist even if tools are available.

#### monitor 1: promise-without-task detector

At finalize time, check:

- did the model output contain a delayed promise?
- is there a matching follow-up plan or task?

If not:

- mark the task with a planning anomaly
- emit operator-visible diagnostics
- surface it in dashboard / triage / continuity

#### monitor 2: tool expectation guard

If the LLM called `ts_attach_promise_guard`, then finalize must verify:

- guard exists
- follow-up plan or task was created
- guard was closed

If not:

- finalize as `done-with-planning-anomaly` or similar projected status
- emit a watchdog-visible signal

#### monitor 3: fallback runtime scheduling

For low-risk, high-confidence cases, the runtime can still schedule the follow-up directly even if the LLM path is unavailable.

This preserves the current safety net:

- deterministic parsing remains the backup path
- the LLM tool path becomes the structured path

### recommended runtime sequence

```text
user message
  -> register / [wd]
  -> runtime classifies:
       - simple immediate task
       - simple delayed reply
       - compound or ambiguous
  -> if simple immediate:
       run now
  -> if simple delayed:
       schedule directly
  -> if compound or ambiguous:
       ask LLM planner
         -> create follow-up plan
         -> arm promise guard
  -> source task runs
  -> finalize checks:
       - plan exists?
       - promised follow-up actually scheduled?
       - guard closed?
  -> if yes:
       follow-up task remains in truth source
  -> if no:
       anomaly enters watchdog / triage / dashboard
```

### why this is better than "more rules"

This hybrid approach is better because:

1. the fast path remains deterministic
2. `[wd]` remains immediate
3. simple delayed replies remain cheap and reliable
4. compound follow-up can become structured
5. runtime still catches LLM omission or failure

### rollout suggestion

#### phase A

- keep current simple delayed-reply parser
- add planning tools and prompt contract
- only route obviously compound requests into the tool path

#### phase B

- add promise guard and anomaly detection
- project planning anomalies into dashboard / triage / continuity

#### phase C

- evaluate whether more channels or agents should use tool-assisted planning by default

### final recommendation

The best current direction is:

- do not move `[wd]` into the LLM
- do not rely on regex growth forever
- do not rely on LLM output alone
- expose explicit task-system tools
- add strong prompt rules
- add runtime monitoring that proves the tool path really happened

In one sentence:

> Let the LLM help decompose compound requests, but let the runtime prove that every promised follow-up became a real scheduled task.

## 中文

> 状态：设计草稿
> 范围：复合请求、延迟 follow-up 规划、以及 tool-assisted task decomposition

### 问题

有些用户请求在一条消息里同时包含多个任务意图：

- 现在做一件事
- 过一会儿再回来做一件事
- 甚至第二件事还依赖第一件事是否完成

例如：

- `你先查一下天气，然后5分钟后回复我信息`
- `先整理这个问题，10分钟后再提醒我看结果`
- `先跑一轮检查，半小时后回来告诉我是否还报错`

Regex 能兜住一部分低歧义句子，但它不是这类问题的长期正确解法。

### 目标

这份设计希望做到：

1. 保留当前快速 control-plane 路径
2. 避免让每条用户请求都先进入一次 LLM planning
3. 让 LLM 在真正需要时显式创建结构化 follow-up task
4. 发现“模型口头承诺了未来动作，但没真正建任务”的情况
5. 保持 task-system runtime 作为最终真相源

### 非目标

这份设计不应该：

1. 把 `[wd]` 生成移进 LLM
2. 让每条请求在首条确认前都依赖 tool 调用
3. 把自由文本输出当成 delayed task 已存在的证明
4. 替代针对简单、低风险 delayed reply 的确定性解析

### 推荐模型：hybrid，而不是 tool-only

推荐方向是一个 hybrid 模型：

1. deterministic runtime fast path
2. tool-assisted planning path
3. runtime verification and fallback

它比两个极端都更好：

- 只靠 regex 扩展，太脆弱
- 只靠 LLM 建任务，也不可靠

### 为什么 `[wd]` 必须保持在 LLM 之外

`[wd]` 是 control-plane acknowledgement，不是 planning 产物。

它必须保持在 LLM 之外，因为：

1. 它必须第一时间可见、低延迟
2. 不能等待模型 planning 或 tool latency
3. 就算模型超时或跳过 tool，它也必须照常工作

所以顺序应保持为：

```text
消息到达
  -> register / pre-register
  -> 发送 [wd]
  -> 选择执行路径
       - deterministic runtime fast path
       - 或 LLM-assisted planning path
```

### 什么情况下应该让 LLM 介入

只有当 runtime 检测到这条消息可能是复合或模糊请求时，才应该让 LLM 介入。

建议路由规则：

- 保持 deterministic 处理的情况：
  - 简单即时任务
  - 简单单一意图 delayed reply
- 进入 LLM planning 的情况：
  - 即时工作 + 延迟 follow-up
  - 依赖前序工作的 follow-up
  - 延迟意图存在但不够精确的多步请求

可以压成一句：

```text
简单请求 -> runtime 直接处理
复合或模糊请求 -> runtime 让 LLM 用工具做 planning
```

### 建议提供的工具

LLM 不应该直接操作原始 task 文件，而应该调用显式 task-system 工具。

#### 工具：`ts_get_task_planning_context`

用途：

- 获取 planner 所需的任务/session 上下文

输入：

```json
{
  "session_key": "agent:main:feishu:direct:...",
  "message_text": "你先查一下天气，然后5分钟后回复我信息"
}
```

输出：

```json
{
  "session_key": "agent:main:feishu:direct:...",
  "agent_id": "main",
  "channel": "feishu",
  "current_queue_state": {
    "position": 2,
    "active_task_id": "task_abc"
  },
  "message_text": "你先查一下天气，然后5分钟后回复我信息"
}
```

#### 工具：`ts_create_followup_plan`

用途：

- 为复合请求记录一份结构化 follow-up 计划

输入：

```json
{
  "source_task_id": "task_main_123",
  "immediate_work": "查一下天气",
  "followup_kind": "delayed-reply",
  "followup_delay_seconds": 300,
  "followup_message": "回来继续汇报天气结果",
  "dependency": "after-source-task-finalized"
}
```

输出：

```json
{
  "plan_id": "plan_xyz",
  "source_task_id": "task_main_123",
  "accepted": true,
  "runtime_contract": {
    "followup_kind": "delayed-reply",
    "dependency": "after-source-task-finalized"
  }
}
```

#### 工具：`ts_schedule_followup_from_plan`

用途：

- 把计划物化成真实的 scheduled follow-up task

输入：

```json
{
  "plan_id": "plan_xyz"
}
```

输出：

```json
{
  "task_id": "task_followup_456",
  "status": "paused",
  "due_at": "2026-04-06T11:30:00+08:00",
  "scheduled": true
}
```

#### 工具：`ts_attach_promise_guard`

用途：

- 告诉 runtime：模型打算承诺一个未来动作
- 即使调度还没完成，也先创建一层显式 guard expectation

输入：

```json
{
  "source_task_id": "task_main_123",
  "promise_type": "delayed-followup",
  "expected_by_finalize": true
}
```

输出：

```json
{
  "guard_id": "guard_789",
  "armed": true
}
```

#### 工具：`ts_finalize_planned_followup`

用途：

- 确认计划中的 follow-up 确实已经物化

输入：

```json
{
  "source_task_id": "task_main_123",
  "guard_id": "guard_789",
  "followup_task_id": "task_followup_456"
}
```

输出：

```json
{
  "ok": true,
  "promise_fulfilled": true
}
```

### 提示词里应该明确要求什么

模型需要显式规则。只有给它工具还不够。

建议补进 prompt 的要求：

1. 如果请求只包含即时工作，不要创建 delayed follow-up task
2. 如果请求明确要求 delayed follow-up，必须通过 task-system 工具创建真实 plan 或 task
3. 不能在自然语言里承诺未来回复，除非对应的 task-system 工具调用成功
4. 如果用户请求模糊，应先追问，而不是静默猜测 delayed follow-up
5. 如果 tool 调度失败，必须明确说失败，而不是假装未来 follow-up 已存在

最重要的一条硬规则是：

> 只有当 runtime 已接受一条真实 scheduled follow-up 时，模型才能说“我 5 分钟后回来”。

### 监控与兜底

runtime 必须默认 LLM 可能会：

- 超时
- 跳过工具
- 选错工具
- 用自然语言承诺未来动作，却没有建 task

所以即使引入工具，runtime 监控仍然必须存在。

#### 监控 1：promise-without-task detector

在 finalize 时检查：

- 模型输出里是否存在 delayed promise
- 是否存在匹配的 follow-up plan 或 task

如果没有：

- 给任务打上 planning anomaly
- 发 operator-visible diagnostics
- 在 dashboard / triage / continuity 中暴露出来

#### 监控 2：tool expectation guard

如果 LLM 调用了 `ts_attach_promise_guard`，那么 finalize 必须验证：

- guard 存在
- follow-up plan 或 task 已创建
- guard 已关闭

如果没有：

- 把任务 finalize 成 `done-with-planning-anomaly` 或类似投影状态
- 发 watchdog 可见信号

#### 监控 3：fallback runtime scheduling

对于低风险、高置信度的情况，即使 LLM 路径不可用，runtime 仍可以直接调度 follow-up。

这样就保留了当前安全网：

- deterministic parsing 仍然是 backup path
- LLM tool path 负责更结构化的那部分

### 推荐 runtime 顺序

```text
用户消息
  -> register / [wd]
  -> runtime 分类:
       - simple immediate task
       - simple delayed reply
       - compound or ambiguous
  -> 如果是 simple immediate:
       直接执行
  -> 如果是 simple delayed:
       直接调度
  -> 如果是 compound or ambiguous:
       让 LLM planner 介入
         -> create follow-up plan
         -> arm promise guard
  -> source task 执行
  -> finalize 检查:
       - plan 存在吗?
       - promised follow-up 真的建出来了吗?
       - guard 关闭了吗?
  -> 如果是:
       follow-up task 留在 truth source 中
  -> 如果否:
       anomaly 进入 watchdog / triage / dashboard
```

### 为什么这比“继续补规则”更好

这个 hybrid 方案更好，因为：

1. fast path 仍然是确定性的
2. `[wd]` 仍然是立即可见的
3. 简单 delayed reply 仍然便宜而可靠
4. compound follow-up 可以变成结构化对象
5. runtime 仍然能抓住 LLM 漏调工具或失败的情况

### 建议 rollout

#### phase A

- 保留当前 simple delayed-reply parser
- 增加 planning tools 与 prompt contract
- 只把明显复合请求路由到 tool path

#### phase B

- 增加 promise guard 与 anomaly detection
- 把 planning anomaly 投影进 dashboard / triage / continuity

#### phase C

- 再评估是否要让更多 channel 或 agent 默认走 tool-assisted planning

### 最终建议

当前最好的方向是：

- 不把 `[wd]` 移进 LLM
- 不再长期依赖 regex 增长
- 不相信 LLM 文本输出本身
- 暴露显式 task-system tools
- 增加明确 prompt 规则
- 增加 runtime 监控，证明 tool path 真的发生过

一句话总结：

> 让 LLM 帮忙拆解复合请求，但让 runtime 负责证明每一个被承诺的 follow-up 都变成了真实 scheduled task。
