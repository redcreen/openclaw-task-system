# Strategy

## Current Strategic Direction
- Direction: `reply-latency and context-weight governance`
- Status: `active`
- Why Now: the repo-local performance milestone is closed, but measured Telegram sessions still show 16s-50s reply latency driven by oversized context surfaces; activation prep should pause until that user-visible blocker is reduced and made measurable

## Strategy Evidence Contract

- 战略建议必须引用 roadmap、development plan、当前 `.codex/status.md` 和 `.codex/plan.md`，不能只凭聊天直觉。
- 如果建议插入治理专项或架构专项，必须说明触发它的 durable repo 证据，而不是只说“感觉应该做”。
- 如果建议调整 milestone 顺序，必须指出当前顺序哪里已经和真实执行不一致，以及调整后会减少什么长期风险。
- 如果问题跨到业务方向、兼容性承诺、外部定位或显著成本 / 时间边界，必须升级给人类裁决。
- 重要战略判断应落成 devlog，避免下一次回来时只剩结论没有推理链。

## What This Layer Owns

| Topic | Strategic Layer Owns? | Notes |
| --- | --- | --- |
| roadmap / development plan 对齐建议 | yes | 可以建议调整，但不代替业务裁决 |
| 是否插入治理 / 架构专项 | yes | 需要基于 repo 证据和长期风险 |
| 当前切片是否仍是主线 | yes | 用于判断继续、重排或挂回 backlog |
| 项目定位是否需要提升 | yes | 只提出建议，仍需人类审批 |
| 业务方向变化 | no | 必须升级给人类 |

## Carryover Backlog

| Topic | Current Position | Why It Is Not Mainline |
| --- | --- | --- |
| activation rehearsal prep | supporting backlog | 当前 measured slowdown 已重新成为用户可见 blocker，所以 activation 线先退回 supporting backlog，等治理专题给出 resume 条件再回主线 |
| host-side self-heal / repair planning | supporting backlog | 只有 audit bootstrap 的边界需要被业务正式提升时，才升级优先级 |
| maintainer-facing polish | supporting backlog | 只有它能明显降低接手成本或测量摩擦时，才回拉主线 |

## Human Review Boundary

- Human Approves:
  - business direction changes
  - compatibility promises
  - external positioning changes
  - significant cost or timeline tradeoffs
- System May Propose:
  - roadmap reshaping
  - governance / architecture side-tracks
  - milestone reorder suggestions
  - strategic carryover decisions for supporting backlog topics

## Future Program-Board Boundary

- 战略层负责判断“为什么下一步是这条线”，以及何时建议插入专项或调整路线。
- 程序编排层负责把战略判断翻译成 workstream、切片顺序和串并行边界。
- 不要让战略层静默膨胀成全能调度器；编排仍应保留在 program-board。

## Next Strategic Checks
1. 把 Telegram 会话里“慢”的证据冻结成可重复跑的 repo 命令，而不是继续依赖手工拆日志。
2. 判断 prompt surface、startup transcript 和 per-turn wrapper 里，哪些属于必须保留的上下文，哪些属于纯负载。
3. 给 activation 线定义明确的 resume 条件，避免治理专题长期悬空或 silently 吞回旧主线。
