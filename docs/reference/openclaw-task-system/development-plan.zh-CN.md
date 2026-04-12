[English](development-plan.md) | [中文](development-plan.zh-CN.md)

# Development Plan

## 目的

这份计划文档位于 roadmap 和 `.codex/plan.md` 之间。

它用来回答三件事：

- 最近一个项目级里程碑是怎样收口的
- 它靠什么验证关闭
- 什么时候才应该重新开新的项目级里程碑

## 当前定位

仓库现在已经完成：

- Phase 0-6 最小闭环
- 架构整改收口
- 双语公开文档收敛
- `Milestone 1：post-hardening 收口`

当前没有新的项目级活跃里程碑。

这份计划现在主要记录刚完成的 closeout 里程碑，以及下次重新开新里程碑的规则。

## 里程碑总览

| 里程碑 | 状态 | 目标 | 验证 | 退出条件 |
| --- | --- | --- | --- | --- |
| Milestone 1：post-hardening 收口 | 已完成 | 收紧 compound / future-first 边界、补足 release-facing 证据深度，并把仓库带到干净的 post-hardening 状态 | `bash scripts/run_tests.sh`、`python3 scripts/runtime/release_gate.py --json`、planning / channel / main-ops acceptance helpers、文档一致性检查 | 边界文档、acceptance 深度与 operator/release-facing 收尾已经收敛，且没有重新打开架构债务 |

## 已完成的收口队列

### 1. 边界收敛

已交付：

- compound follow-up 文档现在描述的是已发货 runtime 边界，而不是开放设计占位
- output-channel separation 文档现在与当前 runtime contract 一致，不再把 `task_user_content` 写成现役长期协议
- same-session routing 决策文档现在把 `collect-more` 说明为已发货的非普通任务路径
- 用户可见状态与 runtime-owned 状态投影在活跃文档栈里已经统一

结果：

- 文档与 runtime 行为现在描述的是同一条边界
- 主文档栈不再依赖模糊的“临时兼容”说法解释已交付行为

### 2. 证据深度

已交付：

- planning acceptance 现在显式证明：已排定的 follow-up 摘要仍留在控制面投影里，不会混进业务内容
- channel acceptance 现在包含 `webchat` 的 bounded-focus 样本
- main-ops acceptance 现在补上了 `followup-task-missing` 的运维恢复投影样本

结果：

- 剩余高风险区域不再只靠 summary-only 文案支撑

### 3. 运维与发布侧收口

已交付：

- operator 与 release-facing 文档现在指向同一套验证入口
- roadmap、README、todo intake 和控制面文档现在指向同一个 post-closeout 状态
- archive 与 promotion guidance 继续和 planning evidence workflow 保持一致

结果：

- 运维人员可以从同一套命令集完成 recovery、triage 与 validation
- 发布文档不再指向半完成或重复的指导

### 4. 下次重新开题的规则

只有满足下面三条时，才重新开一个新的项目级里程碑：

1. 扩展工作从 `docs/todo.md` 升级成一个有名字的 roadmap candidate
2. 这个候选已经有明确验证和退出条件
3. 如果不显式命名，仓库就会重新开始积累泛化 follow-up debt

在那之前，稳态入口应以 `roadmap.md`、`test-plan.md` 和 `.codex/status.md` 为准。

## 验证栈

关闭这条里程碑时使用的验证栈：

```bash
bash scripts/run_tests.sh
python3 scripts/runtime/release_gate.py --json
python3 scripts/runtime/planning_acceptance_suite.py --json
python3 scripts/runtime/channel_acceptance.py --json
python3 scripts/runtime/main_ops_acceptance.py --json
```

之后如果新的改动再次触及真实外发或 planning contract，仍应补真实或半真实 evidence capture。
