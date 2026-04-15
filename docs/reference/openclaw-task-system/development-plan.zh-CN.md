[English](development-plan.md) | [中文](development-plan.zh-CN.md)

# Development Plan

## 目的

这份计划文档是 roadmap 之下的人类执行层。

它用来回答：

- 最近一个已完成里程碑到底收了什么
- 当前正在执行的阶段为什么是这条线
- 下一步进入真实激活之前，还必须满足什么条件

## 总体进展

| 项目 | 当前值 |
| --- | --- |
| 主线进度 | 主线已经完成到 `Milestone 3`；当前工作已经切到有界 activation 准备，而不是继续无限期做性能调优 |
| 当前阶段 | `性能基线收口后的 live pilot activation 准备` |
| 当前目标 | 在已收口的性能基线上重新打开 live pilot activation 准备，而不是让 Milestone 3 继续停留在 open-ended tuning bucket |
| 明确下一步动作 | `AP-1` 定义 activation rehearsal 入口条件与必须采集的 operator evidence 包 |
| 下一候选动作 | 在入口条件、install-sync 意图和 rollback 边界都显式后，运行一轮有界的 `feishu6-chat` live activation rehearsal |

## Activation 准备任务进度

| 顺序 | 任务 | 状态 |
| --- | --- | --- |
| 1 | AP-1 定义 activation rehearsal 入口条件与基于已收口 benchmark baseline 的 operator evidence 包 | 下一步 |
| 2 | AP-2 判断第一次有界 rehearsal 前是否需要显式执行 `growware_local_deploy.py --json` 清理 installed-runtime drift | 已排队 |
| 3 | AP-3 定义第一次 live activation checkpoint、rollback 边界，以及新测得回归何时重新回流主线 | 已排队 |

## 当前定位

仓库已经完成：

- Phase 0-6 最小闭环
- 架构整改收口
- 双语公开文档收敛
- `Milestone 1：post-hardening 收口`
- `Milestone 2：Growware Project 1 pilot foundation`

当前激活中的项目级阶段是：

- `性能基线收口后的 live pilot activation 准备`

Milestone 2 已经收口，因为 Growware pilot 的项目本地控制面、policy 编译层、验证入口、binding preview，以及只读宿主侧 audit bootstrap 都已经落到仓库真相里，而且遗留 `.growware/policies/*.json` 已从 live runtime / preflight 依赖中退役。

Milestone 3 现在也已经收口，因为仓库已经具备可复现 benchmark 合同、可复核的热点归因、已验证的优化结果，以及保护改进路径的回归门禁。

## 当前下一步

| 下一步 | 为什么做 |
| --- | --- |
| `AP-1` 定义 activation rehearsal 入口条件与必须采集的 operator evidence 包 | 性能里程碑已经收口，下一类风险不再是“有没有继续调快”，而是没有显式入口条件就直接进入 rehearsal。 |

## 里程碑总览

| 里程碑 | 状态 | 目标 | 验证 | 退出条件 |
| --- | --- | --- | --- | --- |
| Milestone 1：post-hardening 收口 | 已完成 | 收掉剩余 compound / future-first 边界、补 release-facing evidence，并把仓库带到干净的 post-hardening 状态 | `bash scripts/run_tests.sh`、`python3 scripts/runtime/release_gate.py --json`、planning / channel / main-ops acceptance helpers、文档一致性检查 | 边界文档、acceptance 深度与 operator / release-facing 收尾已经收敛，且没有重新打开架构债务 |
| Milestone 2：Growware Project 1 pilot foundation | 已完成 | 把 Growware `Project 1` 从候选变成仓库内可维护的正式基线，收敛项目本地 policy 真相、激活 gate 与 host-audit bootstrap | Growware policy sync / preflight / binding preview、定向 Growware tests、`bash scripts/run_tests.sh`、runtime mirror、doctor / smoke 与文档对齐 | 编译后的 `.policy` 成为唯一 live runtime input，激活安全边界文档化且全绿，host-audit 范围也有明确边界 |
| Milestone 3：系统性能测试与优化 | 已完成 | 先建立可复现的性能测量基线，再定位热点并做有证据的优化 | 当前 runtime 安全验证栈、性能测量入口、基线样本数据与 profile / benchmark 产物 | 已有 benchmark / profile 基线、热点归因、优化结果与回归门禁，且没有破坏 runtime truth 与控制面边界 |

## Milestone 2：Growware Project 1 Pilot Foundation

### 1. 项目本地真相与 Policy Layer

已完成：

- `.growware/` 记录了 Growware `Project 1`、`feishu6-chat` 以及项目本地 contracts / ops surface
- `docs/policy/*.md` 是人类 policy source，`.policy/` 是编译后的机器执行层
- `growware_policy_sync.py` 负责把 policy 文档编译成 manifest / index / rule artifacts
- `growware_project.py` 把 policy manifest / index / rule 数据暴露到项目摘要里
- `growware_feedback_classifier.py`、`growware_preflight.py` 与 `growware_local_deploy.py` 都已经收敛到编译后的 policy layer
- 遗留 `.growware/policies/*.json` 已退役，不再作为 live runtime / preflight 的必需输入

### 2. 验证与 Pilot 激活安全

已完成：

- `growware_preflight.py` 会检查 `policy-sync`
- `growware_local_deploy.py` 会先做 policy sync write + check，再做 runtime mirror 和 doctor
- 安装与 usage 文档已经把 `growware_policy_sync.py`、binding preview 和宿主侧 audit 命令补进入口
- plugin tests 与 Python tests 已经同步到当前 Growware policy 路径
- reviewed baseline 已在同一条编译后的 `.policy/` 路径上复核：policy sync、preflight、binding preview、runtime mirror、doctor / smoke、定向 Growware tests 和全量测试栈均通过

### 3. 宿主侧 Audit Bootstrap

已完成：

- `openclaw_runtime_audit.py` 会从真实 `~/.openclaw` 数据里检查 recent tasks、stale running tasks、failed deliveries、cron events、config health 与用户可见摘要
- `tests/test_openclaw_runtime_audit.py` 覆盖 stale-task、failed-delivery、cron-error 与用户可见噪声过滤行为
- audit 边界已冻结为只读 bootstrap evidence，不是静默修复工具，也不是当前里程碑之后的默认 rollout gate

### 4. 收口结论

Milestone 2 现在已经具备下面四条完成信号：

1. 编译后的 `.policy` 已成为 runtime 依赖的唯一 live intake / deploy 真相
2. policy sync、preflight、binding preview、定向 Growware tests、runtime mirror、doctor 和 smoke 在同一条基线上全部通过
3. 专用 `growware` 生产 session 的 hygiene 边界已写入文档与工具入口，不再依赖口头约定
4. roadmap / development-plan / `.codex/*` 已明确记录：host-side audit 仍然只是 bootstrap evidence，下一条主线是性能测试与优化

## Milestone 3：系统性能测试与优化

### 1. Benchmark 合同

已完成：

- `scripts/runtime/performance_baseline.py` 已经把 runtime、same-session routing、control-plane projection 和 operator 入口收敛成统一的 repo-local benchmark / profile 合同
- `docs/reference/openclaw-task-system/performance-baseline*.md` 已经把 reviewed fixtures、预算、命令和 profile 词汇冻结成 durable repo truth
- 第一轮 benchmark surface 刻意保持 repo-local，因此 host-install drift 会被看见，但不会被混进 baseline 本身

### 2. 已验证的热点收敛

已完成：

- `task_status.py` 把 reviewed `system-overview` fixture 从约 `484ms` median 收到约 `18ms`
- `task_state.py`、`openclaw_bridge.py` 和 `main_task_adapter.py` 把注册路径的重复 rescan 压到单次 inflight snapshot / shared store
- `openclaw_hooks.py` 现在让 repo 自带 Growware same-session classifier 走进程内 fast path，把 reviewed classifier path 从约 `90.0957ms` median / `132.2014ms` p95 收到约 `24.9839ms` / `38.5312ms`

### 3. 回归保护与验证

已完成：

- `tests/test_task_status.py`、`tests/test_task_state.py`、`tests/test_openclaw_bridge.py`、`tests/test_main_task_adapter.py`、`tests/test_openclaw_hooks.py` 和 `tests/test_performance_baseline.py` 已经对这些测量路径提供结构性保护
- reviewed repo-local 验证基线已经在 benchmark、preflight、binding preview、runtime mirror、全量 testsuite、doctor 和 smoke 上重新复核
- installed-runtime drift 继续通过 `plugin_doctor.py` 保持可见，而不是被悄悄吞进 repo-local 性能里程碑里

### 4. 收口结论

Milestone 3 现在已经满足下面四条收口信号：

1. durable repo truth 里已经存在可复现的 benchmark / profile 合同
2. 主要热点已经有可复核的前后证据，而不是只凭“感觉变快了”
3. 改进路径已经被 benchmark budget 和结构性回归检查保护起来
4. 整个优化过程没有破坏 runtime truth、激活边界或已有验证栈

## 性能基线收口后的 Live Pilot Activation 准备

### 当前执行原则

这条新主线必须遵守三个约束：

1. 继续把 `performance_baseline.py` 当作 guardrail；没有测量回归就不重新打开大范围性能调优
2. 在第一次有界 rehearsal 之前，显式决定 installed-runtime drift 是否需要通过本地 deploy 清掉
3. live activation rehearsal 必须绑定在已批准的 `feishu6-chat` 证据采集、rollback 边界和当前 runtime truth 上

### Immediate Execution Line

当前执行线拆成三步：

1. 定义 activation 入口条件和 operator evidence 包
   - 先定清楚 rehearsal 前后要抓哪些 repo-local 与 host-visible 信号
   - 让 activation 叙事继续建立在已复核的 benchmark 和验证基线上

2. 决定 install-sync 路径
   - 判断当前 installed-runtime drift 是否必须在首轮 rehearsal 前清掉
   - 任何 `growware_local_deploy.py --json` 都保持显式触发，不从 repo-only 工作里隐含推出

3. 准备第一次有界 rehearsal
   - 定义 rollback 条件、证据采集包，以及新出现的 slowdown 何时应该回流到性能线

### 建议入口条件

- reviewed repo-local 性能基线继续保持全绿
- Milestone 2 的 runtime 安全验证栈继续保持全绿
- activation evidence、rollback 边界和 install-sync 意图在 rehearsal 前已经写成真相
- carry-forward 的性能热点继续留在 backlog，只有 activation 证据把它们升级成 measured blocker 时才回流主线

## 验证栈

进入 activation 准备阶段时，同时保持 repo-local 性能基线和 Growware runtime 安全基线全绿：

```bash
python3 scripts/runtime/performance_baseline.py --profile-scenario hooks-cycle --profile-scenario same-session-routing-classifier --profile-scenario system-overview --profile-top 8 --enforce-budgets --json
python3 scripts/runtime/growware_policy_sync.py --write --json
python3 scripts/runtime/growware_preflight.py --json
python3 scripts/runtime/growware_openclaw_binding.py --json
python3 -m unittest tests.test_growware_feedback_classifier tests.test_growware_policy_sync tests.test_growware_preflight tests.test_growware_project tests.test_openclaw_runtime_audit -v
bash scripts/run_tests.sh
python3 scripts/runtime/runtime_mirror.py --write
python3 scripts/runtime/plugin_doctor.py --json
python3 scripts/runtime/plugin_smoke.py --json
```

只有当当前改动明确是为了在 rehearsal 前刷新本地 OpenClaw 安装时，才额外运行 `python3 scripts/runtime/growware_local_deploy.py --json`。
