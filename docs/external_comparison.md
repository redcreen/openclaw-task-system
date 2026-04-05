# External Comparison

> 角色：这份文档记录外部参考项目的对比结论，帮助本项目判断哪些设计值得借鉴，哪些不该照搬。

## 1. 这份对比解决什么问题

`openclaw-task-system` 不是普通聊天插件，也不是通用 agent orchestrator。

它要解决的是：

- 消息如何提升成任务
- 控制面如何独立成层
- `[wd]`、follow-up、watchdog、continuity 如何成为系统能力
- 多 channel 如何在同一 contract 下工作

因此，对外部项目的对比重点不是“名字像不像”，而是它们是否对这些问题有启发。

## 2. 本轮参考对象

本轮正式对比了 4 类参考：

1. `humanlayer/agentcontrolplane`
2. `hzxbzp/llama-agents`
3. `docker/cagent`
4. GitHub Copilot SDK 的 steering / queueing 设计

## 3. 总结表

| 对象 | 值得借鉴 | 不该照搬 |
|---|---|---|
| `humanlayer/agentcontrolplane` | control-plane 必须独立成层 | 不要把项目带偏成分布式 orchestrator |
| `hzxbzp/llama-agents` | queue / control plane / worker 分层 | 不要过度偏向多 agent 编排框架 |
| `docker/cagent` | runtime 组件边界 | 不要把重点从 chat-native task runtime 带走 |
| GitHub Copilot SDK steering / queueing | steering / queueing 语义划分 | 不要把产品语义文档当作完整架构替代品 |

## 4. 分项结论

### 4.1 `humanlayer/agentcontrolplane`

链接：

- https://github.com/humanlayer/agentcontrolplane

借鉴点：

- `control-plane` 是独立概念，不应只是普通 reply 的附属功能
- 系统需要控制面真相源，而不是临时消息拼接

不照搬的原因：

- 这个方向更偏分布式 orchestrator
- 本项目核心仍然是 OpenClaw 上的 chat-native task runtime

### 4.2 `hzxbzp/llama-agents`

链接：

- https://github.com/hzxbzp/llama-agents

借鉴点：

- `queue / control plane / worker` 职责边界明确
- 任务运行态不应退化成消息副作用

不照搬的原因：

- 它更偏多 agent 编排框架
- 本项目当前更关键的是 channel 入口、控制面和用户状态一致性

### 4.3 `docker/cagent`

链接：

- https://github.com/docker/cagent

借鉴点：

- runtime 的组件化组织方式
- 系统能力应拆成清晰模块，而不是继续堆脚本

不照搬的原因：

- 它更像通用 agent runtime 产品
- 本项目重点不是 runtime 花样，而是控制面与任务真相源

### 4.4 GitHub Copilot SDK steering / queueing

链接：

- https://docs.github.com/en/copilot/how-tos/copilot-sdk/use-copilot-sdk/steering-and-queueing

借鉴点：

- 用户追加消息不能继续被简单当成“再来一条普通消息”
- 需要区分：
  - steering message
  - queueing message
  - control-plane message
  - reply message

不照搬的原因：

- 这是行为和产品语义文档
- 不是完整的 task runtime 实现

## 5. 对本项目最有价值的借鉴点

最终真正吸收进本项目 roadmap 的，主要是 4 条：

1. control-plane 必须独立成层
2. queue / control plane / worker 必须明确分层
3. 用户追加消息必须有正式 steering / queueing 语义
4. 不要把项目带偏成通用 orchestrator

## 6. 最终结论

这轮对比的正式结论是：

1. 当前没有找到与本项目完全同构的现成实现
2. 真正值得借鉴的是分层思想和语义边界
3. 本项目最独特也最关键的问题仍然是：

> 在多 channel 聊天入口上，把消息流提升成任务流，并把控制面做成用户第一时间可见、最高优先级、可解释的系统能力。

因此，对外部项目最正确的使用方式是：

- 借鉴它们的分层思想
- 保持我们自己的问题定义
- 不被带偏成另一个产品形态
