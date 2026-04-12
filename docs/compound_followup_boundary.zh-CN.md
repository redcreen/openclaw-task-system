# Compound follow-up boundary

[English](compound_followup_boundary.md) | [中文](compound_followup_boundary.zh-CN.md)

> 状态：已发货的 runtime 边界
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
- supervisor-first contract：runtime 会校验“稍后再做”的承诺背后是否真的落成了真实任务
- acceptance coverage：显式证明 compound 请求在没有 structured tool plan 前，不能偷偷挂出 hidden follow-up state

当前系统明确**不承诺**：

- 广泛自动支持 mixed-intent compound request
- 从 legacy post-run phrasing 里静默补出 hidden follow-up task
- 让 task-system 变成统一的前置语义分类器

这意味着当前已发货的 runtime 边界已经明确：

- compound request 仍然可以先进入普通 task 路径
- 但 runtime 不会只凭 compound wording 静默创建 delayed follow-up
- 如果系统真的要承诺未来动作，必须先有可审计、可恢复的 structured planning state

长期正确答案不应该是：

- 让 task-system 继续长出更多 phrase / regex 规则

而应该是：

- 继续让 agent / LLM 理解请求
- 让 task-system 监督并验证未来承诺是否真的落成 task

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
- compound 请求：没有 structured plan 前，不会由 runtime 静默自动物化 follow-up
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

### 下一步 roadmap 方向

一个很强的候选方向是：

- 把 task-system 的 task 创建和 follow-up 调度能力，暴露成 LLM 可调用工具

这样模型就可以在不同场景里显式选择：

- 正常即时执行
- 创建明确的 delayed follow-up
- 进行多步任务拆解

下一轮真正要讨论的不是“再补哪些短语规则”，而是怎样把这类结构化 planning 能力变成新的明确 roadmap candidate。
