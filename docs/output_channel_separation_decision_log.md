# output channel separation decision log

[English](#english) | [中文](#中文)

## English

### status

- recorded: 2026-04-06
- scope: separating scheduling state from user-visible business content

### problem

Tool-assisted planning introduced a structural ambiguity:

- task-system already had a runtime-owned control-plane path for:
  - `[wd] 已收到...`
  - `[wd] 已安排妥当...`
- but the model could still mention scheduling state in the normal assistant reply

That produced duplicated or mixed user-facing messages such as:

- a normal answer that says `我已经排上了`
- plus a task-system `[wd]` that says the same thing

This was not acceptable because scheduling state is supervision state, not business content.

### rejected direction

The rejected direction is:

- let the model say scheduling state in natural language
- then keep adding regex, phrase lists, or keyword cleanup rules to strip it out

This was rejected because:

- it does not scale
- it is wording-dependent
- it silently mixes two channels first and only then tries to separate them
- it creates an unbounded maintenance burden

### accepted direction

The accepted design is output-channel separation:

1. scheduling state stays in tool results and task truth source
2. task-system projects scheduling state as runtime-owned `[wd]`
3. user-visible business content must travel in a dedicated content channel
4. the normal assistant reply must not carry raw scheduling state

### minimum implementation

The minimum implementation chosen for this phase is:

1. require user-visible business content to be emitted inside:
   - `<task_user_content> ... </task_user_content>`
2. once planning tools are used for a task, runtime only forwards content from that block
3. if no such block exists, runtime suppresses user-facing content instead of guessing
4. scheduling confirmation remains a separate `[wd]` control-plane message
5. delayed follow-up content still replies to the original message and does not carry `[wd]`

### additional product constraints confirmed in live review

Live review added two more constraints that should now be treated as part of the same design:

1. a scheduling confirmation must include a human-meaningful follow-up summary
   - bad: `[wd] 已安排妥当，将在 2分钟后 回复。`
   - good: `[wd] 已安排妥当：2分钟后同步明天天气。`
2. if a request is primarily about future reminders or future follow-up delivery, the immediate user-visible message should usually be control-plane only
   - do not send the eventual business result immediately unless the model explicitly indicates that an immediate result is required
   - in those future-first cases, the default immediate user-visible output should be `[wd]` scheduling state, and the business result should wait until the due follow-up fires

This keeps the user-facing semantics stable:

- scheduling state is `[wd]`
- future follow-up content is the later business reply
- the immediate main answer should not collapse those two into one mixed message

### rationale

This is stricter than prompt-only guidance, but it keeps the boundary explicit:

- business content channel
- control-plane channel

That boundary is the real solution.

It is better than free-form output cleanup.

## 中文

### 状态

- 记录时间：2026-04-06
- 范围：把排程状态和用户可见业务内容彻底拆成两个输出通道

### 问题

tool-assisted planning 引入了一个结构性问题：

- task-system 已经有一条 runtime-owned 控制面通道，用来发：
  - `[wd] 已收到...`
  - `[wd] 已安排妥当...`
- 但模型仍可能在普通主答复里再说一次排程状态

于是用户会看到这种混合情况：

- 主答复里出现 `我已经排上了`
- 同时 task-system 又发一条 `[wd]` 说明已经安排妥当

这在语义上是错误的，因为“是否排上”属于监督状态，不属于业务内容。

### 明确拒绝的方向

明确拒绝的方向是：

- 先允许模型把排程状态说进自然语言主答复
- 再不断补 regex、句式表、关键词过滤或文本清洗规则把它抠掉

拒绝原因：

- 这种方案不会收敛
- 它强依赖具体说法
- 它先把两条通道混在一起，再试图事后拆开
- 后续维护成本会无限上升

### 接受的方向

正式接受的设计方向是：**输出通道分离**

1. 排程状态先留在 tool 结果和 truth source 里
2. task-system 再把排程状态投影成 runtime-owned 的 `[wd]`
3. 用户可见业务内容必须走单独的内容通道
4. 普通主答复不能再承载裸排程状态

### 这一阶段的最小实现

这一阶段选定的最小实现是：

1. 要求用户可见业务内容必须放进：
   - `<task_user_content> ... </task_user_content>`
2. 一旦某条任务已经使用了 planning tools，runtime 之后只转发这个内容块里的东西
3. 如果没有这个内容块，runtime 选择抑制用户可见内容，而不是继续猜
4. 排程成功/失败确认仍然单独走 `[wd]`
5. 到点 follow-up 内容继续回复原消息，且不带 `[wd]`

### 在 live review 中进一步确认的产品约束

这轮 live review 又补了两条需要固定下来的约束：

1. 排程确认消息必须带可读的 follow-up 摘要
   - 不好的写法：`[wd] 已安排妥当，将在 2分钟后 回复。`
   - 更合理的写法：`[wd] 已安排妥当：2分钟后同步明天天气。`
2. 如果一条请求的核心价值本来就在未来提醒 / 未来同步，那么即时用户可见消息默认应以控制面为主
   - 除非模型明确表示“现在就需要给即时业务结果”
   - 否则不应立刻把未来要发送的业务结果提前发出来
   - 这类请求的默认即时可见输出应是 `[wd]` 调度状态，业务内容留到真正到点时再发

这样才能稳定维持下面这条用户语义：

- 排程状态走 `[wd]`
- 到点 follow-up 才是业务内容
- 不能把这两类信息再混成同一条即时回复

### 设计缘由

这比“只靠提示词提醒模型”更严格，但边界更清楚：

- 一条是业务内容通道
- 一条是控制面通道

真正应该稳定下来的，就是这条边界。

它比自由文本清洗更接近正式架构。
