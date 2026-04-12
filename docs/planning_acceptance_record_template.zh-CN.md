[English](planning_acceptance_record_template.md) | [中文](planning_acceptance_record_template.zh-CN.md)

# Planning Acceptance 记录模板

把这份文件当成新建一次真实或半真实 planning acceptance 记录的起点。

参考资料：

- [planning_acceptance_runbook.zh-CN.md](planning_acceptance_runbook.zh-CN.md)
- [archive/planning_acceptance_record_2026-04-12.zh-CN.md](archive/planning_acceptance_record_2026-04-12.zh-CN.md)

## 可复制模板

````md
[English](planning_acceptance_record_YYYY-MM-DD.md) | [中文](planning_acceptance_record_YYYY-MM-DD.zh-CN.md)

# YYYY-MM-DD Planning Acceptance 记录

## 1. 基本信息

- 日期：
- 执行人：
- 验收类型：`real` / `semi-real`
- 环境：
  - source repo / installed plugin：
  - channel：
  - account / workspace：
  - branch / revision：
- 本次背景：

## 2. 验收目标

- 本轮改动是什么：
- 这次运行要证明什么：
- 涉及哪些 runtime / planning / release-facing 边界：

## 3. 样例输入

用户输入：

```text
<粘贴本次代表性请求>
```

## 4. 自动化前置结果

执行命令：

```bash
bash scripts/run_tests.sh
python3 scripts/runtime/run_planning_acceptance_bundle.py --json --date YYYY-MM-DD
```

结果：

- broader regression：
- bundle summary：
- planning acceptance steps：
- stable acceptance steps：
- install / doctor / smoke checks：

## 5. 用户侧观察

### 5.1 首条 `[wd]`

- 是否第一时间可见：
- 是否仍由 runtime 生成：
- 证据：

### 5.2 30 秒进度 follow-up

- 是否观察到真实用户可见消息：
- 是否带出真实进展摘要：
- 结论：

### 5.3 到点 continuation / follow-up

- 是否按预期 materialize / claim：
- 是否保留正确 reply target：
- 证据：

### 5.4 最终收口

- `plan_status` 是否 fulfilled：
- `promise_guard_status` 是否 fulfilled：
- happy-path planning anomaly 是否清零：

## 6. 运维侧观察

- planning / continuity / dashboard 看到了什么：
- anomaly / overdue 投影是否正确：
- repo 默认数据目录是否保持 clean：
- 关键证据：

## 7. 通过判定

- 总结论：`pass` / `fail` / `pass-with-notes`
- 严重级别：
- 摘要：
- 未覆盖或延期项：

## 8. 附件与证据

- artifacts：
- 相关 JSON 输出：
- task IDs / plan IDs：
- session keys：

## 9. 后续动作

- 下一条 dated evidence 何时需要补：
- 是否需要补文档或 runbook：
- 下轮 planning 改动后要重复哪些验证：
````
