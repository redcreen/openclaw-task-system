# 项目助手继续

## 现在在哪里

| 项目 | 当前值 |
| --- | --- |
| 层级 | `中型` |
| 当前判断 | 当前主线是 `Milestone 2: Growware Project 1 pilot foundation`，不是稳态维护。 |
| 当前阶段 | 收口 Growware 的 policy truth、activation gate 和 host-audit bootstrap。 |
| 当前工作域 | Growware 项目本地控制面与激活基线 |
| 当前切片 | `growware pilot: policy truth + activation baseline` |
| 当前执行线 | 先把 Growware foundation 变成可验证的 pilot baseline，再考虑 live rollout。 |
| 当前结论 | `EL-1` 已完成；当前主线继续推进 `EL-2` 到 `EL-4`。 |
| 架构信号 | `黄色` |
| 升级 Gate | `提醒后继续` |
| 当前主要风险 | `.policy/` 与 `.growware/policies/*.json` 之间仍有真相源裂缝。 |
| 完整看板 | `项目助手 进展` / `project assistant progress` |

## 接下来先做什么

| 顺序 | 当前要做的事 |
| --- | --- |
| 1 | 关闭 `docs/policy/*.md -> .policy/` 与 `.growware/policies/*.json` 之间的 live truth drift。 |
| 2 | 跑 Growware activation baseline：`growware_policy_sync`、`growware_preflight`、binding preview、runtime mirror、doctor / smoke 和定向 tests。 |
| 3 | 明确 `openclaw_runtime_audit.py` 在当前 milestone 的边界，决定它是否进入下一条里程碑。 |

## 当前任务板

| 任务 | 类型 | 状态 |
| --- | --- | --- |
| 把当前 Growware 实现提升成正式 milestone，并让 roadmap / plan / status 对齐。 | 阶段收口 | 已完成 |
| 关闭 policy truth 裂缝。 | 边界收敛 | 进行中 |
| 验证 Growware activation baseline。 | 激活前验证 | 待执行 |
| 决定 host audit 的 milestone 边界。 | 路线裁剪 | 待决策 |
