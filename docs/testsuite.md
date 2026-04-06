# Test Suite

> 最后更新：2026-04-06
> 角色：这是本项目的正式测试手册。它定义自动化 testsuite 跑什么、保证什么，以及哪些属于人工验收。

## 1. 测试目标

`openclaw-task-system` 测试的不是几个孤立函数，而是一整套“任务运行时 + 控制面”能力。

正式 testsuite 需要回答 4 个问题：

1. runtime 是否稳定
2. control-plane / scheduler 是否可解释
3. plugin 与 runtime 接线是否完整
4. 用户视角的真实通道体验是否符合当前 contract

其中前 3 层进入自动化必跑；第 4 层保留人工或半真实验收。

## 2. 正式分层

### 2.1 自动化必跑层

这部分必须稳定、可重复、默认全绿。

包括：

- Python runtime / CLI 回归
- Node plugin / control-plane 回归
- Plugin Doctor
- Plugin Smoke

统一入口：

```bash
bash scripts/run_tests.sh
```

### 2.2 协议与日志证据层

这层验证的重点不是“有没有输出”，而是：

- lane 是否按优先级与冲突规则工作
- `skip / drop / sent / error` 是否有稳定解释
- terminal / preempt / supersede / continuation / host delivery 是否有完整证据链

核心覆盖文件：

- [plugin/tests/pre-register-and-ack.test.mjs](../plugin/tests/pre-register-and-ack.test.mjs)
- [plugin/tests/control-plane-lane.test.mjs](../plugin/tests/control-plane-lane.test.mjs)
- [plugin/tests/scheduler-diagnostics.test.mjs](../plugin/tests/scheduler-diagnostics.test.mjs)
- [plugin/tests/delivery-runners.test.mjs](../plugin/tests/delivery-runners.test.mjs)
- [tests/test_openclaw_hooks.py](../tests/test_openclaw_hooks.py)
- [tests/test_openclaw_bridge.py](../tests/test_openclaw_bridge.py)

### 2.3 冒烟与接线层

这层验证项目仍然是一个可安装、可接线、可走通基本生命周期的系统。

包括：

- `plugin_doctor.py`
- `plugin_smoke.py`

### 2.4 人工 / 半真实验收层

这层不属于“自动化必绿”，因为它依赖当前运行态、真实 channel 或当前 active tasks。

包括：

- Telegram / Feishu 的真实交互验收
- `dashboard --json`
- `continuity --json`
- `queues --json`
- `lanes --json`

## 3. 自动化入口

### 3.1 一键全量入口

```bash
bash scripts/run_tests.sh
```

它会顺序运行：

1. Python runtime / CLI 回归
2. Node plugin / control-plane 回归
3. Plugin Doctor
4. Plugin Smoke

### 3.2 单项入口

Python：

```bash
python3 -m unittest discover -s tests -v
```

Node plugin：

```bash
node --test plugin/tests/*.test.mjs
```

Doctor：

```bash
python3 scripts/runtime/plugin_doctor.py
```

Smoke：

```bash
python3 scripts/runtime/plugin_smoke.py --json
```

## 4. Python 测试分组

测试目录：

- [tests/](../tests)

### 4.1 Runtime / Hook / Bridge

- [test_openclaw_hooks.py](../tests/test_openclaw_hooks.py)
- [test_openclaw_bridge.py](../tests/test_openclaw_bridge.py)
- [test_main_task_adapter.py](../tests/test_main_task_adapter.py)

覆盖：

- register / finalize / follow-up / watchdog / continuity
- structured `control_plane_message`
- `registerDecision` / bridge decision / task adapter

### 4.2 Task Truth Source

- [test_task_state.py](../tests/test_task_state.py)
- [test_task_status.py](../tests/test_task_status.py)
- [test_task_policy.py](../tests/test_task_policy.py)
- [test_task_config.py](../tests/test_task_config.py)
- [test_task_store_lookup.py](../tests/test_task_store_lookup.py)
- [test_taskmonitor_state.py](../tests/test_taskmonitor_state.py)

覆盖：

- task 存储
- 状态迁移
- 用户状态投影
- taskmonitor / policy / config

### 4.3 运维与 CLI

- [test_main_ops.py](../tests/test_main_ops.py)
- [test_health_report.py](../tests/test_health_report.py)
- [test_watchdog_cycle.py](../tests/test_watchdog_cycle.py)
- [test_silence_monitor.py](../tests/test_silence_monitor.py)

覆盖：

- `dashboard / continuity / queues / lanes / triage / producer / channel-acceptance`
- watchdog / silence monitor / health report

### 4.4 Delivery / Instruction Path

- [test_delivery_flow.py](../tests/test_delivery_flow.py)
- [test_delivery_outage.py](../tests/test_delivery_outage.py)
- [test_delivery_reconcile.py](../tests/test_delivery_reconcile.py)
- [test_instruction_executor.py](../tests/test_instruction_executor.py)
- [test_enqueue_test_instruction.py](../tests/test_enqueue_test_instruction.py)
- [test_notify.py](../tests/test_notify.py)

### 4.5 接线与 acceptance 脚本

- [test_plugin_doctor.py](../tests/test_plugin_doctor.py)
- [test_plugin_smoke.py](../tests/test_plugin_smoke.py)
- [test_main_acceptance.py](../tests/test_main_acceptance.py)
- [test_channel_acceptance.py](../tests/test_channel_acceptance.py)
- [test_stable_acceptance.py](../tests/test_stable_acceptance.py)

## 5. Node plugin 测试分组

- [plugin/tests/pre-register-and-ack.test.mjs](../plugin/tests/pre-register-and-ack.test.mjs)
- [plugin/tests/control-plane-lane.test.mjs](../plugin/tests/control-plane-lane.test.mjs)
- [plugin/tests/scheduler-diagnostics.test.mjs](../plugin/tests/scheduler-diagnostics.test.mjs)
- [plugin/tests/delivery-runners.test.mjs](../plugin/tests/delivery-runners.test.mjs)

合起来覆盖：

- pre-register / canonical snapshot / `queueKey`
- long-queue retention for receive-side pre-register / early-ack state
- immediate `[wd]` / early ack / dedupe
- runtime delivery pipeline preserves `reply_to_id / thread_id` across outbox -> delivery-ready -> send-instructions
- short follow-up
- structured `control_plane_message`
- terminal / preempt / supersede
- `sent / skipped / dropped / error / adapter-unavailable`
- continuation / host delivery / fulfilled shortcut
- raw `<task_user_content>` marker suppression
- host / continuation direct-send paths also suppress raw `<task_user_content>` leakage
- promise-guard rehydrate after reload
- same-audience control-plane lane recovers after timed-out direct send
- lifecycle `entered / ignored / skipped`
- scheduler diagnostics 字段
- runner 字段：
  - `runner`
  - `lifecycleStage`
  - `deliveryPath`
- operator-visible 顶层失败出口：
  - `hook failure`
  - `gateway failure`
  - `control-plane send failure`
  - `plugin load enabled / disabled`
- producer contract / pre-register 对齐：
  - `queue identity`
  - `pre-register snapshot`
  - `producerMode`
  - channel capability matrix

## 6. 通过标准

### 6.1 自动化 testsuite 通过

需要同时满足：

- `run_tests.sh` 成功退出
- Python unittest 全绿
- Node plugin tests 全绿
- `plugin_doctor.py` 通过
- `plugin_smoke.py --json` 返回 `"ok": true`

### 6.2 阶段退出意义

完整自动化 testsuite 全绿时，可支撑这些阶段性结论：

- `Phase 2`
  - control-plane lane 优先级、冲突规则和证据链已稳定
- `Phase 3`
  - 用户状态投影已统一到同一 truth source
- `Phase 4`
  - producer contract 已正式落成到代码与运维输出
- `Phase 5`
  - channel acceptance matrix 已正式落成并进入 stable acceptance

### 6.3 人工验收需要继续观察

- `[wd]` 是否在用户视角第一时间可见
- control-plane 消息是否被普通 reply 堵住
- 是否出现重复 ack / 重复 follow-up / 残留 received task
- `dashboard / continuity` 是否与预期一致

## 7. 当前边界

- 真实运行态命令不是自动化必绿项，因为它们依赖现场状态
- Node plugin 测试已经按能力拆分，但 helper 仍集中在 `plugin/tests/helpers/`
- “全 channel receive-time `[wd]`” 不是当前 testsuite 承诺的结论；它属于后续 roadmap 增强方向

## 8. Phase 6 最小 starter suite

针对 `llm_tool_task_planning` 这条新线，建议不要一上来把整套 testsuite 做大，而是先跑通一个最小闭环。

### 8.1 最小验证目标

最小 starter suite 只回答 5 个问题：

1. tool-created follow-up plan 能否写入 truth source
2. plan 能否物化成真实 paused follow-up task
3. finalize 能否抓住 `promise-without-task`
4. overdue follow-up 能否仍被执行并留下稳定证据
5. 首条 `[wd]`、30 秒 follow-up、fallback / recovery 是否仍保持 runtime-owned

### 8.2 建议第一批自动化测试

#### Python 最小集

优先从 runtime truth source 和 finalize contract 开始：

- [test_openclaw_hooks.py](../tests/test_openclaw_hooks.py)
  - plan register / materialize / overdue execution
- [test_main_task_adapter.py](../tests/test_main_task_adapter.py)
  - promise guard / finalize anomaly
- [test_task_policy.py](../tests/test_task_policy.py)
  - follow-up plan contract / `followup_due_at`

建议新增的最小文件：

- `tests/test_task_planning_tools.py`
  - 覆盖：
    - `ts_create_followup_plan`
    - `ts_schedule_followup_from_plan`
    - `ts_attach_promise_guard`

#### Node plugin 最小集

优先验证控制面职责没有被这条新线破坏：

- [plugin/tests/pre-register-and-ack.test.mjs](../plugin/tests/pre-register-and-ack.test.mjs)
  - 首条 `[wd]` 仍为 runtime-owned
- [plugin/tests/control-plane-lane.test.mjs](../plugin/tests/control-plane-lane.test.mjs)
  - 30 秒 follow-up / fallback 不被 tool path 抢走

建议新增的最小文件：

- `plugin/tests/tool-planning-flow.test.mjs`
  - 覆盖：
    - post-ack 默认进入 tool-assisted planning
    - fixed runtime-owned control-plane messages 仍走原控制面路径

### 8.3 最小跑法

在实现早期，建议先只跑这个最小集合：

```bash
python3 -m unittest \
  tests.test_openclaw_hooks \
  tests.test_main_task_adapter \
  tests.test_task_policy \
  tests.test_task_planning_tools

node --test \
  plugin/tests/pre-register-and-ack.test.mjs \
  plugin/tests/control-plane-lane.test.mjs \
  plugin/tests/tool-planning-flow.test.mjs
```

目标不是一开始就替代完整 testsuite，而是：

- 先把最小 contract 跑绿
- 再把 coverage 逐步并回全量入口

### 8.4 扩展顺序

最小 starter suite 跑通后，再按这个顺序扩展：

1. 扩 promise-without-task anomaly 投影
2. 扩 overdue follow-up 与恢复路径
3. 扩 dashboard / triage / continuity 证据链
4. 扩更多 channel 或不同 agent 的 planning path

### 8.5 不该一开始就做的事

为了控制成本，Phase 6 最小测试阶段不要一开始就做：

- 全 channel rollout 测试
- 大而全的 LLM prompt 组合验收
- 把所有 follow-up / progress 文案都工具化
- 用复杂集成测试替代掉最小 contract 测试
