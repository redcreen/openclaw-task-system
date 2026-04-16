[English](roadmap.md) | [中文](roadmap.zh-CN.md)

# OpenClaw Task System 路线图

## 状态

主线 roadmap 已经完成到 Phase 6 最小闭环和 `Milestone 1：post-hardening 收口`。

当前里程碑状态已经切换为：

- `Milestone 2：Growware Project 1 pilot foundation` 已完成
- `Milestone 3：系统性能测试与优化` 已完成
- `性能基线收口后的 live pilot activation 准备` 已激活

## 总体进展

| 项目 | 当前值 |
| --- | --- |
| 主线进度 | 主线已经完成到 `Milestone 3`；仓库当前进入有界 activation 准备，而不是继续无限期做性能调优 |
| 当前阶段 | `性能基线收口后的 live pilot activation 准备` |
| 当前目标 | 在已收口的性能基线上重新打开 live pilot activation 准备，而不是让 Milestone 3 继续停留在 open-ended tuning bucket |
| 明确下一步动作 | `AP-1` 定义 activation rehearsal 入口条件与必须采集的 operator evidence 包 |
| 下一候选动作 | 在入口条件、install-sync 意图和 rollback 边界都显式后，运行一轮有界的 `feishu6-chat` live activation rehearsal |

查看详细执行计划：[reference/openclaw-task-system/development-plan.zh-CN.md](reference/openclaw-task-system/development-plan.zh-CN.md)

已完成的主线里程碑：

- Phase 0：项目定义与边界
- Phase 1：协议与真相源对齐
- Phase 2：最小 control-plane lane 与 scheduler evidence
- Phase 3：统一的用户可见状态投影
- Phase 4：producer contract 与 same-session 语义
- Phase 5：channel rollout 与 acceptance
- Phase 6 最小闭环：supervisor-first planning runtime
- Milestone 1：post-hardening 收口
- Milestone 2：Growware Project 1 pilot foundation
- Milestone 3：系统性能测试与优化

## 主线产出

主线已经交付：

- runtime-owned 的 `[wd]` 与 control-plane delivery
- 统一的 queue identity 与 task 真相源
- channel acceptance matrix 与 producer contract
- same-session message routing
- planning 最小闭环与 future-first output control
- continuity、watchdog 与 recovery visibility
- doctor、ops 与 stable acceptance 里的 install drift 可见性

## Milestone 2 收口结果

Milestone 2 已经正式收口，当前结论是：

- `.growware/` 已经成为 Growware `Project 1` 的项目本地控制面，`feishu6-chat` 是主反馈 / 审批 / 通知入口
- `docs/policy/*.md` 已经成为人类 policy source，`.policy/` 已经成为 Growware 运行时决策消费的编译机器层
- `growware_feedback_classifier.py`、`growware_project.py`、`growware_preflight.py` 和 `growware_local_deploy.py` 已经收敛到编译后的 policy layer
- 遗留 `.growware/policies/*.json` 已从 live control surface 退役，不再作为 runtime / preflight 的真相输入
- `openclaw_runtime_audit.py` 保持在只读宿主侧体检 bootstrap 边界内，没有被升级成 repair 或 rollout gate
- reviewed activation baseline 已经在编译后的 `.policy/` 路径上复核通过

## Milestone 3 收口结果

Milestone 3 已经正式收口，当前结论是：

- `scripts/runtime/performance_baseline.py` 已经把 runtime、control-plane 和 operator surface 收敛成可复现的 repo-local benchmark / profile 合同
- `docs/reference/openclaw-task-system/performance-baseline*.md` 已经固定 fixtures、预算、热点归因和优化证据，不再让性能工作散落在临时命令输出里
- reviewed 热点优化已经沉淀成仓库真相：`system-overview` 从约 `484ms` median 降到约 `18ms`，注册路径重扫被压到单次 inflight snapshot，repo 自带 same-session classifier 从约 `90ms` / `132ms` 收到约 `25ms` / `39ms`
- 结构性回归测试和 benchmark budget 已经保护这些改进路径，而且没有重新打开 runtime truth 或控制面漂移
- `plugin_doctor.py` 里的 installed-runtime drift 仍然保持可见，但它被留在 activation 准备阶段单独决策，而不是被混进 repo-local 性能里程碑里当隐形 blocker

## 当前 / 下一步 / 更后面

| 时间层级 | 重点 | 退出信号 |
| --- | --- | --- |
| 当前 | 执行 `性能基线收口后的 live pilot activation 准备` | 在任何有界 rehearsal 之前，把激活入口条件、operator evidence 预期和 install-sync 决策写成显式真相 |
| 下一步 | 运行有界的 `feishu6-chat` live activation rehearsal | rehearsal evidence 建立在 repo-local 验证全绿和明确 rollback 边界之上 |
| 更后面 | 再考虑保守 self-heal、更强 planning / steering 与更高保真的 real-channel evidence | 新工作不会重新打开 policy ownership drift，也不会绕过 runtime truth 和审批边界 |

## 里程碑

| 里程碑 | 状态 | 目标 | 依赖 | 退出条件 |
| --- | --- | --- | --- | --- |
| Phase 0-2 | 已完成 | 建立基础 task runtime、注册、状态与最小控制面行为 | plugin/runtime 基础接线 | 长任务使用同一套 task 真相 |
| Phase 3-4 | 已完成 | 加入 delayed reply、watchdog、continuity 与 host delivery | continuity 与 scheduler evidence chain | 重启与恢复路径可解释 |
| Phase 5 | 已完成 | 强化 dashboard、queues、lanes、triage 与 operator 投影 | main ops 工具链 | 用户视角与 operator 视角使用同一套真相 |
| Phase 6 最小闭环 | 已完成 | 固定 planning acceptance、future-first output 与 same-session routing 的最小发货闭环 | planning acceptance 工具链 | 自动化与半真实 acceptance 持续全绿 |
| Milestone 1：post-hardening 收口 | 已完成 | 收掉剩余 compound / future-first 边界、补 release-facing evidence，并完成 operator-facing 收尾 | 主线稳定与 release-facing 验证入口 | 边界文档、acceptance 深度与 operator / release-facing 收尾已经收敛，且没有重新打开架构债务 |
| Milestone 2：Growware Project 1 pilot foundation | 已完成 | 把 Growware `Project 1` 从未来候选变成仓库内可维护的正式基线，收敛项目本地 policy 真相、激活 gate 与 host-audit bootstrap | `.growware/`、`docs/policy/`、`.policy/`、Growware runtime scripts、binding preview、session hygiene 与验证入口 | 编译后的 `.policy` 成为唯一 live runtime input，激活安全边界文档化且全绿，host-audit bootstrap 也有明确边界 |
| Milestone 3：系统性能测试与优化 | 已完成 | 为 runtime、control-plane 与 operator 入口建立可复现性能基线，识别热点并做有证据的优化 | Milestone 2 收口、稳定的基线命令、可复现样本数据和性能测量入口 | 已经有 benchmark / profile 基线、主要热点归因、优化结果与回归门禁，且没有破坏 runtime truth 与控制面边界 |

## 后续候选方向

当前 activation 准备线之后的潜在候选包括：

- Growware pilot 的真实激活，以及围绕 `feishu6-chat` 的端到端证据捕获
- 基于 `openclaw_runtime_audit.py` 的保守 repair planning / self-heal
- 面向更广 compound request 的更强 structured planning / tool decomposition
- 当 delivery 或 planning contract 变化时补更高保真的 real-channel evidence
- 在不破坏 runtime truth 与 supervisor-first 边界的前提下，继续深化 steering 或 operator ergonomics

架构整改主线仍然保持这两条明确决定：

- `lifecycle_coordinator.py` 拥有 runtime lifecycle projection
- `scripts/runtime/` 是 canonical source，而 `plugin/scripts/runtime/` 是严格同步镜像

参考入口：

- [workstreams/architecture-hardening/README.zh-CN.md](workstreams/architecture-hardening/README.zh-CN.md)
- [reference/openclaw-task-system/development-plan.zh-CN.md](reference/openclaw-task-system/development-plan.zh-CN.md)
- [reference/openclaw-task-system/growware-pilot.zh-CN.md](reference/openclaw-task-system/growware-pilot.zh-CN.md)
- [reference/openclaw-task-system/runtime-audit-self-heal-proposal.zh-CN.md](reference/openclaw-task-system/runtime-audit-self-heal-proposal.zh-CN.md)

## 已交付子专题：Same-Session Message Routing

这个已发货能力定义了同一 session 连续消息如何在下面几类路径里路由：

- `steering`
- `queueing`
- `control-plane`
- `collect-more`

运行时行为：

1. runtime 先判断当前 task 状态
2. 只有边界模糊时才调用 runtime-owned 的结构化 classifier
3. runtime 再决定执行动作，例如：
   - `merge-before-start`
   - `interrupt-and-restart`
   - `append-as-next-step`
   - `queue-as-new-task`
   - `enter-collecting-window`
4. 每个 routing 决策都会返回 runtime-owned 的 `[wd]` 回执

入口文档：

- [reference/session_message_routing/README.zh-CN.md](reference/session_message_routing/README.zh-CN.md)
- [reference/session_message_routing/decision_contract.zh-CN.md](reference/session_message_routing/decision_contract.zh-CN.md)
- [reference/session_message_routing/test_cases.zh-CN.md](reference/session_message_routing/test_cases.zh-CN.md)
- [reference/session_message_routing/development_plan.zh-CN.md](reference/session_message_routing/development_plan.zh-CN.md)

## 工作规则

`docs/todo.md` 只是临时 intake 文件。

真正的 delivery 主线仍以这份 roadmap 为准。
