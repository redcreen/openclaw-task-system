# 项目进展

## 一眼总览

| 问题 | 当前答案 |
| --- | --- |
| 项目 | `OpenClaw Task System` |
| 当前判断 | `Milestone 2` 与 `Milestone 3` 已完成；当前主线是 `post-performance live pilot activation preparation`。 |
| 当前阶段 | activation 准备阶段：先固定 evidence、install-sync 和 rollback 边界，再进入第一次有界 rehearsal。 |
| 当前工作域 | activation prep / operator evidence / deploy boundary |
| 当前切片 | `activation-prep entry criteria + install-sync decision` |
| 当前执行进度 | `0 / 3` |
| 架构信号 | `绿色` |
| 直接价值 | 把下一阶段从“性能已优化但怎么启动 rehearsal 还模糊”切到“入口条件、证据和 rollback 都明确”的工程线。 |
| 当前主要风险 | 如果 activation 入口条件和 install-sync 意图不先写清，rehearsal 会重新掉回模糊边界。 |

## 当前定位

| 维度 | 当前状态 | 说明 | 入口 |
| --- | --- | --- | --- |
| 主线状态 | `post-performance live pilot activation preparation` 进行中 | Growware foundation 和性能里程碑都已完成，当前主线切到 activation 准备。 | [路线图](/Users/redcreen/Project/openclaw-task-system/docs/roadmap.zh-CN.md) |
| 当前阶段 | activation entry criteria、install-sync 与 rehearsal 风险控制 | 当前不直接进入 live rehearsal，先把边界写清。 | [开发计划](/Users/redcreen/Project/openclaw-task-system/docs/reference/openclaw-task-system/development-plan.zh-CN.md) |
| 当前切片 | activation 准备当前切片 | 原始切片名：`activation-prep entry criteria + install-sync decision` | [状态](/Users/redcreen/Project/openclaw-task-system/.codex/status.md) |
| 当前执行线 | 先定 activation evidence 与 rollback，再决定 install-sync，最后才进入 rehearsal | 当前 checkpoint 重点是 AP-1 到 AP-3。 | [计划](/Users/redcreen/Project/openclaw-task-system/.codex/plan.md) |
| 当前 Gate | `自动继续` | 方向明确；只有真实 deploy 或 live rehearsal 才升级。 | [状态 / 当前升级状态](/Users/redcreen/Project/openclaw-task-system/.codex/status.md:35) |

## 当前这轮到底在做什么

| 当前工作 | 类型 | 对维护者的直接价值 | 当前状态 | 对应任务 |
| --- | --- | --- | --- | --- |
| 收口 Growware pilot foundation，并把 `.policy/` 写实为唯一 live policy truth | 阶段收口 | 让 M2 不再处于“半迁移”状态 | 已完成 | `Milestone 2` |
| 收口性能里程碑，并把 benchmark / 优化 / 回归门禁写实为已完成 | 阶段收口 | 让 M3 不再处于“永远还有下一个 hotspot”的状态 | 已完成 | `Milestone 3` |
| 定义 activation 入口条件和 operator evidence 包 | rehearsal 准备 | 让首轮 rehearsal 有明确进入条件 | 进行中 | `AP-1` |
| 决定 install-sync 路径与 rollback 规则 | 风险控制 | 让 rehearsal 不会在 deploy 边界上模糊推进 | 待执行 | `AP-2` / `AP-3` |

## 已完成的阶段产出

| 能力 | 当前状态 | 对应实现 |
| --- | --- | --- |
| Growware 项目本地控制面 | 已落地 | `.growware/`、Growware pilot 文档、渠道绑定信息 |
| 人类 policy source 与编译机器层 | 已落地 | `docs/policy/*.md`、`.policy/`、`growware_policy_sync.py` |
| 编译 policy 的运行时消费 | 已落地 | `growware_feedback_classifier.py`、`growware_project.py`、`growware_preflight.py`、`growware_local_deploy.py` |
| 宿主侧只读体检 bootstrap | 已落地 | `openclaw_runtime_audit.py` 与对应 tests |
| 遗留 `.growware/policies/*.json` 退役 | 已完成 | runtime / preflight 不再依赖旧 JSON |

## 架构监督

| 项目 | 当前值 |
| --- | --- |
| 信号 | `绿色` |
| 根因假设 | 当前风险已经从“没有 baseline”转成“activation 边界如果不写清，就会在下一阶段重新模糊”。 |
| 正确落层 | 用 activation entry criteria、install-sync intent 和 rollback 规则来约束 rehearsal。 |
| 自动触发 | live activation scope、install drift、local deploy intent、benchmark budget 或 operator 入口发生变化时复核 |
| 升级 Gate | `自动继续` |

## 接下来要做什么

| 下一步 | 为什么做 | 对应入口 |
| --- | --- | --- |
| 定义 activation entry criteria 和 operator evidence 包 | 让第一次 rehearsal 不是“已经想开始了再补规则” | [计划](/Users/redcreen/Project/openclaw-task-system/.codex/plan.md) |
| 判断 installed-runtime drift 是否需要先清掉 | 让 deploy 边界和 repo-only 边界继续保持清晰 | [开发计划](/Users/redcreen/Project/openclaw-task-system/docs/reference/openclaw-task-system/development-plan.zh-CN.md:121) |
| 在 rehearsal 前继续保持 benchmark 与 runtime-safety 验证栈全绿 | 防止 activation 准备破坏刚收口的性能与 Growware foundation | [路线图](/Users/redcreen/Project/openclaw-task-system/docs/roadmap.zh-CN.md:69) |
