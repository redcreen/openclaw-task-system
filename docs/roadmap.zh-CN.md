[English](roadmap.md) | [中文](roadmap.zh-CN.md)

# OpenClaw Task System 路线图

## 状态

主线 roadmap 已经完成到 Phase 6 最小闭环和 `Milestone 1：post-hardening 收口`。

现在已经正式打开新的命名里程碑：

- `Milestone 2：Growware Project 1 pilot foundation`

已完成的主线里程碑：

- Phase 0：项目定义与边界
- Phase 1：协议与真相源对齐
- Phase 2：最小 control-plane lane 与 scheduler evidence
- Phase 3：统一的用户可见状态投影
- Phase 4：producer contract 与 same-session 语义
- Phase 5：channel rollout 与 acceptance
- Phase 6 最小闭环：supervisor-first planning runtime
- Milestone 1：post-hardening 收口

## 主线产出

主线已经交付：

- runtime-owned 的 `[wd]` 与 control-plane delivery
- 统一的 queue identity 与 task 真相源
- channel acceptance matrix 与 producer contract
- same-session message routing
- planning 最小闭环与 future-first output control
- continuity、watchdog 与 recovery visibility
- doctor、ops 与 stable acceptance 里的 install drift 可见性

## Growware Pilot 阶段快照

这一阶段已经落地：

- `.growware/` 已经成为 Growware `Project 1` 的项目本地控制面，`feishu6-chat` 是主反馈 / 审批 / 通知入口
- `docs/policy/*.md` 已经成为人类 policy source，`.policy/` 已经成为 Growware 运行时决策消费的编译机器层
- `growware_feedback_classifier.py`、`growware_project.py`、`growware_preflight.py` 和 `growware_local_deploy.py` 已经开始消费或强制校验编译后的 policy layer
- `openclaw_runtime_audit.py` 已经提供一个基于真实 `~/.openclaw` 数据的只读宿主侧体检 bootstrap

在进入激活前还要收口的边界：

- 关掉编译后的 `.policy/` 与遗留 `.growware/policies/*.json` 之间剩余的真相源裂缝
- 用一条干净基线跑通 policy sync、preflight、binding preview、runtime mirror、doctor / smoke 与 session hygiene
- 决定只读 host audit 是否足以作为 Milestone 2 的组成部分，还是应该升成下一个命名里程碑

## 当前 / 下一步 / 更后面

| 时间层级 | 重点 | 退出信号 |
| --- | --- | --- |
| 当前 | 收口 `Milestone 2：Growware Project 1 pilot foundation`，把 policy 真相、pilot 激活安全性和 host audit 定位收敛起来 | 编译后的 `.policy/` 成为唯一 live intake / deploy 真相，激活检查持续全绿，运维侧也有一套统一的基线命令入口 |
| 下一步 | 只有在 foundation gate 干净后，才激活 `feishu6-chat` 上的本地 feedback -> code -> verify -> deploy pilot | binding preview、session hygiene 和 local deploy 都能在没有未解漂移或宿主阻塞的前提下演练 |
| 更后面 | 只有在 pilot baseline 稳定后，才考虑保守自修复和更强 planning / steering | 新工作不会重新打开隐藏 ownership drift，也不会绕过 runtime truth |

## 里程碑

| 里程碑 | 状态 | 目标 | 依赖 | 退出条件 |
| --- | --- | --- | --- | --- |
| Phase 0-2 | 已完成 | 建立基础 task runtime、注册、状态与最小控制面行为 | plugin/runtime 基础接线 | 长任务使用同一套 task 真相 |
| Phase 3-4 | 已完成 | 加入 delayed reply、watchdog、continuity 与 host delivery | continuity 与 scheduler evidence chain | 重启与恢复路径可解释 |
| Phase 5 | 已完成 | 强化 dashboard、queues、lanes、triage 与 operator 投影 | main ops 工具链 | 用户视角与 operator 视角使用同一套真相 |
| Phase 6 最小闭环 | 已完成 | 固定 planning acceptance、future-first output 与 same-session routing 的最小发货闭环 | planning acceptance 工具链 | 自动化与半真实 acceptance 持续全绿 |
| Milestone 1：post-hardening 收口 | 已完成 | 收掉剩余 compound / future-first 边界、补 release-facing evidence，并完成 operator-facing 收尾 | 主线稳定与 release-facing 验证入口 | 边界文档、acceptance 深度与 operator / release-facing 收尾已经收敛，且没有重新打开架构债务 |
| Milestone 2：Growware Project 1 pilot foundation | 进行中 | 把 Growware `Project 1` 从未来候选变成仓库内可维护的正式基线，收敛项目本地 policy 真相、激活 gate 与 host-audit bootstrap | `.growware/`、`docs/policy/`、`.policy/`、Growware runtime scripts、binding preview、session hygiene 与验证入口 | 项目本地 policy 成为唯一 live runtime input，激活安全边界文档化且全绿，host-audit bootstrap 也有明确的 milestone 边界 |

## 后续候选方向

`Milestone 2` 现在已经是 active work，不应该继续当成“顺手补一下”的候选。

Milestone 2 之后的潜在候选包括：

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
- [reference/openclaw-task-system/development-plan.zh-CN.md](reference/openclaw-task-system/development-plan.zh-CN.md#milestone-2-growware-project-1-pilot-foundation)
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
