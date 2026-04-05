# OpenClaw Task System Usage Guide

本文件只讲两件事：

- 已经装好之后，日常怎么用
- 维护时哪些命令最常用

项目是什么、为什么存在、主线状态是什么，统一看：

- [README.md](../README.md)
- [roadmap.md](./roadmap.md)

## 1. 日常使用模型

当前系统的基本节奏是：

1. 用户消息进入 task-system 管理范围
2. 系统登记任务
3. 返回首条 `[wd]`
4. 真实执行开始
5. 有必要时同步进展或 follow-up
6. 以 `done / failed / blocked / paused / recovered` 收口

这套模型已经覆盖：

- 普通长任务
- delayed reply / continuation
- watchdog / continuity 恢复
- 重启后的任务继续执行

## 2. 运维入口

### 2.1 健康与总览

```bash
python3 scripts/runtime/main_ops.py health
python3 scripts/runtime/main_ops.py dashboard
python3 scripts/runtime/main_ops.py dashboard --json
python3 scripts/runtime/main_ops.py triage
python3 scripts/runtime/main_ops.py triage --json
```

适合回答：

- 现在整体是否正常
- 是否有需要马上处理的问题
- 当前最该做的下一步是什么

### 2.2 队列与 lane

```bash
python3 scripts/runtime/main_ops.py queues
python3 scripts/runtime/main_ops.py queues --json
python3 scripts/runtime/main_ops.py lanes
python3 scripts/runtime/main_ops.py lanes --json
```

适合回答：

- 当前有哪些 queue
- 哪些 session 在共享同一个 lane
- 当前建议 `serial / serial-per-session / parallel-safe`

### 2.3 continuity 与恢复

```bash
python3 scripts/runtime/main_ops.py continuity
python3 scripts/runtime/main_ops.py continuity --json
python3 scripts/runtime/main_ops.py continuity --auto-resume-if-safe --dry-run --json
python3 scripts/runtime/main_ops.py continuity --resume-watchdog-blocked --dry-run
```

适合回答：

- 有没有 watchdog-blocked / continuity 风险
- 当前能不能安全 auto-resume
- 这轮恢复之后是否已经收口

### 2.4 producer 与 channel contract

```bash
python3 scripts/runtime/main_ops.py producer --json
python3 scripts/runtime/main_ops.py channel-acceptance --json
```

适合回答：

- 当前 channel 是 receive-side 还是 dispatch-side contract
- 这一条 session 在当前边界下的 producer 语义是什么
- 当前 channel acceptance matrix 是否仍然成立

### 2.5 任务控制

```bash
python3 scripts/runtime/main_ops.py list
python3 scripts/runtime/main_ops.py show <task_id>
python3 scripts/runtime/main_ops.py cancel --task-id <task_id>
python3 scripts/runtime/main_ops.py stop
python3 scripts/runtime/main_ops.py stop-all
python3 scripts/runtime/main_ops.py purge --session-key '<session_key>'
```

适合回答：

- 当前有哪些 active main tasks
- 某一条任务具体处于什么状态
- 是否要取消、停止或清理测试残留

## 3. 外发与指令执行

### 3.1 instruction executor

默认 dry-run：

```bash
python3 scripts/runtime/instruction_executor.py
```

真实执行：

```bash
python3 scripts/runtime/instruction_executor.py --execute
```

标记真实宿主上下文：

```bash
python3 scripts/runtime/instruction_executor.py --execute --execution-context host
```

当前通过 `openclaw message send` 路径可直接执行的通道，以本机 CLI 实际支持列表为准。  
`feishu` 不走这条 CLI 实发链，而是走专门的 Feishu 发送路径。

### 3.2 watchdog 调试

只验证 watchdog 产物，不做真实外发：

```bash
python3 scripts/runtime/watchdog_cycle.py config/task_system.json --no-execute
```

标记宿主上下文：

```bash
python3 scripts/runtime/watchdog_cycle.py config/task_system.json --execution-context host
```

### 3.3 生成测试指令

```bash
python3 scripts/runtime/enqueue_test_instruction.py --channel telegram --chat-id @example --message "task system test"
```

带账号：

```bash
python3 scripts/runtime/enqueue_test_instruction.py --channel slack --account-id workspace-bot --chat-id "#ops" --message "task system test"
```

## 4. 推荐维护顺序

如果你是在当前项目状态下做维护，推荐顺序是：

1. 先看 `dashboard / triage`
2. 再看 `continuity`
3. 必要时看 `queues / lanes`
4. 需要发送与恢复时再看 instruction executor / watchdog cycle
5. 最后再做清理、取消或 stop 类动作

## 5. 验证入口

完整自动化回归：

```bash
bash scripts/run_tests.sh
```

稳定验收：

```bash
python3 scripts/runtime/stable_acceptance.py
python3 scripts/runtime/stable_acceptance.py --json
```

插件自检：

```bash
python3 scripts/runtime/plugin_doctor.py
python3 scripts/runtime/plugin_smoke.py
```
