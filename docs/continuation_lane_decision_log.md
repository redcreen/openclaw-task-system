# English

## continuation lane decision log

### status

- recorded: 2026-04-06
- scope: delayed follow-up claiming, scheduling, and delivery
- related change: `7476f1d` `Split continuation claim lane from main lane`

### problem

Tool-created delayed follow-ups were successfully written into the task truth source, but some of them did not fire at their due time.

Observed example:

- a request created two valid follow-up tasks:
  - one due in 3 minutes
  - one due in 5 minutes
- both tasks were present in truth source as:
  - `status = paused`
  - `continuation_state = scheduled`
  - valid `continuation_due_at`
- after the due time passed, the user still received nothing

This was not a planning failure.

It was a continuation claiming failure.

### root cause

The old `claim_due_continuations_from_payload()` implementation used session-level busy locking:

- any `running` task under the same `(agent_id, session_key)` blocked continuation claim
- only one continuation per session could be claimed in one pass

This caused two bad outcomes:

1. a running main task could block a due continuation
2. one due continuation could block another continuation in the same session

In user-facing terms, this was wrong:

- a scheduled follow-up already had a real task
- but the user still saw no result
- and later due tasks could delay earlier due tasks simply because they shared a session lane

### why the old design was wrong

The old design treated delayed follow-ups as if they shared the same execution lane semantics as main tasks.

That assumption does not hold.

Main tasks and delayed follow-ups have different responsibilities:

- main task lane:
  - agent and llm execution
  - potentially long-running
  - user request fulfillment
- continuation lane:
  - time-based delivery
  - task-system supervised output
  - short, deterministic dispatch at or after a due time

They can share:

- the same user-facing session context
- the same truth source

But they must not share:

- the same busy-lock semantics

### accepted design change

The accepted runtime contract is now:

1. delayed follow-ups stay in the same user-facing session context
2. delayed follow-ups are claimed by a task-system continuation lane
3. continuation claiming is ordered by absolute `continuation_due_at`
4. a running main task must not block a due continuation
5. one due continuation must not starve another continuation in the same session

This is a structural change, not a compensation policy.

### implementation summary

The claim logic was changed so that:

- due continuations are collected from truth source
- they are sorted by:
  - `continuation_due_at`
  - `created_at`
  - `task_id`
- all due continuations can be claimed in one pass
- claim no longer depends on session-level `running` state from the main lane

### tests added or updated

The regression suite now explicitly covers:

- all due tasks in the same session lane are claimed
- due continuations are ordered by absolute due time within one session
- a running main task in the same session does not block continuation claim

### user-facing rationale

This change exists because delayed follow-ups are not “extra chat replies”.

They are scheduled supervision outcomes.

If a user asks for:

- `1 minute later`
- `3 minutes later`
- `5 minutes later`

the system must behave like a real scheduler:

- earlier due work goes first
- unrelated main-lane work must not hide or delay it

### future architecture note

This decision should be folded into the long-term architecture wording:

- continuation lane is a first-class lane
- continuation scheduling is due-time ordered
- continuation delivery is supervised by task-system, not blocked by main-lane busy state

Until that wording is fully merged into the architecture document, this file is the decision log of record.

---

# 中文

## continuation lane 决策日记

### 状态

- 记录时间：2026-04-06
- 范围：延迟 follow-up 的 claim、调度与发送
- 相关提交：`7476f1d` `Split continuation claim lane from main lane`

### 问题

tool 创建出来的 delayed follow-up 已经成功写进 task truth source，但有些任务到了时间点却没有真正发出去。

实际观察到的例子：

- 一条请求成功创建了两条 follow-up task：
  - 一条 3 分钟后到点
  - 一条 5 分钟后到点
- 它们在 truth source 里都已经是：
  - `status = paused`
  - `continuation_state = scheduled`
  - 并且有合法的 `continuation_due_at`
- 但到了时间点之后，用户还是没有收到消息

这不是 planning 失败。

这是 continuation claim 失败。

### 根因

旧的 `claim_due_continuations_from_payload()` 采用了 session 级别的 busy 锁：

- 同一个 `(agent_id, session_key)` 下只要有任何 `running` task，就会阻塞 continuation claim
- 同一个 session 在一次 claim 中只允许 claim 一条 continuation

这会带来两个错误结果：

1. 一个 running 的 main task 会阻塞已经到点的 continuation
2. 同一个 session 下，一条 due continuation 也会阻塞另一条 continuation

从用户视角看，这显然不对：

- follow-up 明明已经排上了
- 但用户却收不到
- 甚至更早到点的任务，也可能因为共用 session lane 而被更晚的任务拖住

### 为什么旧设计是错的

旧设计默认认为 delayed follow-up 和 main task 共享同一种执行 lane 语义。

这个假设不成立。

main task 和 delayed follow-up 的职责不同：

- main task lane：
  - 负责 agent / llm 执行
  - 可能长时间运行
  - 负责完成用户主请求
- continuation lane：
  - 负责按时间点发送
  - 属于 task-system 的监督输出
  - 本质上是短、确定、到点即发的调度动作

它们可以共享：

- 同一个用户可见 session 上下文
- 同一个 truth source

但它们不应该共享：

- 同一种 busy-lock 阻塞语义

### 采用的设计变更

现在接受的 runtime contract 是：

1. delayed follow-up 仍然属于同一个用户可见 session 上下文
2. delayed follow-up 由 task-system 的 continuation lane claim
3. continuation claim 按绝对 `continuation_due_at` 排序
4. running 的 main task 不能阻塞 due continuation
5. 一条 due continuation 也不能饿死同 session 的另一条 continuation

这是一种结构改法，不是补偿策略。

### 实现摘要

claim 逻辑现在改成：

- 从 truth source 中收集所有 due continuation
- 按以下顺序排序：
  - `continuation_due_at`
  - `created_at`
  - `task_id`
- 同一轮里可以 claim 所有 due continuation
- claim 不再依赖 main lane 的 session-level `running` 状态

### 补充或更新的测试

现在回归测试已经明确覆盖：

- 同一个 session lane 下，所有 due task 都能被 claim
- 同一个 session 中，continuation 按绝对 due time 顺序 claim
- 同一个 session 里 running 的 main task 不会阻塞 continuation claim

### 面向用户的设计缘由

这次修改的出发点是：

delayed follow-up 不是“附带的一条聊天回复”，而是正式的调度监督结果。

如果用户要求的是：

- `1 分钟后`
- `3 分钟后`
- `5 分钟后`

系统就应该表现得像一个真正的 scheduler：

- 更早到点的先执行
- 无关的 main lane 工作不应该把它藏起来或拖住

### 后续架构文档说明

这份决策后面需要进一步折叠进正式架构文档：

- continuation lane 是一等 lane
- continuation scheduling 按 due time 排序
- continuation delivery 由 task-system 监督，不受 main-lane busy state 阻塞

在正式架构文档完全吸收之前，这份文件就是这次设计决策的记录依据。
