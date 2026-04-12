[English](plugin_installation.md) | [中文](plugin_installation.zh-CN.md)

# 插件安装指南

这份文档负责：

- 安装前提
- 插件安装方式
- OpenClaw 最小配置
- 安装后验证

项目范围与已交付边界统一看：

- [../README.zh-CN.md](../README.zh-CN.md)
- [roadmap.zh-CN.md](roadmap.zh-CN.md)
- [archive/local_install_validation_2026-04-09.zh-CN.md](archive/local_install_validation_2026-04-09.zh-CN.md)

## 安装前提

默认前提：

- 已安装 OpenClaw
- 本地可用 `python3`
- `plugin/`、`scripts/runtime/`、`config/` 三处 payload 保持一致
- `scripts/runtime/` 作为 canonical runtime source，`plugin/scripts/runtime/` 作为 install mirror

## 安装方式

稳定版远程安装：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/redcreen/openclaw-task-system/v0.1.0/scripts/install_remote.sh)
```

主干最新版安装：

```bash
OPENCLAW_TASK_SYSTEM_REF=main bash <(curl -fsSL https://raw.githubusercontent.com/redcreen/openclaw-task-system/main/scripts/install_remote.sh)
```

纯 OpenClaw 安装：

```bash
openclaw plugins install git+https://github.com/redcreen/openclaw-task-system.git#v0.1.0
```

本地源码安装：

```bash
openclaw plugins install ./plugin
```

## 当前本地安装边界

当前 OpenClaw 版本下，本地安装还存在一个现实边界：

- 插件 runtime 通过 `child_process.spawn(...)` 调 Python hook
- OpenClaw 2026.4.2 可能把它识别成 dangerous code pattern
- 即使显式加 force flag，本地重装也未必一定成功

所以 `openclaw plugins install ./plugin` 现在应视为“可能可用”，不是“默认稳定可用”。

如果本地安装被拦截，当前推荐做法是：

1. 继续维护好 `plugin/` installable payload
2. 用 `plugin_doctor.py`、`plugin_smoke.py`、`stable_acceptance.py` 在源码侧验证
3. 用 install drift 视图确认源码和安装态 runtime 是否已经漂移

## 安装前检查

```bash
python3 scripts/runtime/runtime_mirror.py --check
python3 scripts/runtime/plugin_doctor.py
python3 scripts/runtime/plugin_smoke.py
```

机器可读输出：

```bash
python3 scripts/runtime/plugin_doctor.py --json
python3 scripts/runtime/plugin_smoke.py --json
```

## 最小配置

远程安装脚本会把最小插件配置写入：

- `~/.openclaw/openclaw.json`

如果你要预览或重写这份最小配置：

```bash
python3 scripts/runtime/configure_openclaw_plugin.py
python3 scripts/runtime/configure_openclaw_plugin.py --write
```

最常用的配置来源是：

- [`../config/task_system.json`](../config/task_system.json)
- [`../config/task_system.example.json`](../config/task_system.example.json)
- [`../config/openclaw_plugin.example.json`](../config/openclaw_plugin.example.json)

## 安装后验证

建议顺序：

1. `plugin_doctor.py`
2. `plugin_smoke.py`
3. `main_ops.py dashboard --json`
4. `stable_acceptance.py --json`
5. 如果要跑更宽的 release-facing 验证，再跑 `release_gate.py --json`
6. 如果改了 planning，再跑 `planning_acceptance_suite.py --json`

示例：

```bash
python3 scripts/runtime/main_ops.py dashboard --json
python3 scripts/runtime/stable_acceptance.py --json
python3 scripts/runtime/release_gate.py --json
python3 scripts/runtime/planning_acceptance_suite.py --json
python3 scripts/runtime/main_ops.py plugin-install-drift --json
```

## Install Drift 可见性

如果要确认源码和本地安装态 runtime 是否漂移，直接看：

```bash
python3 scripts/runtime/main_ops.py dashboard --only-issues
python3 scripts/runtime/main_ops.py triage --json
python3 scripts/runtime/main_ops.py plugin-install-drift --json
```

现在 `dashboard / triage` 已经会直接投影 install drift，不需要只记一个独立脚本名。

## Source 与 Install 的所有权

当前所有权约定是：

- `scripts/runtime/`：canonical runtime source
- `plugin/scripts/runtime/`：随插件一起打包的 install mirror
- 本地 installed runtime：OpenClaw extensions 目录下的实际部署副本

当 runtime 代码变更时，打包或跑全量测试前先校验 repo mirror：

```bash
python3 scripts/runtime/runtime_mirror.py --check
```
