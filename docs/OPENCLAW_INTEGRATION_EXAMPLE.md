# OpenClaw Integration Example

## 1. 目标

本文件给出一个简化示例，说明 OpenClaw 主流程未来如何调用任务系统，而不是把任务逻辑直接写死在主流程里。

## 2. 简化接入顺序

### Step 1: 用户消息进入 main

主程序收集上下文：

- `agent_id`
- `session_key`
- `channel`
- `chat_id`
- `user_id`
- `user_request`

### Step 2: 交给桥接层决定是否注册任务

调用：

```python
decision = register_inbound_task(ctx)
```

如果：

- `should_register_task = false`
  继续走短任务路径

- `should_register_task = true`
  保存 `task_id`，后续所有阶段更新都带着这个 `task_id`

### Step 3: 阶段同步时回写

当 `main` 给用户发出可见进展后：

```python
record_progress(task_id, progress_note="checked files")
```

### Step 4: 阻塞、完成、失败时收口

阻塞：

```python
record_blocked(task_id, "waiting for approval")
```

完成：

```python
record_completed(task_id, "fixed and verified")
```

失败：

```python
record_failed(task_id, "provider timeout")
```

## 3. 为什么这样接

这样接的好处是：

- 主程序不用直接理解 task json 结构
- 桥接层成为唯一接入口
- 任务系统可以独立测试
- 后续扩展到其他 agent 时不需要重写核心逻辑

## 4. 第一阶段建议

第一阶段只要求：

- `main` 走这套桥接逻辑
- 先不要求所有 agent 同步接入
- 先保证状态真实、静默可检测、终态可收口
