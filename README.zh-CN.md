[English](README.md) | [中文](README.zh-CN.md)

# OpenClaw Task System

## 这是什么

OpenClaw Task System 是给 OpenClaw 补上的正式 task runtime。

它把 OpenClaw 从“会回复的聊天流”变成“能正式接活、跟踪、恢复并收口任务的系统”。

适合这些场景：

- 请求会跑一段时间
- 有 delayed reply 或 scheduled follow-up
- 需要排队、取消、恢复
- 重启后任务不能丢
- 需要用户可见的控制面回执

## `[wd]` 是什么

`[wd]` 是 runtime-owned 的首条确认消息。

它告诉用户：

- 请求已经被系统接住
- 已经创建或复用了 task
- 这条请求已经进入 task-system 的受控状态

`[wd]` 不是自由聊天文案，而是正式控制面回执。

## 已交付能力地图

当前已交付的能力包括：

- runtime-owned 的首条 `[wd]` 与控制面消息
- 统一任务登记、queue identity 与用户可见状态投影
- 同一 session 连续输入的自动路由：`steering / queueing / control-plane / collect-more`
- delayed reply / continuation
- future-first planning 与结构化 `main_user_content_mode`
- watchdog / continuity 恢复链路
- planning anomaly 的运维投影与 recovery hint
- `dashboard / triage / queues / lanes / continuity / planning` 等运维视图
- 更短的 task CLI 查询入口
- producer contract 与 channel acceptance 真相源

same-session routing 现在已经是正式交付能力：

- 同一 session 的后续消息可以在任务未开始前并入当前任务
- 安全重启阶段的 follow-up 会走 `interrupt-and-restart`
- 明显独立的新请求仍然会单独排队
- 每次自动 routing decision 都会返回 runtime-owned `[wd]` 回执

当前刻意保留的边界仍然是：

- 单一意图、表达清晰的 delayed reply 已支持
- 更复杂的 compound request 仍应走 structured planning，而不是继续扩 regex / phrase list

详见：

- [`docs/compound_followup_boundary.zh-CN.md`](./docs/compound_followup_boundary.zh-CN.md)
- [`docs/llm_tool_task_planning.zh-CN.md`](./docs/llm_tool_task_planning.zh-CN.md)

## 当前状态

仓库现在已经进入一个更干净的阶段边界：

- Phase 0：完成
- Phase 1：完成
- Phase 2：完成
- Phase 3：完成
- Phase 4：完成
- Phase 5：完成
- Phase 6 最小闭环：完成
- Milestone 1：post-hardening 收口：完成
- Milestone 2：Growware Project 1 pilot foundation：完成
- Milestone 3：系统性能测试与优化：进行中

当前主线不是继续模糊收尾。

而是在已经收口的 Growware foundation 之上，进入“先测量、后优化”的性能阶段。

## 快速开始

稳定版远程安装：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/redcreen/openclaw-task-system/v0.2.0/scripts/install_remote.sh)
```

主干最新版安装：

```bash
OPENCLAW_TASK_SYSTEM_REF=main bash <(curl -fsSL https://raw.githubusercontent.com/redcreen/openclaw-task-system/main/scripts/install_remote.sh)
```

纯 OpenClaw 安装：

```bash
openclaw plugins install git+https://github.com/redcreen/openclaw-task-system.git#v0.2.0
```

## 文档地图

建议按这个顺序看：

- [`docs/roadmap.zh-CN.md`](./docs/roadmap.zh-CN.md)：正式主线、阶段结论与边界
- [`docs/architecture.zh-CN.md`](./docs/architecture.zh-CN.md)：运行时分层、truth source 与 contract
- [`docs/test-plan.zh-CN.md`](./docs/test-plan.zh-CN.md)：发布门槛与验收预期
- [`docs/README.zh-CN.md`](./docs/README.zh-CN.md)：文档导航与次级入口

补充资料：

- [`docs/policy/README.zh-CN.md`](./docs/policy/README.zh-CN.md)：人类 policy source 与编译后的 `.policy/` 机器层
- [`docs/plugin_installation.zh-CN.md`](./docs/plugin_installation.zh-CN.md)：安装路径、配置与 install drift 说明
- [`docs/usage_guide.zh-CN.md`](./docs/usage_guide.zh-CN.md)：日常运维与命令入口
- [`docs/testsuite.zh-CN.md`](./docs/testsuite.zh-CN.md)：详细自动化与验收清单
- [`docs/reference/openclaw-task-system/growware-pilot.zh-CN.md`](./docs/reference/openclaw-task-system/growware-pilot.zh-CN.md)：Growware `Project 1` 接入、`feishu6-chat` 绑定和 `.growware/` 真相源
- [`docs/reference/session_message_routing/README.zh-CN.md`](./docs/reference/session_message_routing/README.zh-CN.md)：same-session routing 的正式 contract
- [`docs/reference/README.zh-CN.md`](./docs/reference/README.zh-CN.md)：稳定参考资料
- [`docs/archive/README.zh-CN.md`](./docs/archive/README.zh-CN.md)：历史记录与已退役文档

## 运行时与源码目录

- [`plugin/`](./plugin)：可安装的 OpenClaw 插件 payload
- [`scripts/runtime/`](./scripts/runtime)：唯一 canonical editable runtime source tree
- [`plugin/scripts/runtime/`](./plugin/scripts/runtime)：供 installable plugin payload 使用的严格同步镜像
- [`config/`](./config)：运行时与插件配置样例

canonical source 规则：

- runtime 代码只在 [`scripts/runtime/`](./scripts/runtime) 下直接编辑
- 用 `python3 scripts/runtime/runtime_mirror.py --write` 同步 [`plugin/scripts/runtime/`](./plugin/scripts/runtime)
- 把 `runtime_mirror.py --check`、`plugin_doctor.py`、`scripts/install_remote.sh` 与 `scripts/run_tests.sh` 当作这条规则的 enforcement path

## 验证入口

完整自动化回归：

```bash
bash scripts/run_tests.sh
```

稳定验收：

```bash
python3 scripts/runtime/stable_acceptance.py --json
```

same-session routing 验收：

```bash
python3 scripts/runtime/same_session_routing_acceptance.py --json
```

planning 验收：

```bash
python3 scripts/runtime/planning_acceptance.py --json
python3 scripts/runtime/planning_acceptance_suite.py --json
```

runtime mirror 同步：

```bash
python3 scripts/runtime/runtime_mirror.py --check
python3 scripts/runtime/runtime_mirror.py --write
```
