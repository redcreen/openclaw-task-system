# Delivery Supervision

## Current Delivery Direction
- Direction: `reply-latency and context-weight governance`
- Status: `active`
- Why Now: repo-local 性能里程碑已经收口，但 host-observed 回复慢重新成为用户可见 blocker，当前监督重点是治理证据、上下文减负顺序和 activation 恢复条件

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
| 2 | 推进执行线 | 先固定 slowdown 证据和 audit 命令，再排序 prompt/context 减负项，最后才写 activation 恢复条件 | delivery worker | 每轮主体 |
| 3 | 运行验证并刷新真相 | 运行 runtime-safety 验证、session audit 和 benchmark guardrail，并刷新状态真相 | delivery worker | 每轮验证后 |
| 4 | 决定继续 / 升级 / 暂停 | 根据信号、blocker 和升级边界决定下一轮动作 | supervisor | 每轮收口时 |
| 5 | 记录阶段边界与恢复条件 | 把治理结论、resume gate 和后续 activation 风险沉淀出来 | supervisor + docs-and-release | 每个治理 checkpoint |

## Automatic Continue Boundaries

| Situation | Gate | Why |
| --- | --- | --- |
| 已批准方向内的 latency/context evidence、治理脚本、验证与文档对齐 | continue automatically | 当前切片仍在既定方向内，且没有新的用户级取舍 |
| 黄色信号但可在既有方向内收口 | raise but continue | 保留风险可见性，继续当前 checkpoint，并要求下一轮复核 |
| prompt budget、audit 阈值或验证成本需要调整但未跨到业务裁决 | raise but continue | 先记进 strategy / program board / delivery-supervision，再继续 |
| 方向、兼容性、定位、成本 / 时间边界变化 | require user decision | 立即停止自动继续，升级给人类 |
| 验证失败、benchmark 失绿、要做真实 deploy / launch，或要删除关键上下文能力 | require user decision | 先停在当前 checkpoint，再决定是否进入更高风险动作 |

## Escalation Timing

| When | Required Decision | Owner |
| --- | --- | --- |
| 开始新一轮长任务前 | 检查是否仍在已批准方向内；否则升级 | supervisor |
| 每轮验证之后 | 根据 gate / blocker / benchmark signal 决定继续还是先提醒 | delivery worker + supervisor |
| 准备进入真实本地 deploy 或 live rehearsal 时 | 必须重新确认 install-sync intent、resume gate、rollback 边界和监督状态 | supervisor + docs-and-release |
| 出现新的 measured slowdown 或治理 cuts 触发能力风险时 | 决定是否继续自动推进还是升级给人类 | supervisor |

## Executor Supervision Loop

| Executor | Current Input | Responsibility | Status |
| --- | --- | --- | --- |
| PTL | strategy + program board + delivery supervision + status | 确认当前 checkpoint、升级边界和下一轮入口 | active |
| delivery worker | active slice + execution tasks + validator outputs | 推进当前长任务、运行验证、刷新真相 | active |
| docs-and-release | roadmap + development-plan + handoff + gate outputs | 保持维护者文档、交接和门禁一致 | active |

## Backlog Re-entry Policy

| Topic | Re-entry Rule | Current Position |
| --- | --- | --- |
| follow-up polish | 只有能明显降低 activation 准备摩擦、且不分叉真相时，才允许回流 | 先保持在 supporting backlog |
| activation rehearsal prep | 只有治理专题给出 resume 条件后，才允许回主线 | 暂时保持在 supporting backlog |
| host-side self-heal | 只有审计边界发生业务级变化时，才允许升级 | 继续留在 supporting backlog |

## Next Delivery Checks
1. 确认每轮 checkpoint 都会刷新 status / plan / program-board / devlog，而不是只改一层。
2. 继续判断 session-level audit、prompt/context 排序和 startup/transcript 规则是否已经足够明确，可以支持第一轮治理 cut。
3. 只有在治理 topic 给出 resume 条件后，才把 activation prep 拉回主线。
