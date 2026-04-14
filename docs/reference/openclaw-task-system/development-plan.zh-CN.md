[English](development-plan.md) | [中文](development-plan.zh-CN.md)

# Development Plan

## 目的

这份计划文档位于 roadmap 和 `.codex/plan.md` 之间。

它用来回答：

- 最近一个已完成里程碑到底收了什么
- 当前正在执行的阶段为什么是这条线
- 下一步进入真实激活之前，还必须满足什么条件

## 当前定位

仓库已经完成：

- Phase 0-6 最小闭环
- 架构整改收口
- 双语公开文档收敛
- `Milestone 1：post-hardening 收口`
- `Milestone 2：Growware Project 1 pilot foundation`

当前激活中的项目级阶段是：

- `Milestone 3：系统性能测试与优化`

Milestone 2 已经收口，因为 Growware pilot 的项目本地控制面、policy 编译层、验证入口、binding preview，以及只读宿主侧 audit bootstrap 都已经落到仓库真相里，而且遗留 `.growware/policies/*.json` 已从 live runtime / preflight 依赖中退役。

Milestone 3 的职责不是继续补 foundation 语义，而是先建立一套可复现、可归因、可回归的性能基线，避免后续 live activation、operator ergonomics 或 self-heal 讨论继续建立在“感觉哪里慢”的前提上。

## 里程碑总览

| 里程碑 | 状态 | 目标 | 验证 | 退出条件 |
| --- | --- | --- | --- | --- |
| Milestone 1：post-hardening 收口 | 已完成 | 收掉剩余 compound / future-first 边界、补 release-facing evidence，并把仓库带到干净的 post-hardening 状态 | `bash scripts/run_tests.sh`、`python3 scripts/runtime/release_gate.py --json`、planning / channel / main-ops acceptance helpers、文档一致性检查 | 边界文档、acceptance 深度与 operator / release-facing 收尾已经收敛，且没有重新打开架构债务 |
| Milestone 2：Growware Project 1 pilot foundation | 已完成 | 把 Growware `Project 1` 从候选变成仓库内可维护的正式基线，收敛项目本地 policy 真相、激活 gate 与 host-audit bootstrap | Growware policy sync / preflight / binding preview、定向 Growware tests、`bash scripts/run_tests.sh`、runtime mirror、doctor / smoke 与文档对齐 | 编译后的 `.policy` 成为唯一 live runtime input，激活安全边界文档化且全绿，host-audit 范围也有明确边界 |
| Milestone 3：系统性能测试与优化 | 进行中 | 先建立可复现的性能测量基线，再定位热点并做有证据的优化 | 当前 runtime 安全验证栈、性能测量入口、基线样本数据与 profile / benchmark 产物 | 已有 benchmark / profile 基线、热点归因、优化结果与回归门禁，且没有破坏 runtime truth 与控制面边界 |

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

### 当前执行原则

这条当前主线必须遵守三个约束：

1. 先测量、后优化，不接受无基线优化
2. 先建立可复现样本和统一命令入口，再讨论热点
3. 任何性能改动都不能破坏 Milestone 2 刚刚收口的 runtime truth、激活边界和部署验证栈

### Immediate Execution Line

当前执行线拆成四步：

1. 定义 benchmark surface 与预算
   - 覆盖 runtime register / resolve-active / progress / finalize
   - 覆盖 same-session routing 与 classifier 调用链
   - 覆盖 control-plane enqueue / delivery / queue projection
   - 覆盖 operator 入口，例如 `main_ops.py`、`plugin_doctor.py`、`plugin_smoke.py`、`growware_preflight.py`

2. 建立可复现测量入口
   - 固定样本数据、环境假设与命令入口
   - 避免测量结果依赖当前宿主的偶然状态

3. 采集第一轮 baseline 并做热点归因
   - 输出 benchmark / profile 结果
   - 给出主要热点、影响范围和优先级

4. 执行第一轮有证据的优化与回归门禁
   - 每项优化都有前后对比
   - 至少把关键路径纳入脚本化回归检查

### 建议范围

- runtime register / resolve-active / progress / finalize 路径
- same-session routing 与 classifier 调用链
- control-plane enqueue / delivery / queue projection
- task store、SQLite、文件扫描与日志读取热点
- `main_ops.py`、`plugin_doctor.py`、`plugin_smoke.py`、`growware_preflight.py` 等 operator 入口

### 建议退出条件

- 至少一套可复现 benchmark / profile 基线
- 主要热点有明确归因，而不是只知道“整体变慢”
- 每次优化都有前后对比
- 性能回归检查进入脚本化门禁或稳定验证入口

## 验证栈

Milestone 3 开始前，先维持 Milestone 2 的 runtime 安全验证栈全绿：

```bash
python3 scripts/runtime/growware_policy_sync.py --write --json
python3 scripts/runtime/growware_preflight.py --json
python3 scripts/runtime/growware_openclaw_binding.py --json
python3 -m unittest tests.test_growware_feedback_classifier tests.test_growware_policy_sync tests.test_growware_preflight tests.test_growware_project tests.test_openclaw_runtime_audit -v
bash scripts/run_tests.sh
python3 scripts/runtime/runtime_mirror.py --write
python3 scripts/runtime/plugin_doctor.py --json
python3 scripts/runtime/plugin_smoke.py --json
```

只有当当前改动本来就是要真正本地部署进 OpenClaw 时，才额外运行 `python3 scripts/runtime/growware_local_deploy.py --json`；性能阶段的 repo 内基线工作本身不默认触发真实本地部署。
