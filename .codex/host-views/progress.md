# 项目进展

## 一眼总览

| 问题 | 当前答案 |
| --- | --- |
| 项目 | `OpenClaw Task System` |
| 当前判断 | `Milestone 2: Growware Project 1 pilot foundation` 已完成；当前主线是 `Milestone 3: system performance testing and optimization`。 |
| 当前阶段 | 性能基线阶段：先定义 benchmark surface、fixtures、预算和测量入口，再做热点归因与优化。 |
| 当前工作域 | runtime / control-plane / operator 性能基线 |
| 当前切片 | `performance baseline: measurement surface + reproducible entrypoints` |
| 当前执行进度 | `0 / 4` |
| 架构信号 | `黄色` |
| 直接价值 | 把下一阶段从“感觉哪里慢”切到“有 baseline、有热点归因、有回归门禁”的工程线。 |
| 当前主要风险 | benchmark surface、样本和预算还没冻结；如果过早优化，会重新制造不可比较的结果。 |

## 当前定位

| 维度 | 当前状态 | 说明 | 入口 |
| --- | --- | --- | --- |
| 主线状态 | `Milestone 3: system performance testing and optimization` 进行中 | Growware foundation 已完成，当前主线已经切到性能基线。 | [路线图](/Users/redcreen/Project/openclaw-task-system/docs/roadmap.zh-CN.md) |
| 当前阶段 | 基线定义、测量入口和热点归因 | 当前不做 live rollout，先把性能测量面收干净。 | [开发计划](/Users/redcreen/Project/openclaw-task-system/docs/reference/openclaw-task-system/development-plan.zh-CN.md) |
| 当前切片 | 性能基线当前切片 | 原始切片名：`performance baseline: measurement surface + reproducible entrypoints` | [状态](/Users/redcreen/Project/openclaw-task-system/.codex/status.md) |
| 当前执行线 | 先定义 benchmark surface，再采集 baseline，最后才允许优化 | 当前 checkpoint 重点是 PL-1 到 PL-4。 | [计划](/Users/redcreen/Project/openclaw-task-system/.codex/plan.md) |
| 当前 Gate | `提醒后继续` | 方向明确，但 benchmark contract 仍需持续可见。 | [状态 / 当前升级状态](/Users/redcreen/Project/openclaw-task-system/.codex/status.md:35) |

## 当前这轮到底在做什么

| 当前工作 | 类型 | 对维护者的直接价值 | 当前状态 | 对应任务 |
| --- | --- | --- | --- | --- |
| 关闭 Growware pilot foundation，并把 `.policy/` 写实为唯一 live policy truth | 阶段收口 | 让 M2 不再处于“半迁移”状态 | 已完成 | `Milestone 2` |
| 定义 runtime、control-plane 与 operator 的 benchmark surface、fixtures 和预算 | 基线定义 | 让性能工作有统一测量词汇和目标 | 进行中 | `PL-1` |
| 建立可复现测量入口 | 测量基础设施 | 让 baseline 可以稳定复跑，而不是靠个人本地习惯 | 待执行 | `PL-2` |
| 采集 baseline、归因热点并落第一轮有证据的优化 | 性能优化 | 让每次优化都有前后证据和回归保护 | 待执行 | `PL-3` / `PL-4` |

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
| 信号 | `黄色` |
| 根因假设 | 正确性与控制面此前已经收口，但性能证据还没有被定义成 durable 资产。 |
| 正确落层 | 用 milestone 级别的 benchmark surface、baseline 产物和回归门禁来约束优化。 |
| 自动触发 | runtime hot path、queue / delivery projection、SQLite / file-scan access、benchmark helpers 或 operator 入口发生变化时复核 |
| 升级 Gate | `提醒后继续` |

## 接下来要做什么

| 下一步 | 为什么做 | 对应入口 |
| --- | --- | --- |
| 定义 benchmark surface、fixtures 和预算 | 让性能工作从一开始就可比较、可复核 | [计划](/Users/redcreen/Project/openclaw-task-system/.codex/plan.md) |
| 建立可复现测量命令 | 避免 baseline 依赖临时命令和个人习惯 | [开发计划](/Users/redcreen/Project/openclaw-task-system/docs/reference/openclaw-task-system/development-plan.zh-CN.md:74) |
| 在 baseline capture 前后保持 runtime-safety 验证栈全绿 | 防止性能阶段破坏刚收口的 Growware foundation | [路线图](/Users/redcreen/Project/openclaw-task-system/docs/roadmap.zh-CN.md:29) |
