[English](testsuite.md) | [中文](testsuite.zh-CN.md)

# 测试总览

## 这份文档讲什么

`testsuite` 是详细测试手册，回答：

- 自动化 testsuite 到底跑了哪些层
- 哪些属于协议与日志证据
- 哪些仍属于人工或半真实验收

## 自动化必跑

- Python runtime / CLI 回归
- Node plugin / control-plane 回归
- Plugin Doctor
- Plugin Smoke

统一入口：

```bash
bash scripts/run_tests.sh
```

## 详细清单

完整测试分组、脚本入口与 acceptance 说明，继续看 [testsuite.md](testsuite.md)。
