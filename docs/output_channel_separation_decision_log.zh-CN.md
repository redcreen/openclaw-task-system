# output channel separation decision log

[English](output_channel_separation_decision_log.md) | [中文](output_channel_separation_decision_log.zh-CN.md)

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

### 当前已发货的 runtime contract

当前已发货的 runtime contract 是：

1. 排程成功/失败确认仍然单独走 runtime-owned `[wd]` 或其他控制面消息
2. 一旦 planning 状态已建立，runtime 优先信任 structured planning metadata，而不是自由文本里的排程描述
3. future-first 任务可以通过 `main_user_content_mode` 显式抑制即时业务内容，或只保留一条短摘要
4. 如果 runtime 不能安全信任即时业务内容，就应抑制它，而不是继续猜
5. 到点 follow-up 内容继续回复原消息，且不带 `[wd]`
6. runtime 不能把原始 planning marker 或 scheduling metadata 泄漏给用户

历史上的 `task_user_content` 校验现在只保留一个窄用途：

- 防止旧 transcript 泄漏模式悄悄回归，并为历史清理提供审计入口

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
