# Worker Handoff

## Current Handoff Direction
- Direction: `Milestone 3: system performance testing and optimization`
- Status: `active`
- Why Now: 当前工作已经切到 benchmark surface、measurement entrypoints 和 baseline evidence，多轮 handoff 需要围绕同一条性能主线恢复

## Worker Handoff Contract

- worker handoff 不是只恢复聊天上下文，而是把剩余工作、恢复入口、回队列规则和升级条件写成 durable 真相。
- 当 worker 在 checkpoint、超时、失败或显式交接后停下，PTL 必须能从 durable 控制面读回剩余工作，并决定继续、换人、回流或升级。
- 回流到 program-board 的工作不能丢失原来的验证入口、边界说明和当前风险。
- 如果 handoff 过程中暴露出业务方向、兼容性承诺或显著成本 / 时间边界变化，PTL 必须升级给人类裁决。
- handoff 结论必须写回 `.codex/status.md` / `.codex/plan.md` / `.codex/program-board.md`，不能只停在临时聊天里。

## Handoff Triggers

| Trigger | 什么时候发生 | 需要的 handoff 行为 |
| --- | --- | --- |
| checkpoint 完成 | 当前 worker 已到当前检查点 | 评估剩余工作是否继续、切换或回流 |
| 超时 / 长时间无输出 | worker 没有继续推进到下一检查点 | 由 PTL 接管并决定后续 |
| 验证失败 | tests / gate / benchmark baseline 失败 | 暂停当前 worker 推进并评估修复或升级 |
| 显式交接 | 当前线程准备结束或切换上下文 | 生成 durable handoff 并决定下一位 owner |
| 方向重排 | program-board 顺序或主线发生变化 | 将当前未完成工作回流并等待新排序 |

## Recovery Sources

| 恢复源 | 能读到什么 | 为什么重要 |
| --- | --- | --- |
| `.codex/status.md` | 当前 active slice、执行进度、风险和 Next 3 | 恢复当前推进位置 |
| `.codex/plan.md` | 当前执行线、任务板、阶段目标和退出条件 | 恢复当前长任务的具体工作 |
| `.codex/strategy.md` | 主线、专项建议和人类审批边界 | 确认 handoff 后还能不能继续 |
| `.codex/program-board.md` | 活跃 workstreams、排序、backlog 回流规则 | 决定回到哪条线或挂回哪里 |
| `.codex/delivery-supervision.md` | checkpoint 节奏、自动继续边界、升级时机 | 确认 handoff 是否需要升级 |
| 最新 devlog / handoff snapshot | 最近 durable reasoning 与恢复包 | 减少切换 worker 时的认知丢失 |

## Re-entry Actions

| PTL 动作 | 什么时候用 | 结果 |
| --- | --- | --- |
| 继续同一 worker | 当前方向没变，worker 只是到 checkpoint | 保持当前执行线不变 |
| 换 worker 接手 | 当前任务仍有效，但需要新的执行者接住 | 保留同一条执行线或切片 |
| 挂回 program-board | 当前不该继续写，但工作本身仍有效 | 进入下一轮调度 |
| 升级给人类 | handoff 已跨到业务方向、兼容性或成本边界 | 等待裁决，不自动继续 |

## Queue / Return Rules

| 情况 | 回流位置 | 说明 |
| --- | --- | --- |
| 仍是主线且边界没变 | 保留在当前 active slice | 继续或换 worker 接手 |
| 当前不该继续但仍有价值 | 挂回 supporting backlog / sequencing queue | 等待下一次编排判断 |
| 只是文档 / 验证 / 收口尾项 | 并入下一个 checkpoint 的 sidecar work | 不另开一条主写入线 |
| 出现方向冲突 | 不回队列，直接升级 | 避免把错误方向重新排回主线 |

## Human Escalation Boundary

| 情况 | 升级规则 |
| --- | --- |
| 方向未变，技术边界清楚 | 系统可自动继续接续 |
| 只是需要换 worker 或等下一 checkpoint | 系统可自动回流或转交 |
| 业务方向 / 优先级 / 兼容性承诺变化 | 必须升级给人类 |
| 显著成本 / 时间变化 | 必须升级给人类 |

## Next Handoff Checks
1. 确认 worker 停下后的接续、回流和升级都能靠当前 benchmark 主线的 durable 真相完成。
2. 继续观察哪些 baseline capture 场景会反复出现，再决定是否需要更强的调度层。
3. 只在 disjoint write scope 和结果回收口都明确时，才考虑扩成多执行器调度。
