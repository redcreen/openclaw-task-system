# 项目助手继续

## 现在在哪里

| 项目 | 当前值 |
| --- | --- |
| 层级 | `中型` |
| 当前判断 | `Milestone 3` 已收口；当前主线是 `post-performance live pilot activation preparation`。 |
| 当前阶段 | 先固定 activation 入口条件、证据包和 install-sync 决策，再讨论第一次有界 rehearsal。 |
| 当前工作域 | activation prep / operator evidence / deploy boundary |
| 当前切片 | `activation-prep entry criteria + install-sync decision` |
| 当前执行线 | 先定义 activation evidence 和 rollback 边界，再决定 install-sync 路径，最后才允许进入第一次有界 rehearsal。 |
| 当前结论 | `Milestone 2` 与 `Milestone 3` 已完成；当前主线切到 `AP-1` 到 `AP-3`。 |
| 架构信号 | `绿色` |
| 升级 Gate | `自动继续` |
| 当前主要风险 | 如果不先写清 activation 入口条件和 install-sync 意图，就会在 rehearsal 前重新引入阶段边界模糊。 |
| 完整看板 | `项目助手 进展` / `project assistant progress` |

## 接下来先做什么

| 顺序 | 当前要做的事 |
| --- | --- |
| 1 | 定义 activation 入口条件和 operator evidence 包。 |
| 2 | 明确 installed-runtime drift 是否需要在 rehearsal 前通过显式 deploy 清掉。 |
| 3 | 给第一次有界 rehearsal 写清 rollback 条件和性能回流规则。 |

## 当前任务板

| 任务 | 类型 | 状态 |
| --- | --- | --- |
| 收口 Milestone 3，并把性能基线写实为已完成。 | 阶段收口 | 已完成 |
| 定义 activation 入口条件和 operator evidence 包。 | rehearsal 准备 | 进行中 |
| 决定 install-sync 路径。 | deploy 边界 | 待执行 |
| 固定首轮 rehearsal 的 rollback 与性能回流规则。 | 风险控制 | 待执行 |
