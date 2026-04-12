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
| future-first | 请求需要延迟或计划性处理 | 检查即时输出 | runtime 按结构化 `main_user_content_mode` 管控即时输出 |
| recovery / continuity | 存在跨重启或延迟唤醒任务 | 跑 continuity 与 watchdog 流程 | task 状态、continuation 与用户可见解释保持一致 |
| install drift | 同时存在源码仓库与安装态 runtime | 跑 doctor 与 drift 检查 | drift 会在 doctor、ops 视图和 stable acceptance 中被投影出来 |

## 自动化覆盖

自动化发布信心要求至少包括：

- `bash scripts/run_tests.sh`
- `python3 scripts/runtime/stable_acceptance.py --json`

testsuite 必须覆盖：

- Python runtime / CLI 回归
- Node plugin / control-plane 回归
- plugin doctor
- plugin smoke
- planning acceptance helper
- same-session routing acceptance

详细分组见 [testsuite.zh-CN.md](testsuite.zh-CN.md)。

## 手工检查

涉及真实外发或 planning contract 时，至少再看：

- `python3 scripts/runtime/planning_acceptance.py --json`
- `python3 scripts/runtime/planning_acceptance_suite.py --json`
- `python3 scripts/runtime/same_session_routing_acceptance.py --json`
- [planning_acceptance_runbook.zh-CN.md](planning_acceptance_runbook.zh-CN.md) 中的真实 / 半真实通道步骤

## 测试数据与夹具

主要夹具来源：

- `tests/` 下的 runtime task state fixture
- `plugin/tests/` 下的 control-plane fixture
- `docs/artifacts/` 下的 planning 临时产物

历史验收记录统一归到 [archive/README.zh-CN.md](archive/README.zh-CN.md)，不再挤在当前主文档栈里。

## 发布门禁

一个改动集要能视为可发布或可合并，至少应满足：

- `bash scripts/run_tests.sh` 全绿
- `python3 scripts/runtime/stable_acceptance.py --json` 返回 `ok: true`
- 文档与当前已交付行为一致
- 如果改了 runtime / plugin 行为，installable payload 与本地部署步骤也保持同步
