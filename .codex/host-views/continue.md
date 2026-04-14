# 项目助手继续

## 现在在哪里

| 项目 | 当前值 |
| --- | --- |
| 层级 | `中型` |
| 当前判断 | 当前主线是 `Milestone 3: system performance testing and optimization`，不是继续收口 M2。 |
| 当前阶段 | 先建立可复现性能基线，再讨论热点和优化。 |
| 当前工作域 | runtime / control-plane / operator 性能基线 |
| 当前切片 | `performance baseline: measurement surface + reproducible entrypoints` |
| 当前执行线 | 先定义 benchmark surface、fixtures 与 budgets，再采集 baseline，最后才允许优化。 |
| 当前结论 | `Milestone 2` 已完成；当前主线继续推进 `PL-1` 到 `PL-4`。 |
| 架构信号 | `黄色` |
| 升级 Gate | `提醒后继续` |
| 当前主要风险 | 还没有 durable benchmark surface、样本和预算；如果直接优化，很容易回到凭感觉改代码。 |
| 完整看板 | `项目助手 进展` / `project assistant progress` |

## 接下来先做什么

| 顺序 | 当前要做的事 |
| --- | --- |
| 1 | 定义第一轮 benchmark surface、fixtures 和预算。 |
| 2 | 把测量入口收敛成可复现命令，避免 baseline 依赖某个维护者的本地习惯。 |
| 3 | 在保持 Growware / runtime 安全验证栈全绿的前提下，采集第一轮 baseline 并做热点归因。 |

## 当前任务板

| 任务 | 类型 | 状态 |
| --- | --- | --- |
| 关闭 Growware pilot foundation，并把 M2 写实为已完成。 | 阶段收口 | 已完成 |
| 定义 benchmark surface 与预算。 | 基线定义 | 进行中 |
| 建立可复现测量入口。 | 测量基础设施 | 待执行 |
| 采集 baseline、归因热点并保护首轮优化。 | 优化前验证 | 待执行 |
