[English](development-plan.md) | [中文](development-plan.zh-CN.md)

# Development Plan

## 目的

这份计划文档位于 roadmap 和 `.codex/plan.md` 之间。

它用来回答：

- 最近一个已完成里程碑到底收了什么
- 为什么现在又重新打开了新的里程碑
- 下一步进入真实激活之前，还必须满足什么条件

## 当前定位

仓库已经完成：

- Phase 0-6 最小闭环
- 架构整改收口
- 双语公开文档收敛
- `Milestone 1：post-hardening 收口`

现在新的项目级里程碑已经正式激活：

- `Milestone 2：Growware Project 1 pilot foundation`

之所以要打开这条里程碑，是因为仓库里已经存在真实的 Growware pilot 落地工作，包括文档、policy 编译层、preflight / deploy gate 以及宿主侧 audit bootstrap。既然实现已经开始，这条线就不应该继续停留在“未来候选”状态。

## 里程碑总览

| 里程碑 | 状态 | 目标 | 验证 | 退出条件 |
| --- | --- | --- | --- | --- |
| Milestone 1：post-hardening 收口 | 已完成 | 收掉剩余 compound / future-first 边界、补 release-facing evidence，并把仓库带到干净的 post-hardening 状态 | `bash scripts/run_tests.sh`、`python3 scripts/runtime/release_gate.py --json`、planning / channel / main-ops acceptance helpers、文档一致性检查 | 边界文档、acceptance 深度与 operator / release-facing 收尾已经收敛，且没有重新打开架构债务 |
| Milestone 2：Growware Project 1 pilot foundation | 进行中 | 把 Growware `Project 1` 从候选变成仓库内可维护的正式基线，收敛项目本地 policy 真相、激活 gate 与 host-audit bootstrap | Growware policy sync / preflight / binding preview、定向 Growware tests、`bash scripts/run_tests.sh`、runtime mirror、doctor / smoke 与文档对齐 | 编译后的 `.policy` 成为唯一 live runtime input，激活安全边界文档化且全绿，host-audit 范围也有明确边界 |

## Milestone 2：Growware Project 1 Pilot Foundation

### 1. 项目本地真相与 Policy Layer

已交付：

- `.growware/` 现在记录了 Growware `Project 1`、`feishu6-chat` 以及项目本地 contracts / ops surface
- `docs/policy/*.md` 现在是人类 policy source，`.policy/` 现在是编译后的机器执行层
- `growware_policy_sync.py` 现在负责把 policy 文档编译成 manifest / index / rule artifacts
- `growware_project.py` 现在会把 policy manifest / index / rule 数据暴露到项目摘要里
- `growware_feedback_classifier.py` 现在读取编译后的 policy rule，而不是继续依赖遗留 prose 或直接读取 `.growware/policies`

还需要收口：

- 把 `.growware/policies/*.json` 严格收束成兼容层输入，或者彻底移出 live runtime 依赖
- 保证 install、mirror、preflight 和 deploy 流程都收敛到同一套编译 policy 真相

### 2. 验证与 Pilot 激活安全

已交付：

- `growware_preflight.py` 现在会检查 `policy-sync`
- `growware_local_deploy.py` 现在会先做 policy sync write + check，再做 runtime mirror 和 doctor
- 安装与 usage 文档已经把 `growware_policy_sync.py` 和宿主侧 audit 命令补进入口
- plugin tests 与 Python tests 已经同步到当前 Growware 文案和 policy 路径

还需要收口：

- 用同一条干净基线跑通 `growware_policy_sync.py`、`growware_preflight.py`、`growware_openclaw_binding.py --json`、runtime mirror、doctor、smoke 与 session hygiene guidance
- 明确第一次真实 `feishu6-chat` 激活之前，哪些证据是必须具备的

### 3. 宿主侧 Audit Bootstrap

已交付：

- `openclaw_runtime_audit.py` 现在会从真实 `~/.openclaw` 数据里检查 recent tasks、stale running tasks、failed deliveries、cron events、config health 与用户可见摘要
- `tests/test_openclaw_runtime_audit.py` 已经覆盖 stale-task、failed-delivery、cron-error 与用户可见噪声过滤行为
- 当前 audit 边界明确是只读 bootstrap，不是静默修复工具

还需要收口：

- 明确只读 audit 是否足以算作 Milestone 2 的组成部分，还是应该把 repair planning 升成下一个命名里程碑
- 在宿主侧 policy 没明确之前，不把 audit 和 release gate 混成一条线

### 4. 下一步激活门槛

只有下面四条同时成立，才应该从 foundation 进入真实 pilot activation：

1. 编译后的 `.policy` 已经成为 runtime 依赖的唯一 live intake / deploy 真相
2. `growware_policy_sync.py`、`growware_preflight.py`、`growware_openclaw_binding.py --json`、定向 Growware tests、runtime mirror、doctor 和 smoke 在同一条基线上全部通过
3. 专用 `growware` 生产 session 的 hygiene 规则已经明确、可复现
4. roadmap 已经明确写清：host-side audit 仍然只是 bootstrap evidence，还是会升级成下一条 milestone

## 验证栈

当前里程碑应主要依赖下面这组验证：

```bash
python3 scripts/runtime/growware_policy_sync.py --check --json
python3 scripts/runtime/growware_preflight.py --json
python3 scripts/runtime/growware_openclaw_binding.py --json
python3 -m unittest tests.test_growware_feedback_classifier tests.test_growware_policy_sync tests.test_growware_preflight tests.test_growware_project tests.test_openclaw_runtime_audit
bash scripts/run_tests.sh
python3 scripts/runtime/runtime_mirror.py --write
python3 scripts/runtime/plugin_doctor.py --json
python3 scripts/runtime/plugin_smoke.py --json
```

只有当当前改动本来就是要真正本地部署进 OpenClaw 时，才额外运行 `python3 scripts/runtime/growware_local_deploy.py --json`；阶段性 review 本身不默认触发真实本地部署。
