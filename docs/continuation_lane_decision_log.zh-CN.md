[English](continuation_lane_decision_log.md) | [中文](continuation_lane_decision_log.zh-CN.md)

# Continuation Lane 决策记录

## 记录目的

这份文档保存 continuation lane 的关键设计结论，重点是：

- 哪些消息应进入 continuation lane
- 与普通 reply lane、control-plane lane 的边界如何划分
- 哪些 stopgap 行为只是兼容桥接，不应固化成长期职责

## 当前应记住的结论

- continuation lane 负责未来执行和恢复，不负责替代主执行路径
- 运行时需要保留可解释证据，而不是只给用户一个黑盒结果
- lane 边界要服务恢复、watchdog、continuity 和 future-first contract

更完整的决策背景继续看 [continuation_lane_decision_log.md](continuation_lane_decision_log.md)。
