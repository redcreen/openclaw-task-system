[English](external_comparison.md) | [中文](external_comparison.zh-CN.md)

# 外部对比

## 目的

这份文档记录项目从外部 agent / control-plane 系统里吸收哪些原则，以及明确不吸收哪些方向。

## 当前结论

- 吸收 `control-plane` 独立成层的做法
- 吸收 `queue / control plane / worker` 明确分层的做法
- 吸收用户追加消息需要正式 `steering / queueing` 语义的做法
- 不把项目带偏成新的通用 orchestrator

## 使用方式

当你需要解释“为什么 task-system 强调监工优先、控制面优先，而不是继续堆执行器逻辑”时，先看英文原文 [external_comparison.md](external_comparison.md)。
