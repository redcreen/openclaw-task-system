[English](local_install_validation_2026-04-09.md) | [中文](local_install_validation_2026-04-09.zh-CN.md)

# Local Install Validation 2026-04-09

本记录用于说明当前本地 OpenClaw 安装态与 `plugin/` 源码 payload 的验证结论。

## 结论

- 本机存在可用 `openclaw` CLI：
  - `OpenClaw 2026.4.2`
- 本机已有全局安装态插件：
  - `~/.openclaw/extensions/openclaw-task-system`
- 当前源码目录下的 `plugin/` payload 不能通过 `openclaw plugins install ./plugin` 重新安装到本地 OpenClaw。
- 即使使用：
  - `openclaw plugins install --dangerously-force-unsafe-install --link ./plugin`
  - 当前 CLI 仍然拒绝安装。

## 失败原因

OpenClaw 安装器把插件中的 `child_process.spawn(...)` 识别为 dangerous code pattern。

对应源码位置：

- [plugin/src/plugin/index.ts](/Users/redcreen/Project/openclaw-task-system/plugin/src/plugin/index.ts#L692)

实际报错摘要：

```text
Plugin "openclaw-task-system" installation blocked:
dangerous code patterns detected:
Shell command execution detected (child_process)
```

## 已确认信息

- `openclaw plugins list` 显示当前安装态仍在加载：
  - `~/.openclaw/extensions/openclaw-task-system`
- `openclaw plugins inspect openclaw-task-system` 显示当前插件状态为 `loaded`
- 当前安装目录不是源码 link
- 当前安装目录还没有这轮新增的 planning acceptance helper 脚本：
  - `planning_acceptance.py`
  - `create_planning_acceptance_record.py`
  - `prepare_planning_acceptance.py`
  - `capture_planning_acceptance_artifacts.py`
  - `run_planning_acceptance_bundle.py`
  - `planning_acceptance_suite.py`
- 当前安装目录与源码 `plugin/` payload 的漂移已经能直接从主运维视图看到：
  - `python3 scripts/runtime/main_ops.py dashboard --only-issues`
  - `python3 scripts/runtime/main_ops.py triage --json`
  - `python3 scripts/runtime/main_ops.py plugin-install-drift --json`
- 当前 drift 重点信号是：
  - `missing_in_installed_count = 7`
  - `extra_in_installed_count = 0`

## 当前建议

1. 继续把 `plugin/` 视作 installable payload truth source。
2. 在源码仓库里继续跑：
   - `plugin_doctor.py`
   - `plugin_smoke.py`
   - `stable_acceptance.py`
   - `planning_acceptance_suite.py`
   - `main_ops.py dashboard --only-issues`
   - `main_ops.py triage --json`
3. 不要默认承诺“改完就能通过 `openclaw plugins install ./plugin` 安装到本地 OpenClaw”。
4. 如果必须验证真实安装态，需要先确认 OpenClaw 对当前插件危险模式的允许策略。
