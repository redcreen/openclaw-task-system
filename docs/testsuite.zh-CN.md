[English](testsuite.md) | [中文](testsuite.zh-CN.md)

# 测试总览

## 这份文档讲什么

这份文档是 `openclaw-task-system` 的详细测试清单。

它回答：

- `bash scripts/run_tests.sh` 实际会跑什么
- 哪些测试在验证 runtime 行为、control-plane 证据链和安装接线
- 哪些检查仍然属于半真实或人工验收，而不是默认必须全绿的自动化

## 自动化分层

### 1. Python Runtime / CLI 回归

主要入口：

```bash
python3 -m unittest discover -s tests -v
```

覆盖：

- runtime hooks 与 bridge 行为
- task truth source 与状态投影
- main ops、health、continuity 与 watchdog
- planning helper 与 acceptance 脚本
- task CLI 与运维命令

### 2. Node Plugin / Control-Plane 回归

主要入口：

```bash
node --test plugin/tests/*.test.mjs
```

覆盖：

- immediate ack 与 pre-register state
- queue receipt 与 same-session receipt
- control-plane lane 的调度、抢占与 supersede
- delivery runner 与 scheduler diagnostics
- plugin lifecycle 与终态控制面行为

### 3. Plugin Doctor

入口：

```bash
python3 scripts/runtime/plugin_doctor.py
```

验证：

- plugin manifest 与入口接线
- runtime hooks 路径
- 本地安装态 runtime 的同步可见性

### 4. Plugin Smoke

入口：

```bash
python3 scripts/runtime/plugin_smoke.py --json
```

验证：

- 最小 register、progress、resolve、finalize 生命周期
- control-plane message 结构
- task truth source 的最小闭环

## 核心 Acceptance Helper

下面这些也是自动化，但它们属于 contract 级 acceptance，不是窄单测：

- `python3 scripts/runtime/planning_acceptance.py --json`
- `python3 scripts/runtime/planning_acceptance_suite.py --json`
- `python3 scripts/runtime/same_session_routing_acceptance.py --json`
- `python3 scripts/runtime/stable_acceptance.py --json`

当前它们验证的 contract 包括：

- future-first `main_user_content_mode`
- planning materialization 与 anomaly projection
- same-session routing decision 与 receipt
- installed runtime sync 与稳定发布预期

## 半真实 / 人工检查

这些很重要，但不属于默认必须全绿的自动化层：

- 真实 Feishu / Telegram 交互
- `dashboard --json`
- `triage --json`
- `planning --json`
- `continuity --json`
- `queues --json`
- `lanes --json`

如果改动涉及真实通道行为，统一参考 [planning_acceptance_runbook.zh-CN.md](planning_acceptance_runbook.zh-CN.md)。

## 全量入口

正式一键回归入口仍然是：

```bash
bash scripts/run_tests.sh
```

它会顺序执行：

0. runtime mirror 校验
1. Python runtime / CLI 回归
2. Node plugin / control-plane 回归
3. Plugin Doctor
4. Plugin Smoke
