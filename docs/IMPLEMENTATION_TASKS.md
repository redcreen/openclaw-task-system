# OpenClaw Task System Implementation Tasks

## 1. 任务拆解原则

本清单面向执行型大模型或工程代理，目标是让开发工作按小步、可测试、可回归的方式推进。

拆解原则：

- 每个任务应尽量独立
- 每个任务完成后应有明确测试
- 每个任务不应同时引入过多新概念
- 先 `main`，后多 agent
- 先最小闭环，后增强能力

## 2. 开发主线

开发顺序建议如下：

1. 明确 task schema
2. 标准化 task state API
3. 为 state 层补单测
4. 为静默扫描补单测
5. 标准化 outbox payload
6. 跑通最小 outbox 流转
7. 定义 `main` 的长任务判定规则
8. 接入 `main` 的任务注册
9. 接入 `main` 的进展回写
10. 接入 `main` 的终态收口
11. 跑通 `main + 任务系统` 最小闭环
12. 建立统一自动化测试入口
13. 推广到其他 agent
14. 增加任务状态可视化与查询入口
15. 增加 OpenClaw 主程序桥接层

## 3. 第一阶段最小里程碑

第一阶段必须完成：

- task state API
- state 自动化测试
- 静默扫描自动化测试
- `main` 任务注册
- `main` 进展回写
- `main` 终态收口
- 最小 outbox / send 闭环
- 自动化测试入口

## 4. 单任务模板

每个开发任务都应至少包含：

- 目标
- 输入
- 输出
- 修改范围
- 独立测试
- 完成判定

## 5. 推荐起始任务

建议最先执行的 5 个任务：

### Task A1

明确 `task_state.py` 的 schema 和状态迁移规则。

### Task A2

为 `task_state.py` 提供统一 API：

- `register_task`
- `start_task`
- `touch_task`
- `block_task`
- `pause_task`
- `complete_task`
- `fail_task`
- `archive_task`

### Task A3

为 `task_state.py` 写自动化单测。

### Task A4

为 `silence_monitor.py` 写自动化单测，覆盖：

- 未超时
- 已超时
- 已通知
- 已完成

### Task A5

标准化 outbox payload 与消费链路的最小测试。

## 6. main 接入任务

在基础层稳定后，进入 `main` 接入：

### Task B1

定义 `main` 的长任务判定条件。

### Task B2

实现 `main` 长任务注册。

### Task B3

实现 `main` 用户可见进展回写。

### Task B4

实现 `main` 终态收口。

### Task B5

编写 `main` 的最小闭环集成测试。

### Task B6

提供任务状态查询与可视化输出脚本。

### Task B7

实现 `main` 任务适配层，统一封装判定、注册、进展回写、终态收口。

### Task B8

实现 OpenClaw 主程序桥接层，统一接收 `session_key/channel/chat_id/user_request` 等真实上下文。

## 7. 最终自动化测试目标

最终应能通过统一入口完成回归，例如：

- `python3 -m unittest discover -s workspace/openclaw-task-system/tests -v`
- 或未来定义的统一测试命令

自动化测试通过时，应至少覆盖：

- task state
- 静默扫描
- outbox flow
- main integration

当前建议统一入口：

- `bash workspace/openclaw-task-system/scripts/run_tests.sh`

## 8. 第二阶段任务

在第一阶段稳定后再进入：

- 多 agent 推广
- 配置模型实现
- 发送路径增强
- 恢复策略
- 并发测试

## 9. 成功标准

任务系统第一阶段成功的标准：

- `main` 长任务不再只靠用户催促续跑
- 超时时能产生保守通知
- 状态更新与终态收口可靠
- 自动化测试能稳定通过
