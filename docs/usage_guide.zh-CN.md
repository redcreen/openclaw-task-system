[English](usage_guide.md) | [中文](usage_guide.zh-CN.md)

# OpenClaw Task System 使用指南

## 日常节奏

装好之后，系统的典型节奏是：

1. 用户消息进入 task-system 管理范围
2. 系统登记或附着到已有任务
3. runtime 先返回首条 `[wd]`
4. 原执行链继续工作
5. 有需要时同步进展、follow-up 或 continuity
6. 最终以 `done / failed / blocked / paused / recovered` 收口

## 常用运维入口

健康和总览：

```bash
python3 scripts/runtime/main_ops.py health
python3 scripts/runtime/main_ops.py dashboard --json
python3 scripts/runtime/main_ops.py triage --json
```

队列和 lane：

```bash
python3 scripts/runtime/main_ops.py queues --json
python3 scripts/runtime/main_ops.py lanes --json
```

continuity 与恢复：

```bash
python3 scripts/runtime/main_ops.py continuity --json
python3 scripts/runtime/main_ops.py continuity --auto-resume-if-safe --dry-run --json
```

planning / acceptance：

```bash
python3 scripts/runtime/planning_acceptance_suite.py --json
python3 scripts/runtime/same_session_routing_acceptance.py --json
python3 scripts/runtime/stable_acceptance.py --json
```

## 什么时候读英文原文

如果你要看完整的命令清单、运维问题示例和 acceptance 工具链说明，继续读 [usage_guide.md](usage_guide.md)。
