[English](roadmap.md) | [中文](roadmap.zh-CN.md)

# OpenClaw Task System 路线图

## 范围

当前 roadmap 关注主线交付，而不是临时想法收集。它回答：

- 现在项目已经做到哪一层
- 当前还保留哪些明确边界
- 下一次继续推进时，优先收哪一类问题

## 当前 / 下一步 / 更后面
| 时间层级 | 重点 | 退出信号 |
| --- | --- | --- |
| 当前 | 保持 Phase 0-6 主线和 post-hardening 收口稳定，确保 `[wd]`、control-plane、continuity、planning acceptance 持续全绿 | 自动化 testsuite、release gate 与 dated evidence workflow 持续稳定 |
| 下一步 | 只有当新能力被命名成明确 roadmap candidate 时，才继续评估更强的 planning / steering 能力 | 新能力不会破坏 `[wd]` 独立、高优先级和真相源一致性 |
| 更后面 | 只有当真实需求成型时，才把更高保真 evidence 或更深 operator UX 推成正式候选 | 扩展工作不会重新退化成泛化 closeout debt |

## 里程碑
| 里程碑 | 状态 | 目标 | 依赖 | 退出条件 |
| --- | --- | --- | --- | --- |
| Phase 0-2 | 已完成 | 建立基础 task runtime、注册、状态与基本控制面 | plugin/runtime 基础接线 | 长任务有统一 task 真相 |
| Phase 3-4 | 已完成 | 引入 delayed reply、watchdog、continuity、host delivery | continuity 与 scheduler 证据链 | 重启和恢复路径可解释 |
| Phase 5 | 已完成 | 强化 dashboard、queues、lanes、triage 等运维投影 | main ops 工具链 | 用户视角与运维视角使用同一套真相 |
| Phase 6 最小闭环 | 已完成 | 固定 planning acceptance、future-first、same-session routing 的最小闭环 | planning acceptance 工具链 | 自动化与半真实验收持续全绿 |
| Milestone 1：post-hardening 收口 | 已完成 | 一口气收紧复杂 follow-up、compound planning、用户内容分离与 release-facing 收尾 | 现有主线稳定与 release-facing 验证入口 | 边界文档、acceptance 深度与 operator/release-facing 收尾已收敛，且没有重新打开架构债务 |

## 里程碑流转

```mermaid
flowchart LR
    P0["P0-P2 基础运行时"] --> P34["P3-P4 continuity / delivery"]
    P34 --> P5["P5 运维投影"]
    P5 --> P6["P6 planning acceptance 最小闭环"]
    P6 --> N["后续边界收口"]
```

## 风险与依赖

- 不改 OpenClaw core 仍然是硬边界
- receive-time ack 受宿主与 channel 能力限制
- compound 请求长期仍需要更强 planning，而不是继续扩 regex
- 发布前必须持续跑 testsuite、plugin doctor、plugin smoke 与 acceptance 工具链

## 后续候选方向

当前已经没有活跃的 post-hardening closeout 欠账。

如果后面继续做扩展能力，应该先命名成新的候选，而不是继续挂成“顺手再补一点”的临时项。

潜在候选方向：

- Growware `Project 1` pilot：把 `feishu6-chat`、项目内 `.growware/`、本地 deploy gate 和专用 `growware` agent 接上，验证 feedback -> code -> verify -> deploy 的本地闭环
- 为更广泛的 compound request 引入更强的 structured planning / tool decomposition
- 当 delivery 或 planning contract 变化时，补更高保真的 real-channel evidence
- 在不破坏 runtime truth 与 supervisor-first 边界的前提下，继续深化 steering 或 operator ergonomics

架构整改专项目前保持这两条明确决定：

- `lifecycle_coordinator.py` 拥有 runtime lifecycle projection
- `scripts/runtime/` 是 canonical source，而 `plugin/scripts/runtime/` 是严格同步镜像

入口文档：

- [workstreams/architecture-hardening/README.zh-CN.md](workstreams/architecture-hardening/README.zh-CN.md)
- [reference/openclaw-task-system/development-plan.zh-CN.md](reference/openclaw-task-system/development-plan.zh-CN.md)
- [reference/openclaw-task-system/growware-pilot.zh-CN.md](reference/openclaw-task-system/growware-pilot.zh-CN.md)
