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
| 当前 | 保持 Phase 0-6 主线稳定，确保 `[wd]`、control-plane、continuity、planning acceptance 持续全绿 | 自动化 testsuite 继续稳定，真实或半真实验收不出现回退 |
| 下一步 | 收口 compound follow-up 与 future-first 相关边界，把“监工优先”语义固定到文档和运维工具 | 复杂 follow-up 不再依赖临时解释，运行时与用户投影保持一致 |
| 更后面 | 评估更强的 planning / steering 能力，但仍保持 task-system 不替代原执行器 | 新能力不会破坏 `[wd]` 独立、高优先级和真相源一致性 |

## 里程碑
| 里程碑 | 状态 | 目标 | 依赖 | 退出条件 |
| --- | --- | --- | --- | --- |
| Phase 0-2 | 已完成 | 建立基础 task runtime、注册、状态与基本控制面 | plugin/runtime 基础接线 | 长任务有统一 task 真相 |
| Phase 3-4 | 已完成 | 引入 delayed reply、watchdog、continuity、host delivery | continuity 与 scheduler 证据链 | 重启和恢复路径可解释 |
| Phase 5 | 已完成 | 强化 dashboard、queues、lanes、triage 等运维投影 | main ops 工具链 | 用户视角与运维视角使用同一套真相 |
| Phase 6 最小闭环 | 已完成 | 固定 planning acceptance、future-first、same-session routing 的最小闭环 | planning acceptance 工具链 | 自动化与半真实验收持续全绿 |
| Milestone 1：post-hardening 收口 | 下一里程碑 / 长任务 | 一口气收紧复杂 follow-up、compound planning、用户内容分离与 release-facing 收尾 | 现有主线稳定与 release-facing 验证入口 | 剩余事项要么已交付，要么已归档，要么被明确拆成新的 roadmap candidate |

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

## 当前整改专项

当前除了继续保持主线稳定外，架构整改专项已经收口为两条明确决定：

- `lifecycle_coordinator.py` 拥有 runtime lifecycle projection
- `scripts/runtime/` 是 canonical source，而 `plugin/scripts/runtime/` 是严格同步镜像

入口文档：

- [workstreams/architecture-hardening/README.zh-CN.md](workstreams/architecture-hardening/README.zh-CN.md)
- [reference/openclaw-task-system/development-plan.zh-CN.md](reference/openclaw-task-system/development-plan.zh-CN.md)
