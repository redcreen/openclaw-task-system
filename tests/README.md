# Tests Overview

这个目录存放 Python 侧测试。

阅读建议：

- 如果你想了解“任务真相源、runtime hook、CLI 运维”怎么验证，先看这里。
- 如果你想了解 plugin 的 control-plane lane / scheduler，去看：
- [pre-register-and-ack.test.mjs](/Users/redcreen/.openclaw/workspace/openclaw-task-system/plugin/tests/pre-register-and-ack.test.mjs)
- [control-plane-lane.test.mjs](/Users/redcreen/.openclaw/workspace/openclaw-task-system/plugin/tests/control-plane-lane.test.mjs)
- [scheduler-diagnostics.test.mjs](/Users/redcreen/.openclaw/workspace/openclaw-task-system/plugin/tests/scheduler-diagnostics.test.mjs)
- [delivery-runners.test.mjs](/Users/redcreen/.openclaw/workspace/openclaw-task-system/plugin/tests/delivery-runners.test.mjs)

按职责可粗分为：

- `test_openclaw_hooks.py` / `test_openclaw_bridge.py`
  - runtime hook / bridge / structured payload
- `test_task_*`
  - task truth source / status / policy / config / lookup
- `test_main_ops.py` / `test_health_report.py` / `test_watchdog_cycle.py`
  - 运维 CLI / dashboard / continuity / watchdog
- `test_delivery_*` / `test_instruction_executor.py` / `test_notify.py`
  - delivery / instruction / notification path
- `test_plugin_doctor.py` / `test_plugin_smoke.py`
  - 接线与冒烟

正式 testsuite 说明见：

- [docs/TESTSUITE.md](/Users/redcreen/.openclaw/workspace/openclaw-task-system/docs/TESTSUITE.md)
