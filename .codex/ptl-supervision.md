# PTL Supervision

## Current PTL Direction
- Direction: `post-performance live pilot activation preparation`
- Status: `active`
- Why Now: Growware foundation 和性能里程碑都已完成，PTL 现在需要围绕 activation 入口条件、install-sync 决策和 rehearsal 边界持续巡检

## PTL Supervision Contract

- PTL 监督环必须读取 `.codex/strategy.md`、`.codex/program-board.md`、`.codex/delivery-supervision.md`、`.codex/plan.md` 和 `.codex/status.md`，不能只凭聊天上下文判断是否继续。
- PTL 负责决定何时继续、何时重排、何时先提醒后继续、何时必须升级给人类；它不负责越权修改业务方向。
- 每次 worker 停下、checkpoint 结束、验证失败或超时后，PTL 都必须重新做一次监督判断。
- PTL 的监督循环必须把结论写回 durable 真相，而不是只在聊天里说一句“继续”。
- 只要问题跨到业务方向、兼容性承诺、外部定位或显著成本 / 时间边界，PTL 就必须停止自动继续并升级给人类。

## Supervision Triggers

| Trigger | 何时触发 | PTL 要做什么 | 产出 |
| --- | --- | --- | --- |
| 周期巡检 | 到达下一次 checkpoint 节点 | 读取 strategy / program-board / delivery-supervision / status | 确认继续还是重排 |
| worker 停下 | 当前 worker 正常结束、超时、失败或显式交接 | 接管剩余工作判断 | 决定继续 / 回流 / 升级 |
| 验证变化 | gate、tests、benchmark baseline、install drift 或 rehearsal 条件变化 | 重新判断升级边界 | 决定是否继续当前线 |
| 计划变化 | active slice 完成、主线切换或 supporting backlog 回流 | 重读 program board | 决定下一条线 |
| 用户裁决 | 人类修改业务方向、优先级或重大取舍 | 更新监督基线 | 重新生成下一轮监督判断 |

## Standing Responsibilities

| 角色 | 主要输入 | 责任 |
| --- | --- | --- |
| PTL | strategy + program-board + delivery-supervision + status | 持续巡检项目、判断继续/重排/升级、把监督结论写回 durable 真相 |
| delivery worker | active slice + execution tasks + validator outputs | 推进当前写入线并在 checkpoint 后把结果交回监督环 |
| docs-and-release | roadmap + development-plan + gate outputs | 保持维护者文档、交接和门禁与 PTL 判断一致 |

## Continue / Resequence / Escalate Matrix

| 情况 | PTL 动作 | 具体处理 | 为什么 |
| --- | --- | --- | --- |
| 当前方向内、验证通过、无新 blocker | 继续 | 自动继续当前线 | 保持节奏不因人工缺席而中断 |
| 黄色信号但仍在既定方向内 | 提醒后继续 | 记录风险并继续到下个 checkpoint | 保持可见性而不把项目停住 |
| active slice 完成或优先级变化 | 重排 | 切换 program-board 顺序并刷新当前执行线 | 让主线和 supporting backlog 保持同一套调度真相 |
| 出现真实 deploy、live rehearsal、业务方向 / 兼容性 / 成本边界变化 | 升级 | 停止自动继续并通知人类裁决 | 防止 PTL 越权 |

## Active Supervision Checks

| 检查项 | 当前信号 | 说明 |
| --- | --- | --- |
| 监督输入完整 | green | strategy / program-board / delivery-supervision / plan / status 都存在 |
| 继续边界清楚 | green | 何时继续 / 提醒 / 升级已有 durable 规则 |
| worker 停下后的接管入口 | green | handoff / re-entry contract 已收口成 durable 真相 |
| 业务裁决越权防护 | green | 一旦跨到 live rollout、本地 deploy、审批边界或兼容性承诺，PTL 只升级不代替决策 |

## Next PTL Checks
1. 确认 worker 停下后，PTL 能从 durable 真相恢复 activation-prep 切片，而不是退回聊天记忆。
2. 继续观察 install-sync、evidence 包和 rollback 边界是否已经足够明确，可以支持第一次有界 rehearsal。
3. 如果新的性能 regression 试图回流，先要求它以 measured blocker 的形式回到监督契约里。
