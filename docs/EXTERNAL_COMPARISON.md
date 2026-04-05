# External Comparison

> 最后更新：2026-04-05
> 角色：这份文档用于记录外部项目对比结论，帮助本项目判断“哪些值得借鉴，哪些不该照搬”。

## 1. 为什么要做这份对比

`openclaw-task-system` 不是单纯的 agent orchestrator，也不是单纯的 queue 或 chatbot 插件。

它在做的是：

> 把 OpenClaw 原本的聊天消息流，提升成带统一任务真相源与用户可见控制面的任务流。

因此，对外部项目的比较不应该只看“名字像不像”，而要看它们是否真的覆盖了下面这些问题：

- 消息到任务的提升
- 高优先级 control-plane
- 用户第一时间可见的 `[wd]`
- queue / continuation / watchdog / continuity / `/tasks`
- 多 channel 的一致语义

结论先说：

- 目前没有找到一个与本项目完全同构的现成 GitHub 项目
- 但有几类项目在局部设计上很值得借鉴

## 2. 对比对象

本轮主要对比了 4 类外部参考：

1. `humanlayer/agentcontrolplane`
2. `hzxbzp/llama-agents`
3. `docker/cagent`
4. GitHub Copilot SDK 的 steering / queueing 设计

## 3. 总表

| 对象 | 像的地方 | 不像的地方 | 最值得借鉴 |
|---|---|---|---|
| `humanlayer/agentcontrolplane` | 强调 agent control plane、异步调度、外环控制 | 更偏分布式 agent orchestrator，不聚焦聊天入口与用户可见控制面 | control-plane 必须独立成层 |
| `hzxbzp/llama-agents` | 明确有 message queue / control plane / agent service 分层 | 更偏多 agent 编排框架，不是多 channel 聊天任务运行时 | queue / control plane / worker 的职责边界 |
| `docker/cagent` | 是一个 agent runtime / orchestration 系统 | 更像 agent builder/runtime 产品，不聚焦 `[wd]`、排队真相源和 channel 入口 | runtime 的模块边界与组件组织方式 |
| GitHub Copilot SDK steering / queueing | 直接处理新消息是 steering 还是 enqueue 的问题 | 是行为文档，不是任务系统实现 | 用户追加消息与已有任务之间的语义规则 |

## 4. 分项结论

### 4.1 `humanlayer/agentcontrolplane`

链接：

- https://github.com/humanlayer/agentcontrolplane

像的地方：

- 明确使用 `control plane` 这个概念
- 强调 agent 运行不应只靠单次请求-响应完成
- 更关注系统级调度与外部控制

不像的地方：

- 更像分布式 agent orchestrator
- 不聚焦多 channel 聊天入口
- 不聚焦“用户第一时间看到 `[wd]` / follow-up / queue 状态”这类用户可见控制面

对本项目的真正借鉴：

- `control-plane` 必须是独立概念，不是普通 reply 的附属功能
- 系统应当有“控制面真相源”，而不是临时消息拼接

不该照搬的地方：

- 不能因为它是 control plane，就直接把本项目做成“任务调度平台”
- 我们的核心还是 chat-native task runtime，而不是通用分布式 agent control service

### 4.2 `hzxbzp/llama-agents`

链接：

- https://github.com/hzxbzp/llama-agents

像的地方：

- 明确区分 message queue、control plane、agent service
- 更像“多组件协同”而不是单函数插件
- 很适合借鉴“消息不是任务本身，任务是围绕消息建立的运行态对象”

不像的地方：

- 更偏多 agent 编排框架
- 不聚焦用户可见控制面
- 不处理真实聊天 channel 下的 ack / queue / continuation 体感问题

对本项目的真正借鉴：

- `queue / control plane / worker` 这三层需要明确分工
- 任务运行态不应退化成消息副作用
- control-plane 应该围绕统一 runtime truth source 展开

不该照搬的地方：

- 不能让本项目过度偏向“多 agent 编排框架”
- 我们当前更需要先解决 channel 入口、用户可见控制面和 task truth source

### 4.3 `docker/cagent`

链接：

- https://github.com/docker/cagent

像的地方：

- 是 agent runtime
- 有 runtime / orchestration / tool 组合能力

不像的地方：

- 更像 agent builder / runtime 产品
- 不聚焦聊天入口到任务流的提升
- 不聚焦 channel queue / receive-time ack / 用户可见 control-plane

对本项目的真正借鉴：

- 模块化 runtime 组织方式
- 把系统能力拆成清晰组件，而不是继续堆脚本

不该照搬的地方：

- 不能把精力误导到通用 agent runtime 外壳
- 当前最关键的问题不是 runtime 花样，而是 channel-native task runtime 的控制面一致性

### 4.4 GitHub Copilot SDK steering / queueing

链接：

- https://docs.github.com/en/copilot/how-tos/copilot-sdk/use-copilot-sdk/steering-and-queueing

像的地方：

- 直接回答“新消息到来后，是 steering、插队，还是排队”
- 很接近本项目对用户追加消息的处理语义
- 能帮助定义 control-plane 与已有任务的冲突规则

不像的地方：

- 这是行为/产品语义文档
- 不是一个 task runtime 的完整实现

对本项目的真正借鉴：

- 新消息不应被简单当作“再来一条普通消息”
- 需要区分：
  - steering message
  - queueing message
  - control-plane message
  - reply message

不该照搬的地方：

- 不能把 SDK 行为文档当成系统架构替代品
- 我们仍需要自己的 task truth source、control-plane lane、channel producer contract

## 5. 对本项目最有价值的借鉴点

真正值得吸收进本项目 roadmap 的，主要是 4 点：

### 5.1 control-plane 必须独立成层

来源：

- `humanlayer/agentcontrolplane`

应用到本项目：

- `[wd]`
- follow-up
- queue position
- cancel / resume
- watchdog / continuity
- completed / failed / paused / cancelled

这些都不应再被当成普通 reply 的附属行为。

### 5.2 queue / control plane / worker 需要明确分工

来源：

- `llama-agents`

应用到本项目：

- channel receive / pre-register producer
- control-plane lane
- task execution / reply lane

这三层必须分清，否则任务语义和消息语义会继续混在一起。

### 5.3 用户追加消息需要有明确 steering / queueing 语义

来源：

- GitHub Copilot SDK steering / queueing

应用到本项目：

- 同一 session 里第二条消息来了，到底是：
  - steering 现有任务
  - 新建排队任务
  - 只产生 control-plane 管理请求

这件事后续要成为正式 contract，而不是继续依赖局部 if/else。

### 5.4 不要把项目偏成通用 orchestrator

来源：

- 对 `agentcontrolplane` / `llama-agents` / `cagent` 的整体比较

应用到本项目：

- 本项目的核心仍然是 OpenClaw 上的 chat-native task runtime
- 不应为了“更像外部框架”而牺牲当前最关键的问题：
  - receive-time ack
  - control-plane 优先级
  - channel queue 与 task queue 边界
  - 用户可见状态一致性

## 6. 最终结论

这轮对比后的清晰结论是：

1. 本项目没有找到一个完全现成的对标实现
2. 值得借鉴的是“分层思想”和“语义边界”，不是直接照搬代码结构
3. 本项目最独特也最关键的地方，仍然是：

> 在多 channel 聊天入口上，把消息流提升成任务流，并把控制面做成用户第一时间可见、最高优先级、可解释的系统能力。

因此，对外部项目最正确的使用方式是：

- 借鉴它们的分层思想
- 保持我们自己的问题定义
- 不被带偏成另一个产品形态
