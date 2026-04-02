# OpenClaw Integration Plan

## 1. 目标

本文件描述如何把 `openclaw-task-system` 以插件方式接入 OpenClaw，而不修改主程序。

目标是：

- OpenClaw 主程序保持不改
- 插件负责接入 OpenClaw 生命周期 hooks
- 任务系统负责长任务判定、注册、进展回写、终态收口
- 静默检测与通知继续在任务系统内部运行

## 2. 建议接入边界

建议把接入点控制在两层：

- OpenClaw 插件层：`plugin/src/plugin/index.ts`
- Python 运行时 hook 入口：`scripts/runtime/openclaw_hooks.py`

插件需要提供给运行时 hook 的最少字段：

- `agent_id`
- `session_key`
- `channel`
- `chat_id`
- `user_id`
- `user_request`

可选增强字段：

- `estimated_steps`
- `touches_multiple_files`
- `involves_delegation`
- `requires_external_wait`
- `needs_verification`

## 3. 插件接入时机

### 3.1 `before_dispatch`

在 OpenClaw 准备把用户请求派发给 agent 之前：

1. 收集上下文
2. 插件调用 `openclaw_hooks.py register`
3. 如果返回 `should_register_task=false`，继续短任务路径
4. 如果返回 `should_register_task=true`，保存 `task_id`

### 3.2 `message_sending`

每次用户可见进展更新后：

- 插件调用 `openclaw_hooks.py progress-active`

### 3.3 `agent_end`

当 agent run 结束时：

- 插件调用 `openclaw_hooks.py finalize-active`
- `success=true` 时自动完成当前活动任务
- `success=false` 时自动失败收口当前活动任务

### 3.4 后续增强 hooks

- 可继续接 `message_sent`
- 可继续接 `session_end`

## 4. 为什么先做插件层

原因是：

- OpenClaw 主程序和任务系统可以低耦合
- 任务系统可以独立测试
- 后续换接入点时，主逻辑不需要重写
- 后续升级 OpenClaw 时更容易维护
- 插件可以只调用一个 hook 脚本入口

## 5. 第一阶段接入策略

第一阶段建议只接 `main`：

- 先在插件的 `before_dispatch` hook 注册长任务
- 先在插件的 `message_sending` hook 回写进展
- 暂时不要求其他 agent 同步接入

## 6. 验收标准

接入完成后，应满足：

- 无需修改 OpenClaw 主程序
- 插件能注册 `main` 的长任务 task instance
- 插件能回写阶段更新
- 插件能在 `agent_end` 自动完成或失败收口
- 现有自动化测试继续通过
- 新增接入测试可覆盖插件调用和 hook 调用
