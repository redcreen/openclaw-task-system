[English](development-plan.md) | [中文](development-plan.zh-CN.md)

# Development Plan

## 目的

这份计划文档位于 roadmap 和 `.codex/plan.md` 之间。

它用来回答三件事：

- 项目级下一里程碑是什么
- 这个里程碑应该怎么执行
- 在什么验证通过后，才能把这条 slice 真正收口

## 当前定位

仓库已经完成：

- Phase 0-6 最小闭环
- 架构整改收口
- 双语公开文档收敛

当前项目级下一里程碑是：

- `Milestone 1：post-hardening 收口`

这条里程碑默认按“一口气执行的长任务”来推进，而不是重新拆回很多零散小收尾。

## 里程碑总览

| 里程碑 | 状态 | 目标 | 验证 | 退出条件 |
| --- | --- | --- | --- | --- |
| Milestone 1：post-hardening 收口 | 下一里程碑 | 收紧 compound / future-first 边界、补足 release-facing 证据深度，并把仓库带到干净的 post-hardening 状态 | `bash scripts/run_tests.sh`、`python3 scripts/runtime/release_gate.py --json`、planning / channel / main-ops acceptance helpers、文档一致性检查 | 剩余工作要么已经交付，要么已经归档，要么被明确转移成新的 roadmap candidate，而不是继续挂成泛化 follow-up |

## 顺序执行队列

### 1. 边界收敛

先把这些产品与 runtime 边界收紧：

- compound follow-up
- future-first planning 预期
- output-channel separation
- 用户可见状态与 runtime-owned 状态投影

退出信号：

- 文档和 runtime 行为描述的是同一条边界
- 主文档栈里不再依赖模糊的“临时兼容”说法去解释已交付行为

### 2. 证据深度

补足当前仍然偏薄的 release-facing 证据：

- planning acceptance evidence depth
- channel acceptance sample depth
- 当前文档明确写出仍偏弱的真实或半真实 dated record

退出信号：

- 剩余高风险区域不再只靠一条 dated record 或 summary-only 文案支撑

### 3. 运维与发布侧收口

完成维护者侧的最后收口：

- operator snapshot 与 runbook 对齐
- release gate 文案与入口命令对齐
- archive 与 promotion guidance 一致

退出信号：

- 运维人员可以从同一套命令集完成 recovery、triage 与 validation
- 发布文档不再指向半完成或重复的指导

### 4. 最终收口

在宣布这条 milestone 完成前，再做一次总收敛：

- 刷新 roadmap、todo 和 active docs 表述
- 必要时把临时记录归档
- 只有在 reasoning 真发生变化时才补 devlog / handoff

退出信号：

- 剩余 backlog 明确且很小
- `.codex/status.md`、`.codex/plan.md`、roadmap 和 test-plan 指向同一个 post-closeout 状态

## 执行规则

把这条 milestone 当成一条长任务执行线：

1. 从第一个未完成队列项开始
2. 除非遇到真实 blocker、checkpoint 或 decision gate，否则持续推进
3. 不因为“顺手”就重开已经收口的旧 slice
4. 只有当这条 milestone 可以正式关闭，或被刻意拆成新的 roadmap candidate 时才停

## 验证栈

里程碑收口的最小验证：

```bash
bash scripts/run_tests.sh
python3 scripts/runtime/release_gate.py --json
python3 scripts/runtime/planning_acceptance_suite.py --json
python3 scripts/runtime/channel_acceptance.py --json
python3 scripts/runtime/main_ops_acceptance.py --json
```

如果这轮触及真实外发或 planning contract，还应补真实或半真实 evidence capture。
