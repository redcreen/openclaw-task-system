# Delivery Supervision

## Current Delivery Direction
- Direction: `Milestone 3: system performance testing and optimization`
- Status: `active`
- Why Now: Growware foundation 已经收口，当前交付监督的重点是先建立 benchmark 纪律，再允许性能优化进入写入线

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
| 2 | 推进执行线 | 先定义 benchmark surface，再补 measurement entrypoints，最后才进入优化 | delivery worker | 每轮主体 |
| 3 | 运行验证并刷新真相 | 运行 runtime-safety 验证和测量入口，并刷新 status / progress / continue / handoff | delivery worker | 每轮验证后 |
| 4 | 决定继续 / 升级 / 暂停 | 根据信号、blocker 和升级边界决定下一轮动作 | supervisor | 每轮收口时 |
| 5 | 记录性能阶段摩擦 | 把测量成本、样本不稳定或回归门禁设计问题沉淀出来 | supervisor + docs-and-release | 每个 benchmark checkpoint |

## Automatic Continue Boundaries

| Situation | Gate | Why |
| --- | --- | --- |
| 已批准方向内的测量与验证 | continue automatically | 当前切片仍在既定方向内，且没有新的用户级取舍 |
| 黄色信号但可在既有方向内收口 | raise but continue | 保留风险可见性，继续当前 checkpoint，并要求下一轮复核 |
| 预算、fixtures 或验证成本需要调整但未跨到业务裁决 | raise but continue | 先记进 strategy / program board / delivery-supervision，再继续 |
| 方向、兼容性、定位、成本 / 时间边界变化 | require user decision | 立即停止自动继续，升级给人类 |
| 验证失败或 benchmark 结果不可复现 | raise but continue | 先停在当前 checkpoint，修复基线后再决定是否继续 |

## Escalation Timing

| When | Required Decision | Owner |
| --- | --- | --- |
| 开始新一轮长任务前 | 检查是否仍在已批准方向内；否则升级 | supervisor |
| 每轮验证之后 | 根据 gate / blocker / benchmark signal 决定继续还是先提醒 | delivery worker + supervisor |
| 出现重复测量摩擦时 | 考虑是否需要新的 benchmark tooling 或 fast / deep 分层 | supervisor |
| 准备回到 activation rehearsal 之前 | 必须重新确认 benchmark、回归门禁、blockers 和监督状态都足够稳定 | docs-and-release |

## Executor Supervision Loop

| Executor | Current Input | Responsibility | Status |
| --- | --- | --- | --- |
| PTL | strategy + program board + delivery supervision + status | 确认当前 checkpoint、升级边界和下一轮入口 | active |
| delivery worker | active slice + execution tasks + validator outputs | 推进当前长任务、运行验证、刷新真相 | active |
| docs-and-release | roadmap + development-plan + handoff + gate outputs | 保持维护者文档、交接和门禁一致 | active |

## Backlog Re-entry Policy

| Topic | Re-entry Rule | Current Position |
| --- | --- | --- |
| follow-up polish | 只有能明显降低测量摩擦、且不分叉真相时，才允许回流 | 先保持在 supporting backlog |
| activation rehearsal prep | 只有性能基线已建立后，才允许并入主线 | 先记录为下一阶段候选 |
| host-side self-heal | 只有审计边界发生业务级变化时，才允许升级 | 继续留在 supporting backlog |

## Next Delivery Checks
1. 确认每轮 checkpoint 都会刷新 status / progress / continue / handoff，而不是只更新其中一部分。
2. 继续判断 benchmark surface 和 budgets 是否已经足够稳定，可以支持第一轮 baseline capture。
3. 如果同类测量摩擦反复出现，再整理成 benchmark tooling 或 gate 分层提案。
