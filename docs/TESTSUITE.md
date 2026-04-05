# Test Suite

> 最后更新：2026-04-05
> 角色：这是本项目的正式测试说明。它定义“自动化 testsuite 跑什么、保证什么、哪些属于人工验收”。

## 1. 测试体系目标

`openclaw-task-system` 做的是 OpenClaw 之上的“任务运行时 + 控制面”，所以测试不能只验证几个函数是否返回对。

正式 testsuite 需要覆盖 4 层目标：

1. 任务运行时是否稳定
2. control-plane lane / scheduler 是否可解释
3. plugin 与 runtime 的接线是否完整
4. 用户视角的真实通道体验是否符合北极星目标

这 4 层里，前 3 层可以自动化；第 4 层需要人工或半真实验收。

## 2. 正式分层

### 2.1 自动化必跑层

这部分必须稳定、可重复、默认应该全绿。

包括：

- Python runtime / CLI 回归
- Node plugin / control-plane 回归
- Plugin Doctor 结构检查
- Plugin Smoke 冒烟验证

统一入口：

```bash
bash workspace/openclaw-task-system/scripts/run_tests.sh
```

### 2.2 协议与日志证据层

这部分的重点不是“有没有输出”，而是：

- control-plane lane 是否按优先级工作
- skip / drop / sent / error 是否都能给出稳定解释
- terminal / preempt / supersede / continuation / host delivery 是否有完整证据链

这一层主要由以下测试覆盖：

- [plugin/tests/pre-register-and-ack.test.mjs](/Users/redcreen/.openclaw/workspace/openclaw-task-system/plugin/tests/pre-register-and-ack.test.mjs)
- [plugin/tests/control-plane-lane.test.mjs](/Users/redcreen/.openclaw/workspace/openclaw-task-system/plugin/tests/control-plane-lane.test.mjs)
- [plugin/tests/scheduler-diagnostics.test.mjs](/Users/redcreen/.openclaw/workspace/openclaw-task-system/plugin/tests/scheduler-diagnostics.test.mjs)
- [plugin/tests/delivery-runners.test.mjs](/Users/redcreen/.openclaw/workspace/openclaw-task-system/plugin/tests/delivery-runners.test.mjs)
- [tests/test_openclaw_hooks.py](/Users/redcreen/.openclaw/workspace/openclaw-task-system/tests/test_openclaw_hooks.py)
- [tests/test_openclaw_bridge.py](/Users/redcreen/.openclaw/workspace/openclaw-task-system/tests/test_openclaw_bridge.py)

### 2.3 冒烟与接线层

这部分验证“项目是否还是一个可安装、可接线、可走通基本生命周期的系统”，而不是只在测试桩里成立。

包括：

- `plugin_doctor.py`
- `plugin_smoke.py`

说明：

- `plugin_doctor.py` 负责检查插件入口、manifest、runtime root、配置路径
- `plugin_smoke.py` 负责跑一条最小 register -> progress -> finalize 生命周期

### 2.4 人工 / 半真实验收层

这部分不进入“必绿自动化 testsuite”，因为它依赖真实工作区状态、真实 channel 环境或当前 active task。

包括：

- Telegram / Feishu 的真实交互验收
- `dashboard --json`
- `continuity --json`
- `queues --json`
- `lanes --json`

说明：

- 这些命令非常重要，但它们读的是当前真实状态
- 如果现场本来就有残留任务，输出可能是 `warn`
- 所以它们属于“运行态验收”，不是“自动化必绿”

## 3. 自动化 testsuite 的正式入口

## 3.1 一键全量入口

```bash
bash workspace/openclaw-task-system/scripts/run_tests.sh
```

它会依次跑：

1. Python runtime / CLI 回归
2. Node plugin / control-plane 回归
3. Plugin Doctor
4. Plugin Smoke

## 3.2 单项入口

只跑 Python 回归：

```bash
python3 -m unittest discover -s workspace/openclaw-task-system/tests -v
```

只跑 Node plugin 回归：

```bash
node --test workspace/openclaw-task-system/plugin/tests/*.test.mjs
```

只跑插件结构检查：

```bash
python3 workspace/openclaw-task-system/scripts/runtime/plugin_doctor.py
```

只跑插件冒烟：

```bash
python3 workspace/openclaw-task-system/scripts/runtime/plugin_smoke.py --json
```

## 4. Python 测试分组

Python 目录在：

- [tests](/Users/redcreen/.openclaw/workspace/openclaw-task-system/tests)

建议按能力理解，而不是按文件名硬背：

### 4.1 Runtime / Hook / Bridge

- [test_openclaw_hooks.py](/Users/redcreen/.openclaw/workspace/openclaw-task-system/tests/test_openclaw_hooks.py)
- [test_openclaw_bridge.py](/Users/redcreen/.openclaw/workspace/openclaw-task-system/tests/test_openclaw_bridge.py)
- [test_main_task_adapter.py](/Users/redcreen/.openclaw/workspace/openclaw-task-system/tests/test_main_task_adapter.py)

覆盖内容：

- register / finalize / follow-up / watchdog / continuity hook
- structured `control_plane_message`
- `registerDecision` / bridge decision / task adapter

### 4.2 Task Truth Source

- [test_task_state.py](/Users/redcreen/.openclaw/workspace/openclaw-task-system/tests/test_task_state.py)
- [test_task_status.py](/Users/redcreen/.openclaw/workspace/openclaw-task-system/tests/test_task_status.py)
- [test_task_policy.py](/Users/redcreen/.openclaw/workspace/openclaw-task-system/tests/test_task_policy.py)
- [test_task_config.py](/Users/redcreen/.openclaw/workspace/openclaw-task-system/tests/test_task_config.py)
- [test_task_store_lookup.py](/Users/redcreen/.openclaw/workspace/openclaw-task-system/tests/test_task_store_lookup.py)
- [test_taskmonitor_state.py](/Users/redcreen/.openclaw/workspace/openclaw-task-system/tests/test_taskmonitor_state.py)

覆盖内容：

- task 存储
- 状态迁移
- 用户状态投影
- `user_facing_status_code / label / family`
- taskmonitor / policy / config

### 4.3 运维与运行态 CLI

- [test_main_ops.py](/Users/redcreen/.openclaw/workspace/openclaw-task-system/tests/test_main_ops.py)
- [test_health_report.py](/Users/redcreen/.openclaw/workspace/openclaw-task-system/tests/test_health_report.py)
- [test_watchdog_cycle.py](/Users/redcreen/.openclaw/workspace/openclaw-task-system/tests/test_watchdog_cycle.py)
- [test_silence_monitor.py](/Users/redcreen/.openclaw/workspace/openclaw-task-system/tests/test_silence_monitor.py)

覆盖内容：

- `/tasks` / queues / lanes / dashboard / continuity
- `*_status_code_counts` / `*_status_counts`
- watchdog / silence monitor / health report

### 4.4 Delivery / Instruction Path

- [test_delivery_flow.py](/Users/redcreen/.openclaw/workspace/openclaw-task-system/tests/test_delivery_flow.py)
- [test_delivery_outage.py](/Users/redcreen/.openclaw/workspace/openclaw-task-system/tests/test_delivery_outage.py)
- [test_delivery_reconcile.py](/Users/redcreen/.openclaw/workspace/openclaw-task-system/tests/test_delivery_reconcile.py)
- [test_instruction_executor.py](/Users/redcreen/.openclaw/workspace/openclaw-task-system/tests/test_instruction_executor.py)
- [test_enqueue_test_instruction.py](/Users/redcreen/.openclaw/workspace/openclaw-task-system/tests/test_enqueue_test_instruction.py)
- [test_notify.py](/Users/redcreen/.openclaw/workspace/openclaw-task-system/tests/test_notify.py)

覆盖内容：

- delivery bridge
- instruction lifecycle
- retry / outage / reconcile
- notify / test instruction

### 4.5 接线与验收脚本

- [test_plugin_doctor.py](/Users/redcreen/.openclaw/workspace/openclaw-task-system/tests/test_plugin_doctor.py)
- [test_plugin_smoke.py](/Users/redcreen/.openclaw/workspace/openclaw-task-system/tests/test_plugin_smoke.py)
- [test_main_acceptance.py](/Users/redcreen/.openclaw/workspace/openclaw-task-system/tests/test_main_acceptance.py)
- [test_stable_acceptance.py](/Users/redcreen/.openclaw/workspace/openclaw-task-system/tests/test_stable_acceptance.py)

覆盖内容：

- 插件结构
- 冒烟路径
- 稳定性与 acceptance 脚本

## 5. Node plugin 测试分组

Node plugin 测试现在按能力拆成了 4 组：

- [plugin/tests/pre-register-and-ack.test.mjs](/Users/redcreen/.openclaw/workspace/openclaw-task-system/plugin/tests/pre-register-and-ack.test.mjs)
- [plugin/tests/control-plane-lane.test.mjs](/Users/redcreen/.openclaw/workspace/openclaw-task-system/plugin/tests/control-plane-lane.test.mjs)
- [plugin/tests/scheduler-diagnostics.test.mjs](/Users/redcreen/.openclaw/workspace/openclaw-task-system/plugin/tests/scheduler-diagnostics.test.mjs)
- [plugin/tests/delivery-runners.test.mjs](/Users/redcreen/.openclaw/workspace/openclaw-task-system/plugin/tests/delivery-runners.test.mjs)

合起来主要覆盖：

- pre-register / canonical snapshot / `queueKey`
- immediate `[wd]` / early ack / dedupe
- short follow-up
- structured `control_plane_message`
- `/status` / `/compact` / `/tasks`
- 统一用户状态投影与 follow-up 状态 code
- terminal / preempt / supersede
- sent / skipped / dropped / error / adapter-unavailable
- continuation / host delivery / fulfilled shortcut
- lifecycle `entered` / `ignored` / `skipped`
- scheduler 证据链字段
- runner 统一字段
  - `runner`
  - `lifecycleStage`
  - `deliveryPath`
- operator-visible 顶层失败出口
  - `hook failure`
  - `gateway failure`
  - `control-plane send failure`
  - `plugin load enabled / disabled`
- producer contract / pre-register 对齐
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
- `plugin_doctor.py` 返回正常结构检查
- `plugin_smoke.py --json` 返回 `"ok": true`

### 6.1.1 对 Phase 2 的意义

当完整自动化 testsuite 通过，并且上述“协议与日志证据层”覆盖以下能力时，可以认为 `ROADMAP Phase 2` 满足退出条件：

- control-plane lane 优先级与冲突规则可解释
- lifecycle / runner / operator-visible failure 都进入结构化证据链
- 剩余宿主侧 `warn/info` 只作为辅助运维日志存在，而不是唯一证据来源

### 6.1.2 对 Phase 3 的意义

当完整自动化 testsuite 通过，并且以下能力都被自动化覆盖时，可以认为 `ROADMAP Phase 3` 满足退出条件：

- `/tasks`、`queues / lanes`、`dashboard / continuity / watchdog` 读取的是同一套用户状态投影
- 统一状态同时具备稳定 code 与用户可见 label，而不是只靠中文文案比较
- follow-up / `[wd]` 至少在核心 runtime 路径里优先基于统一状态 code 做判断

### 6.1.3 对 Phase 4 的意义

当完整自动化 testsuite 通过，并且以下能力都被自动化覆盖时，可以认为 `ROADMAP Phase 4` 满足退出条件：

- producer contract 已作为正式代码输出，而不是只停留在文档描述
- channel 能力矩阵已经明确区分：
  - `receive-side-producer`
  - `dispatch-side-priority-only`
- `dashboard / triage / producer` 读取的是同一份 producer contract 真相
- plugin 侧对 pre-register snapshot 的消费已经输出稳定的 `producerMode` 诊断

### 6.2 人工验收通过

需要额外观察：

- `[wd]` 是否在用户视角第一时间可见
- control-plane 消息是否被普通 reply 堵住
- 是否出现重复 ack / 重复 follow-up / 残留 received task
- `dashboard / continuity` 是否与预期一致

## 7. 当前已知边界

- 真实运行态命令不是自动化必绿项，因为它们受当前工作区状态影响
- Node plugin 测试已经按能力拆分，但共享 helper 仍集中在 `plugin/tests/helpers/`；后续可以继续按场景抽更细的 fixture builder
- “全 channel receive-time `[wd]`” 目前还不是自动化 testsuite 能宣称已覆盖的能力，它仍属于 roadmap 后续阶段目标
