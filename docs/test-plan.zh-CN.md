# 测试计划

[English](test-plan.md) | [中文](test-plan.zh-CN.md)

## 范围与风险

`openclaw-task-system` 的发布门槛验证的是整套 runtime 行为，不是几个孤立 helper。

核心风险包括：

- 用户可见控制面回执与 runtime truth 脱节
- planned follow-up / continuation 变成隐式行为或丢失真相源
- same-session follow-up routing 与 runtime-owned contract 不一致
- installable plugin payload 与本地安装态 runtime 漂移
- 运维视图没有把 planning anomaly 与 recovery action 投影出来

## 验收用例

| 用例 | 前置条件 | 操作 | 预期结果 |
| --- | --- | --- | --- |
| 普通长任务 | runtime 已启用 | 注册一条普通长任务 | runtime 创建或复用 task，并返回 `[wd]` 回执 |
| same-session routing | 已有活跃 session | 发送补充消息、独立新请求、控制命令或 collect-more 输入 | runtime 在 `steering / queueing / control-plane / collect-more` 中做判定，并返回 runtime-owned 回执 |
| planning follow-up | planning 已启用 | 创建 structured follow-up plan 并物化 | follow-up 变成真实 task，并写入稳定 truth source |
| channel rollout boundary | producer contract 已加载 | 检查 channel acceptance 的矩阵、聚焦与 fallback 样本 | 每个通道都保持在当前 rollout contract 定义的 validated 或 bounded 范围内 |
| operator recovery projection | dashboard、triage 与 continuity 入口可用 | 检查 operator acceptance 的 planning recovery、watchdog 风险与快照视图样本 | 运维视图会从同一份 truth source 给出一致的下一步动作、短视图和 runbook |
| future-first | 请求需要延迟或计划性处理 | 检查即时输出 | runtime 按结构化 `main_user_content_mode` 管控即时输出 |
| recovery / continuity | 存在跨重启或延迟唤醒任务 | 跑 continuity 与 watchdog 流程 | task 状态、continuation 与用户可见解释保持一致 |
| install drift | 同时存在源码仓库与安装态 runtime | 跑 doctor 与 drift 检查 | drift 会在 doctor、ops 视图和 stable acceptance 中被投影出来 |

## 自动化覆盖

自动化发布信心要求至少包括：

- `bash scripts/run_tests.sh`
- `python3 scripts/runtime/release_gate.py --json`

`release_gate.py` 会把基础 testsuite、main ops acceptance、stable acceptance、runtime mirror 和 plugin install drift 检查收口成一条显式的 release-facing 门禁线。

testsuite 必须覆盖：

- Python runtime / CLI 回归
- Node plugin / control-plane 回归
- plugin doctor
- plugin smoke
- main ops acceptance helper
- channel acceptance helper
- planning acceptance helper
- same-session routing acceptance

当前 release-facing 样本深度已经显式包含：

- 已排定 follow-up 摘要仍留在控制面投影里
- `webchat` 的 bounded-focus 覆盖
- `followup-task-missing` 的 operator recovery 投影

详细分组见 [testsuite.zh-CN.md](testsuite.zh-CN.md)。

## 手工检查

涉及真实外发或 planning contract 时，至少再看：

- `python3 scripts/runtime/planning_acceptance.py --json`
- `python3 scripts/runtime/planning_acceptance_suite.py --json`
- `python3 scripts/runtime/planning_acceptance_suite.py --dry-run --json`
- `python3 scripts/runtime/run_planning_acceptance_bundle.py --dry-run --json`
- `python3 scripts/runtime/main_ops_acceptance.py --json`
- `python3 scripts/runtime/channel_acceptance.py --json`
- `python3 scripts/runtime/same_session_routing_acceptance.py --json`
- `python3 scripts/runtime/main_ops.py continuity --compact`
- `python3 scripts/runtime/main_ops.py continuity --only-issues`
- `python3 scripts/runtime/main_ops.py triage --compact`
- [planning_acceptance_runbook.zh-CN.md](planning_acceptance_runbook.zh-CN.md) 中的真实 / 半真实通道步骤

## 测试数据与夹具

主要夹具来源：

- `tests/` 下的 runtime task state fixture
- `plugin/tests/` 下的 control-plane fixture
- `docs/artifacts/` 下的 planning 临时产物

历史验收记录统一归到 [archive/README.zh-CN.md](archive/README.zh-CN.md)，不再挤在当前主文档栈里。

## 发布门禁

一个改动集要能视为可发布或可合并，至少应满足：

- `python3 scripts/runtime/release_gate.py --json` 返回 `ok: true`
- 文档与当前已交付行为一致
- 如果改了 runtime / plugin 行为，installable payload 与本地部署步骤也保持同步
