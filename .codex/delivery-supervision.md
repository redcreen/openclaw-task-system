# Delivery Supervision

## Current Delivery Direction
- Direction: `wd reliability and task usefulness convergence`
- Status: `active`
- Why Now: 当前最明显的用户可见问题已经不是性能，而是 runtime-owned `wd` 反馈不够准确、不够有用；同时上一轮 public-doc side-track 已被明确拿掉

## Supervised Delivery Contract

- 长期监督交付必须同时引用 `.codex/strategy.md`、`.codex/program-board.md`、`.codex/plan.md`、`.codex/status.md` 和当前 durable 文档，而不是只凭聊天上下文继续。
- 每个 checkpoint 都必须重新判断：当前工作是可以自动继续、提醒后继续，还是必须升级给人类裁决。
- 长期交付只允许在已批准的业务方向内自动继续；不能自动改变产品方向、兼容性承诺、外部定位或显著成本 / 时间边界。
- 每轮 checkpoint 都必须把验证结果、控制面真相、进展面和交接面刷新成同一套状态，而不是只更新其中一部分。
- 重要的监督循环调整、升级边界变化或 supporting backlog 回流判断，应写入 devlog，避免只剩结论没有推理链。

## Checkpoint Rhythm

| Order | Checkpoint | What Happens | Owner | When |
| --- | --- | --- | --- | --- |
| 1 | 对齐方向与输入 | 读取 strategy / program board / plan / status，确认当前工作流和 checkpoint 目标 | supervisor | 每轮开始前 |
| 2 | 推进执行线 | 先移除不该继续留在 public docs 的 side-track，再修 `wd` 首条 receipt 和终态消息 | delivery worker | 每轮主体 |
| 3 | 运行验证并刷新真相 | 运行 targeted tests、mirror、doctor、smoke 和 local deploy，并刷新状态真相 | delivery worker | 每轮验证后 |
| 4 | 决定继续 / 升级 / 暂停 | 根据信号、blocker 和升级边界决定下一轮动作 | supervisor | 每轮收口时 |
| 5 | 记录阶段边界与恢复条件 | 把治理结论、resume gate 和后续 activation 风险沉淀出来 | supervisor + docs-and-release | 每个治理 checkpoint |

## Automatic Continue Boundaries

| Situation | Gate | Why |
| --- | --- | --- |
| 已批准方向内的 `wd` 语义修正、验证和 public-doc cleanup | continue automatically | 当前切片仍在既定方向内，且没有新的用户级取舍 |
| 黄色信号但仍能通过 wording / rendering 收口 | raise but continue | 保留风险可见性，继续当前 checkpoint，并要求下一轮复核 |
| 队列语义或终态策略需要调整但未跨到业务裁决 | raise but continue | 先记进 strategy / program board / delivery-supervision，再继续 |
| 方向、兼容性、定位、成本 / 时间边界变化 | require user decision | 立即停止自动继续，升级给人类 |
| 验证失败、要做更大范围语义变更，或要删除关键 runtime safety 行为 | require user decision | 先停在当前 checkpoint，再决定是否进入更高风险动作 |

## Escalation Timing

| When | Required Decision | Owner |
| --- | --- | --- |
| 开始新一轮长任务前 | 检查是否仍在已批准方向内；否则升级 | supervisor |
| 每轮验证之后 | 根据 gate / blocker / host-log signal 决定继续还是先提醒 | delivery worker + supervisor |
| 准备进入真实本地 deploy 时 | 重新确认这次 deploy 是为了验证 `wd` 行为，而不是扩大项目范围 | supervisor + docs-and-release |
| 出现新的 host-log 失真模式或能力风险时 | 决定是否继续自动推进还是升级给人类 | supervisor |

## Executor Supervision Loop

| Executor | Current Input | Responsibility | Status |
| --- | --- | --- | --- |
| PTL | strategy + program board + delivery supervision + status | 确认当前 checkpoint、升级边界和下一轮入口 | active |
| delivery worker | active slice + host-log evidence + validator outputs | 推进当前长任务、运行验证、刷新真相 | active |
| docs-and-release | public-doc cleanup scope + gate outputs | 只移除不该继续保留的 side-track 文档 | active |

## Backlog Re-entry Policy

| Topic | Re-entry Rule | Current Position |
| --- | --- | --- |
| follow-up polish | 只有能明显提升 `wd`/continuity 实际使用价值时，才允许回流 | 先保持在 supporting backlog |
| activation rehearsal prep | 当前不抢主线 | 暂时保持在 supporting backlog |
| host-side self-heal | 只有审计边界发生业务级变化时，才允许升级 | 继续留在 supporting backlog |

## Next Delivery Checks
1. 确认每轮 checkpoint 都会刷新 status / plan / program-board，而不是只改一层。
2. 继续判断 `wd` 首条 receipt 和终态消息是否已经足够准确、足够有用。
3. 保持 public docs 不再承载这个项目范围之外的 side-track。
