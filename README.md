# OpenClaw Task System

OpenClaw Task System 是 OpenClaw 之上的统一任务运行时和控制面。

它在做的事情，不是单纯补几个 `[wd]` 或队列脚本，而是把原本只是聊天流里的请求，提升成真正可管理的任务流：

- 有登记
- 有状态
- 有排队
- 有控制面反馈
- 能恢复
- 能收口
- 能被用户和运维同时看懂

一句话说，这个项目是在把 OpenClaw 从“只有消息流”补成“消息流 + 任务流”。

## 这个项目解决什么问题

- 用户发出消息后，不能第一时间知道系统是否真的收到了
- 长任务、延迟任务、跨轮次任务缺少统一任务对象和统一真相源
- 30 秒 follow-up、cancel、watchdog、continuity 这类控制面消息会被普通 reply 挤住
- 同一任务在 `[wd]`、`/tasks`、`queues`、`dashboard` 里显示的状态不一致
- 不同 channel 的行为不一致，很容易继续堆硬编码

所以这个项目存在的原因，不是某一个 feature 缺了，而是 OpenClaw 需要一层统一的任务控制平面。

## 当前主线

当前项目的正式主线已经整理为：

- [Roadmap](/Users/redcreen/.openclaw/workspace/openclaw-task-system/docs/ROADMAP.md)
- [Architecture](/Users/redcreen/.openclaw/workspace/openclaw-task-system/docs/ARCHITECTURE.md)
- [Test Suite](/Users/redcreen/.openclaw/workspace/openclaw-task-system/docs/TESTSUITE.md)
- [Usage Guide](/Users/redcreen/.openclaw/workspace/openclaw-task-system/docs/USAGE_GUIDE.md)
- [Plugin Installation](/Users/redcreen/.openclaw/workspace/openclaw-task-system/docs/PLUGIN_INSTALLATION.md)
- [Temporary Notes](/Users/redcreen/.openclaw/workspace/openclaw-task-system/docs/TODO.md)

默认阅读顺序：

1. `docs/ROADMAP.md`
2. `docs/ARCHITECTURE.md`
3. `docs/TESTSUITE.md`
4. `docs/USAGE_GUIDE.md`
5. `docs/PLUGIN_INSTALLATION.md`

## 文档约定

- `docs/ROADMAP.md`
  - 正式 roadmap
- `docs/ARCHITECTURE.md`
  - 核心设计和长期方案
- `docs/TODO.md`
  - 只作为临时记录和新增事项收集
  - 不再作为正式主线

## 当前验证入口

全量回归：

```bash
bash workspace/openclaw-task-system/scripts/run_tests.sh
```

常用维护检查：

```bash
python3 workspace/openclaw-task-system/scripts/runtime/plugin_doctor.py
python3 workspace/openclaw-task-system/scripts/runtime/plugin_smoke.py
python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py dashboard --json
python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py continuity --json
```

更完整的测试说明见：

- [docs/TESTSUITE.md](/Users/redcreen/.openclaw/workspace/openclaw-task-system/docs/TESTSUITE.md)

## 当前状态

当前项目已经不是“主链路能不能跑”的阶段了，主要在做两件事：

- 把 control-plane lane / scheduler 收紧成稳定、可解释、可验证的机制
- 为后续逐 channel 逼近 receive-time `[wd]` 和统一 control-plane 做准备

当前正式阶段进度：

- `Phase 2`：已完成
- `Phase 3`：已完成
- `Phase 4`：已完成
- `Phase 5`：已完成

目前按代码、testsuite 和文档都已经正式落成的包括：

- 统一 producer contract
- 统一 channel acceptance matrix
- `stable_acceptance` 持续验证 channel rollout / acceptance 不退化
