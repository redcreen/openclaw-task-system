[English](planning_acceptance_record_template.md) | [中文](planning_acceptance_record_template.zh-CN.md)

# Planning Acceptance Record Template

本模板用于记录一次真实 / 半真实 `Phase 6` 验收。

配合这些文档一起使用：

- [planning_acceptance_runbook.md](./planning_acceptance_runbook.md)
- [usage_guide.md](./usage_guide.md)
- [testsuite.md](./testsuite.md)

## 1. 基本信息

- 日期：
- 执行人：
- 环境：
  - source repo / installed plugin：
  - channel：
  - account / workspace：
  - branch / revision：
- 验收类型：
  - 真实通道 / 半真实

## 2. 验收目标

- 本次想确认的重点：
- 涉及功能：
  - `[wd]`
  - 30 秒 follow-up
  - tool-assisted planning
  - continuation / overdue claim
  - planning / continuity ops projection

## 3. 样例输入

用户输入：

```text
先整理这批问题，5 分钟后回来同步结论。
```

如果本次使用其他样例，请记录：

```text
<替换成实际样例>
```

## 4. 自动化前置结果

记录本次验收前置命令结果：

```bash
python3 scripts/runtime/plugin_doctor.py
python3 scripts/runtime/plugin_smoke.py --json
python3 scripts/runtime/planning_acceptance.py --json
python3 scripts/runtime/stable_acceptance.py --json
```

- `plugin_doctor.py`：
- `plugin_smoke.py --json`：
- `planning_acceptance.py --json`：
- `stable_acceptance.py --json`：

## 5. 用户侧观察

### 5.1 首条 `[wd]`

- 是否第一时间可见：
- 是否为第一条可见控制面消息：
- 文案是否正确：
- 证据：

### 5.2 30 秒 follow-up

- 是否触发：
- 是否带出具体状态摘要：
- 是否出现空泛“仍在处理中”：
- 证据：

### 5.3 到点 continuation

- 是否按预期到点：
- 是否执行了计划中的 follow-up：
- reply_to / thread 关联是否正确：
- 证据：

### 5.4 最终收口

- source task 最终状态：
- follow-up task 最终状态：
- 是否残留 `promise-without-task`：
- 证据：

## 6. 运维侧观察

建议附上这些命令的输出或截图：

```bash
python3 scripts/runtime/main_ops.py dashboard --json
python3 scripts/runtime/main_ops.py planning --json
python3 scripts/runtime/main_ops.py continuity --json
python3 scripts/runtime/main_ops.py triage --json
```

记录要点：

- `dashboard` 是否投影出正确主问题：
- `planning` 是否显示正确的 task / pending / anomaly / overdue：
- `continuity` 是否显示正确的 session 风险与动作：
- `triage` 推荐动作是否合理：

## 7. 通过判定

- 是否通过：
- 失败级别：
  - blocker / warn / note
- 结论摘要：

如果失败，请明确归类：

- `[wd]` 可见性问题
- 30 秒 follow-up 摘要问题
- planning 物化问题
- overdue continuation 问题
- ops truth-source 投影问题
- 其他

## 8. 附件与证据

- 用户侧消息截图：
- 命令输出：
- 相关 task id：
- 相关 session key：
- 其他备注：

## 9. 后续动作

- 是否需要补测试：
- 是否需要补 docs：
- 是否需要补 anomaly / runbook：
- 下一位接手人：
