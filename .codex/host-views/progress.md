# 项目进展

## 一眼总览

| 问题 | 当前答案 |
| --- | --- |
| 项目 | `OpenClaw Task System` |
| 当前判断 | 主线不再是稳态维护；`Milestone 2: Growware Project 1 pilot foundation` 已经正式打开。 |
| 当前阶段 | Growware pilot foundation：收敛 policy 真相、activation gate 和 host-audit bootstrap。 |
| 当前工作域 | Growware 项目本地控制面与激活基线 |
| 当前切片 | `growware pilot: policy truth + activation baseline` |
| 当前执行进度 | `1 / 4` |
| 架构信号 | `黄色` |
| 直接价值 | 把已经落地的 Growware 代码与文档收敛成可维护里程碑，而不是继续挂成 future candidate。 |
| 当前主要风险 | `.policy/` 与 `.growware/policies/*.json` 之间仍有兼容层漂移。 |

## 当前定位

| 维度 | 当前状态 | 说明 | 入口 |
| --- | --- | --- | --- |
| 主线状态 | `Milestone 2: Growware Project 1 pilot foundation` 进行中 | 当前主线已经从“观察新候选”切到 Growware 当前实现收口。 | [路线图](/Users/redcreen/Project/openclaw-task-system/docs/roadmap.zh-CN.md) |
| 当前阶段 | policy 真相、激活安全性和 host-audit 定位收口 | 当前不做 live rollout，先把基础边界收干净。 | [开发计划](/Users/redcreen/Project/openclaw-task-system/docs/reference/openclaw-task-system/development-plan.zh-CN.md) |
| 当前切片 | Growware pilot 当前切片 | 原始切片名：`growware pilot: policy truth + activation baseline` | [状态](/Users/redcreen/Project/openclaw-task-system/.codex/status.md) |
| 当前执行线 | 先把 Growware foundation 变成可验证的 pilot baseline | 当前 checkpoint 重点是 EL-2 到 EL-4。 | [计划](/Users/redcreen/Project/openclaw-task-system/.codex/plan.md) |
| 当前 Gate | `提醒后继续` | 方向明确，但 policy truth 与 activation boundary 仍需持续可见。 | [状态 / 当前升级状态](/Users/redcreen/Project/openclaw-task-system/.codex/status.md:39) |

## 当前这轮到底在做什么

| 当前工作 | 类型 | 对维护者的直接价值 | 当前状态 | 对应任务 |
| --- | --- | --- | --- | --- |
| 把 Growware 当前实现从 future candidate 正式提升为 roadmap milestone | 阶段收口 | 让 roadmap、plan、status 和真实代码实现一致 | 已完成 | `EL-1` |
| 关闭 `docs/policy/*.md -> .policy/` 与 `.growware/policies/*.json` 之间的真相源裂缝 | 边界收敛 | 让维护者只需要认一条 live policy truth | 进行中 | `EL-2` |
| 跑通 policy sync、preflight、binding preview、mirror、doctor / smoke 与 session hygiene 的同一条激活基线 | 激活前验证 | 避免每个入口各自看起来能用，但合起来不可运营 | 待执行 | `EL-3` |
| 明确 `openclaw_runtime_audit.py` 是当前 bootstrap 还是下一条 milestone 的入口 | 路线裁剪 | 避免 host audit 在没有批准边界时悄悄膨胀成 repair 系统 | 待决策 | `EL-4` |

## 已完成的阶段产出

| 能力 | 当前状态 | 对应实现 |
| --- | --- | --- |
| Growware 项目本地控制面 | 已落地 | `.growware/`、Growware pilot 文档、渠道绑定信息 |
| 人类 policy source 与编译机器层 | 已落地 | `docs/policy/*.md`、`.policy/`、`growware_policy_sync.py` |
| 编译 policy 的运行时消费 | 已落地 | `growware_feedback_classifier.py`、`growware_project.py`、`growware_preflight.py`、`growware_local_deploy.py` |
| 宿主侧只读体检 bootstrap | 已落地 | `openclaw_runtime_audit.py` 与对应 tests |

## 架构监督

| 项目 | 当前值 |
| --- | --- |
| 信号 | `黄色` |
| 根因假设 | Growware pilot 实现已经落地，但 roadmap 和控制面此前还停留在“未来候选”，导致 policy 与 activation gate 的边界描述不够明确。 |
| 正确落层 | 用 milestone 级别的 control surface 收敛 policy 真相、operator gate 与 host audit 边界。 |
| 自动触发 | `.policy/`、`.growware/`、binding flow、session hygiene 或 host-audit scope 发生变化时复核 |
| 升级 Gate | `提醒后继续` |

## 接下来要做什么

| 下一步 | 为什么做 | 对应入口 |
| --- | --- | --- |
| 关闭 `.policy/` 与 `.growware/policies/*.json` 的 live truth drift | 让 Growware runtime 只认一条 policy 真相 | [计划](/Users/redcreen/Project/openclaw-task-system/.codex/plan.md) |
| 运行 Growware activation baseline 的整套验证 | 证明当前基础可以安全进入下一阶段 | [开发计划 / 验证栈](/Users/redcreen/Project/openclaw-task-system/docs/reference/openclaw-task-system/development-plan.zh-CN.md:74) |
| 决定 host audit 是 bootstrap 还是下一里程碑入口 | 避免当前里程碑边界再次模糊 | [路线图 / 后续候选方向](/Users/redcreen/Project/openclaw-task-system/docs/roadmap.zh-CN.md:60) |
