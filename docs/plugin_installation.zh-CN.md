[English](plugin_installation.md) | [中文](plugin_installation.zh-CN.md)

# 插件安装指南

## 本文负责什么

这份文档只负责：

- 安装前检查
- 插件正式安装
- OpenClaw 最小配置
- 安装后的最小验证

项目背景与主线状态统一看：

- [../README.zh-CN.md](../README.zh-CN.md)
- [roadmap.zh-CN.md](roadmap.zh-CN.md)
- [archive/local_install_validation_2026-04-09.zh-CN.md](archive/local_install_validation_2026-04-09.zh-CN.md)

## 快速安装

稳定版远程安装：

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/redcreen/openclaw-task-system/v0.1.0/scripts/install_remote.sh)
```

主干最新版：

```bash
OPENCLAW_TASK_SYSTEM_REF=main bash <(curl -fsSL https://raw.githubusercontent.com/redcreen/openclaw-task-system/main/scripts/install_remote.sh)
```

## 最小前提

- 已安装 OpenClaw
- 本地可用 `python3`
- 仓库中的 `plugin/`、`scripts/runtime/`、`config/` 文件保持一致

## 安装前检查

```bash
python3 scripts/runtime/plugin_doctor.py
python3 scripts/runtime/plugin_smoke.py
```

## 最小配置

远程安装脚本会把最小可用插件配置写入 `~/.openclaw/openclaw.json`。

如果你要手动重写或预览：

```bash
python3 scripts/runtime/configure_openclaw_plugin.py
python3 scripts/runtime/configure_openclaw_plugin.py --write
```

## 安装后验证

建议顺序：

1. `plugin_doctor.py`
2. `plugin_smoke.py`
3. `dashboard --json`
4. `stable_acceptance.py --json`
5. 需要时再跑 `planning_acceptance_suite.py --json`

更细的配置项和本地安装边界，仍以 [plugin_installation.md](plugin_installation.md) 为英文源文件。
