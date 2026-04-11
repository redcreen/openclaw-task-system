# Compound follow-up boundary

[English](#english) | [中文](#中文)

## English

> Status: open design boundary
> Scope: delayed reply and continuation semantics for mixed-intent user requests

### problem

The current task system handles two classes of requests well:

1. a normal task that should execute now
2. a pure delayed reply such as `3分钟后回复333`

It becomes ambiguous when one user message mixes both:

- `你先查一下天气，然后5分钟后回复我信息`
- `先处理这个问题，10分钟后再提醒我看结果`
- `先去查一下，再过一会儿回来继续`

These are compound task requests with at least two intent segments:

- an immediate task
- a delayed follow-up task

### why regex-only handling is the wrong long-term answer

It is tempting to keep adding more parsing rules for:

- `然后`
- `之后`
- `再`
- `并且`
- `回复我信息`

But that approach does not scale, because:

1. natural language is open-ended
2. the delayed part may be vague or implicit
3. the delayed part may depend on whether the immediate part succeeded
4. the message may contain more than two intent segments
5. a rule can look correct on one phrase and fail on another

So this class of problem should not be treated as a regex-completion problem.

### what the current shipped system does

Today the shipped system supports:

- direct delayed reply recognition for clear, single-intent phrases
- a stopgap for some simple compound requests:
  - immediate work remains a normal task
  - a post-run delayed follow-up can be materialized when the intent is obvious

At the same time, current OpenClaw behavior already sends even simple requests through the normal agent / LLM path.

So the long-term answer should not be:

- make task-system become a universal front-door semantic classifier

It should be:

- let the agent / LLM keep interpreting requests
- let task-system supervise and verify any promised future action

This stopgap exists to avoid user-visible breakage, but it is not the final model.

### correct architectural direction

The right long-term direction is:

1. parse the inbound request into a structured task plan
2. separate immediate work from delayed follow-up work
3. let the runtime create the needed task graph explicitly
4. make the delayed part observable as a first-class follow-up task

Conceptually:

```text
user request
  -> intent decomposition
  -> task plan
      - immediate task
      - delayed follow-up task
      - dependency and ordering
  -> task-system runtime
```

This is a planning problem, not a pure pattern-matching problem.

### product boundary for now

Current boundary:

- clear single-intent delayed replies are fully supported
- simple compound follow-up phrases remain a design boundary, not an auto-materialized runtime path
- complex or ambiguous compound requests should not rely on hardcoded phrase growth forever
- planning acceptance now explicitly verifies that a compound request can remain a normal task without any hidden follow-up state until a structured tool plan exists

Therefore:

- shipping behavior may keep compatibility wording or acceptance guards, but runtime should not silently fabricate a delayed follow-up from a legacy post-run phrase
- roadmap direction must move toward structured planning or tool-assisted task decomposition
- if the LLM planning path is unhealthy, timed out, or skipped, the system must report that honestly instead of pretending the follow-up exists
- even when tools produce internal planning or scheduling state, that state should not be shown directly to the user; it should first be projected by task-system as `[wd]` control-plane state or later business content

### why this matters

Without this boundary, the system drifts into:

- more hardcoded phrase rules
- more brittle delayed-follow-up behavior
- more hidden mismatches between what the agent promises and what the runtime actually scheduled

That would weaken the task system's core contract:

> if the system promises a delayed action, there must be a real scheduled task behind it.

### next design question

One strong candidate direction is:

- expose task-system task creation and follow-up scheduling as explicit LLM-callable tools

That would let the model choose between:

- normal immediate execution
- explicit delayed follow-up creation
- multi-step task decomposition

This question is intentionally left open for the next roadmap discussion.

## 中文

> 状态：开放设计边界
> 范围：混合意图请求中的 delayed reply 与 continuation 语义

### 问题

当前 task system 对两类请求处理得比较稳定：

1. 应该立刻执行的普通任务
2. 明确单一意图的延迟回复，例如 `3分钟后回复333`

一旦一条消息里混合了两种意图，事情就会变得模糊：

- `你先查一下天气，然后5分钟后回复我信息`
- `先处理这个问题，10分钟后再提醒我看结果`
- `先去查一下，再过一会儿回来继续`

这类请求至少包含两个意图片段：

- 一个立即任务
- 一个延迟 follow-up 任务

### 为什么不能长期靠 regex 补规则

看起来最直接的做法，是继续补更多解析规则，例如：

- `然后`
- `之后`
- `再`
- `并且`
- `回复我信息`

但这条路长期一定会失效，因为：

1. 自然语言是开放的
2. 延迟部分可能是模糊表达
3. 延迟部分可能依赖立即任务是否成功
4. 一条消息可能不止两个意图片段
5. 某条规则在一句话里成立，在另一句话里就会误判

所以这类问题不能被当成“继续补 regex”来解决。

### 当前已发布系统在做什么

当前系统已经支持：

- 对清晰、单一意图的 delayed reply 直接识别
- 对部分简单复合请求提供止血式兼容：
  - 前半段仍然作为普通任务立即执行
  - 如果后半段意图足够明显，可以在主任务完成后物化一个 delayed follow-up

同时，当前 OpenClaw 的真实行为是：

- 即使是简单请求，默认也通常还是会进入原来的 agent / LLM 路径

所以长期正确答案不应该是：

- 让 task-system 变成一个统一的前置语义分类器

而应该是：

- 继续让 agent / LLM 理解请求
- 让 task-system 监督并验证未来承诺是否真的落成 task

这个 stopgap 是为了避免明显用户问题，但它不是最终模型。

### 正确的长期架构方向

长期正确方向应该是：

1. 把入站请求先拆成结构化 task plan
2. 把立即工作和延迟 follow-up 分开
3. 由 runtime 显式创建需要的任务图
4. 让延迟部分作为一等 follow-up task 被观察和管理

概念上是：

```text
用户请求
  -> 意图拆解
  -> task plan
      - immediate task
      - delayed follow-up task
      - dependency and ordering
  -> task-system runtime
```

这本质上是 planning 问题，不是纯 pattern-matching 问题。

### 当前产品边界

当前边界可以明确成：

- 单一意图、表达清晰的 delayed reply：完全支持
- 简单复合短语：仍然只是设计边界，不再由 runtime 静默自动物化 follow-up
- 复杂或模糊的复合请求：不能长期依赖硬编码短语增长
- `planning_acceptance.py` 现在会显式验证：复合请求在没有 structured tool plan 前，不能偷偷挂出 hidden follow-up state

所以：

- 当前已发布行为里可以保留兼容提示或验收边界，但 runtime 不应再从 legacy post-run 短语里偷偷补出 follow-up task
- 但 roadmap 的方向必须转向 structured planning 或 tool-assisted task decomposition
- 如果 LLM planning 路径不健康、超时或被跳过，系统必须如实告诉用户，而不能假装 follow-up 已经存在
- 即使 tool 产出了内部 planning / scheduling 状态，这些状态也不应直接回复给用户；它们应先被 task-system 投影成 `[wd]` 控制面信息，或在真正到点时再投影成业务内容

### 为什么这件事重要

如果不把这条边界说清楚，系统就会逐渐滑向：

- 越来越多的硬编码短语规则
- 越来越脆弱的 delayed follow-up 行为
- agent 口头承诺了稍后回来，但 runtime 实际没有建任务

这会削弱 task system 的核心契约：

> 只要系统承诺了稍后再做一件事，背后就必须有一条真实的 scheduled task。

### 下一步设计问题

一个很强的候选方向是：

- 把 task-system 的 task 创建和 follow-up 调度能力，暴露成 LLM 可调用工具

这样模型就可以在不同场景里显式选择：

- 正常即时执行
- 创建明确的 delayed follow-up
- 进行多步任务拆解

这个问题目前故意保持开放，留给下一轮 roadmap 讨论。
