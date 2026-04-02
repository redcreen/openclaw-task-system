# OpenClaw Task System Usage Guide

## 1. 使用目标

本系统面向两类使用者：

- 系统集成者：把任务系统接入 OpenClaw
- 执行型 agent / 维护者：用任务系统管理长任务状态

## 2. 基本使用方式

### 2.1 长任务接入流程

当某个 agent 判断一个请求属于长任务或多步骤任务时，应遵循以下流程：

1. 注册任务
2. 返回启动回执
3. 开始真实执行
4. 每次用户可见更新后回写任务状态
5. 完成 / 阻塞 / 失败时显式收口

## 3. 角色视角使用说明

### 3.1 对 main agent

`main` 是第一阶段优先接入对象。

建议用法：

- 接到长任务时必须创建 task instance
- 分派给其他 agent 前也要保留任务跟踪信息
- 每次对用户阶段同步时都 touch task
- 任务完成或明确阻塞时做终态收口

推荐优先通过以下模块接入：

- `plugin/src/plugin/index.ts`
- `scripts/runtime/openclaw_hooks.py`
- `scripts/runtime/task_status.py`

主程序接入说明可参考：

- `docs/OPENCLAW_INTEGRATION_PLAN.md`
- `docs/PLUGIN_INSTALLATION.md`

当前推荐方式不是改 OpenClaw 主程序，而是安装或链接插件：

- `plugin/`

示例：

```bash
openclaw plugins install --link /Users/redcreen/.openclaw/workspace/openclaw-task-system/plugin
```

安装前推荐先跑自检：

```bash
python3 workspace/openclaw-task-system/scripts/runtime/plugin_doctor.py
```

### 3.2 对其他 agent

后续 `code / document / order / health` 可采用同样模式：

- 长任务注册
- 进展回写
- 终态收口

## 4. 配置使用方式

当前第一版已经支持配置驱动。

建议放置正式配置文件：

- `config/task_system.json`

如果没有正式配置文件，运行时会优先回退到：

- `config/task_system.example.json`

当前支持的核心配置包括：

- 是否启用任务系统
- 数据存储目录
- agent 级开关
- agent 自动启动开关
- 长任务判定阈值
- 静默检测模块开关
- 静默阈值
- 重发阈值
- 发送模式
- `openclaw` 二进制路径
- 外发执行默认上下文标签

插件层当前还支持这些 OpenClaw 接入配置：

- `pythonBin`
- `runtimeRoot`
- `configPath`
- `defaultAgentId`
- `registerOnBeforeDispatch`
- `sendImmediateAckOnRegister`
- `sendImmediateAckForShortTasks`
- `immediateAckTemplate`
- `shortTaskFollowupTimeoutMs`
- `shortTaskFollowupTemplate`
- `syncProgressOnMessageSending`
- `finalizeOnAgentEnd`
- `minProgressMessageLength`
- `ignoreProgressPatterns`

配置样例可参考：

- `config/task_system.example.json`
- `config/openclaw_plugin.example.json`

推荐的任务交互节奏是：

- 所有消息首次进入时，先回一条“已收到，开始处理”
- 短任务如果在 `shortTaskFollowupTimeoutMs` 内还没结束，再补一条“仍在处理中”
- 长任务如果 30 秒内没有新的阶段结果，再由 watchdog 自动补一条“仍在处理中”
- 后续继续按真实阶段进展回写，直到 `done / failed / blocked`

## 5. 运维使用方式

维护者应具备以下能力：

- 查看 inflight tasks
- 查看 archive tasks
- 查看 outbox / sent / delivered 目录
- 查看 `send-instructions / dispatch-results / processed-instructions / failed-instructions`
- 运行静默扫描
- 运行统一自动化测试入口

### 5.1 外发执行器

第一版真实外发通过 `instruction_executor.py` 完成。

默认行为是 dry-run，只生成 `dispatch-results`，不真的发送：

```bash
python3 workspace/openclaw-task-system/scripts/runtime/instruction_executor.py
```

要对真正可外发的通道执行实发，使用：

```bash
python3 workspace/openclaw-task-system/scripts/runtime/instruction_executor.py --execute
```

如果这次执行代表“真实宿主外发”，建议显式带上上下文标签：

```bash
python3 workspace/openclaw-task-system/scripts/runtime/instruction_executor.py --execute --execution-context host
```

当前支持实发的通道：

- `telegram`
- `discord`
- `slack`
- `signal`
- `whatsapp`
- `imessage`
- `line`
- `irc`
- `googlechat`

说明：

- 当前是按你机器上的 `openclaw message send --help` 实际可用通道对齐的
- `feishu` 目前不在 CLI `message send` 支持列表里，所以不会走这条 `--execute` 外发链
- 如果后续要支持 `feishu` 实发，需要单独接 Feishu 专用发送路径，而不是复用当前 CLI 发送器

执行规则：

- `channel=agent` 会被安全跳过，不会误发
- 不支持的通道会被跳过
- 缺少 `chat_id` 或 `message` 会被跳过
- `--execute` 成功后，指令文件会移到 `processed-instructions/`
- `--execute` 失败后，指令文件会移到 `failed-instructions/`
- dry-run 不会移走原始指令文件
- `dispatch-results/*.json` 现在会带 `execution_context`
  常见值包括 `dry-run`、`local`、`host`
- 同时还会带 `requested_execution_context`
  用来表示“本次原本想按什么上下文执行”

如果需要显式指定二进制，可用：

```bash
python3 workspace/openclaw-task-system/scripts/runtime/instruction_executor.py --execute --openclaw-bin /Users/redcreen/.local/bin/openclaw
```

### 5.1.1 watchdog 调试模式

如果要先验证 watchdog 是否发现超时任务、是否生成发送材料，但暂时不做真实外发，使用：

```bash
python3 workspace/openclaw-task-system/scripts/runtime/watchdog_cycle.py workspace/openclaw-task-system/config/task_system.json --no-execute
```

如果要把这次 watchdog 执行结果明确标记为真实宿主外发，可用：

```bash
python3 workspace/openclaw-task-system/scripts/runtime/watchdog_cycle.py workspace/openclaw-task-system/config/task_system.json --execution-context host
```

这条命令会继续产出：

- `outbox/`
- `sent/`
- `delivery-ready/`
- `send-instructions/`
- `dispatch-results/`

但不会调用真实 `openclaw message send`。

### 5.2 生成测试外发指令

为了安全验证真实外发，不建议手写 `send-instructions/*.json`。

推荐用：

```bash
python3 workspace/openclaw-task-system/scripts/runtime/enqueue_test_instruction.py --channel telegram --chat-id @example --message "task system test"
```

如果需要指定账号：

```bash
python3 workspace/openclaw-task-system/scripts/runtime/enqueue_test_instruction.py --channel slack --account-id workspace-bot --chat-id "#ops" --message "task system test"
```

生成后再执行：

```bash
python3 workspace/openclaw-task-system/scripts/runtime/instruction_executor.py --execute
```

## 6. 第一阶段推荐用法

第一阶段不要求复杂配置，只要求：

- 先接入 `main`
- 先跑通最小闭环
- 先保证测试能自动化通过

推荐测试入口：

- `bash workspace/openclaw-task-system/scripts/run_tests.sh`
- `python3 workspace/openclaw-task-system/scripts/runtime/stable_acceptance.py`
- `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py list`
- `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py health`
- `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py repair`
- `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py triage`
- `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py sweep`
- `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py resolve-failures`
- `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py diagnose-delivery`
- `python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py ack-delivery-outage`

推荐状态查看入口：

- `python3 workspace/openclaw-task-system/scripts/runtime/task_status.py <task_id>`
- `python3 workspace/openclaw-task-system/scripts/runtime/task_status.py --list`
- `python3 workspace/openclaw-task-system/scripts/runtime/task_status.py --overview`
- `python3 workspace/openclaw-task-system/scripts/runtime/delivery_reconcile.py`
- `python3 workspace/openclaw-task-system/scripts/runtime/health_report.py`

如果健康检查出现 `warn / error`，推荐先跑统一修复入口：

```bash
python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py repair
```

这条命令会先做安全的中间投递残留清理。

如果还希望顺手重试 retryable 的失败指令，再用：

```bash
python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py repair --execute-retries --execution-context host
```

说明：

- `repair` 默认不会真实外发失败指令，只做安全清理
- `repair` 还会补录历史 `failed-instructions` 的失败分类元数据，便于后续安全重试
- `--execute-retries` 只会重试被标记为 retryable 的失败指令
- `--execution-context host` 适合你在真实宿主环境下跑恢复动作
- `health_report.py` 现在会区分失败指令里的 `retryable / non-retryable / unknown`

如果你不想自己读健康报告并判断下一步，直接用：

```bash
python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py triage
```

它会按当前真实状态给出：

- 是否有 blocked 的 `main` 任务
- 是否有 retryable 的失败指令
- retryable 失败已经重试了几次
- 哪些失败是 non-retryable，需要先修目标或配置
- 如果 retryable 失败已经连续失败，`triage` 会提示先检查宿主网络，不再建议盲目继续重试
- `triage` 还会直接显示最近一次失败摘要，方便判断是不是网络、目标、还是认证问题
- 下一步建议执行的命令

如果你想批量处理长期卡住的 blocked `main` 任务，可以用：

```bash
python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py sweep --fail-stale-blocked-after-minutes 60 --reason "stale blocked main task"
```

说明：

- `sweep` 默认只是检查，不会改状态
- 只有显式传 `--fail-stale-blocked-after-minutes` 才会把超过阈值的 blocked 任务收口成 `failed`

如果你想把“已经确认不再需要继续重试”的失败指令从当前告警里收口出来，可以用：

```bash
python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py resolve-failures --non-retryable
```

这条命令默认也是只检查，不会改状态。  
如果确认要应用，例如把持续 retryable 失败或 non-retryable 失败移出当前活动失败集，再用：

```bash
python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py resolve-failures --persistent-retryable --apply --reason "manual resolution after network triage"
```

或：

```bash
python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py resolve-failures --non-retryable --apply --reason "manual resolution for invalid target"
```

如果你想直接拿到宿主侧网络探测建议，用：

```bash
python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py diagnose-delivery
```

它会输出：

- 当前最值得诊断的 retryable 失败目标
- 最近一次失败摘要
- 一条建议直接在宿主运行的 `openclaw message send ...` 探测命令

如果你已经确认这是外部网络/平台故障，而不是任务系统内部问题，可以先标记为已知外部故障：

```bash
python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py ack-delivery-outage --channel telegram --chat-id 8705812936 --reason "known telegram network outage"
```

这样健康报告会把对应失败从 `error` 降为 `warn`。  
恢复后再清掉：

```bash
python3 workspace/openclaw-task-system/scripts/runtime/main_ops.py clear-delivery-outage --channel telegram --chat-id 8705812936
```

状态总览和健康报告现在也会显示：

- `resolved_failed_instruction_count`

用来表示已经通过 `resolve-failures --apply` 收口的失败项数量。

状态查询里的 `delivery.state` 现在会直接给出当前投递阶段：

- `not-requested`
- `queued`
- `sent`
- `prepared`
- `pending-send`
- `processed`
- `skipped`
- `failed`

状态查询还会暴露残留中间产物：

- `delivery.stale_intermediate_exists`
- `delivery.stale_intermediate_count`

总览里也会汇总：

- `active_stale_delivery_task_count`
- `active_stale_delivery_artifact_count`
- `stale_delivery_task_count`
- `stale_delivery_artifact_count`

如果要检查历史遗留的中间投递产物，比如任务已经进入 `processed-instructions/` 或 `failed-instructions/`，但仍残留 `sent/`、`delivery-ready/`、`send-instructions/`，使用：

```bash
python3 workspace/openclaw-task-system/scripts/runtime/delivery_reconcile.py
```

如果确认要清理这些残留文件，再执行：

```bash
python3 workspace/openclaw-task-system/scripts/runtime/delivery_reconcile.py --apply
```

现在执行器在把指令归档到 `processed-instructions/` 或 `failed-instructions/` 时，也会自动尝试清理同一任务的中间投递残留。

如果想一次看任务系统当前健康状态、插件检查、失败指令和残留投递，使用：

```bash
python3 workspace/openclaw-task-system/scripts/runtime/health_report.py
```

现在健康报告会区分：

- `ok`
- `warn`
- `error`

并且会为每类问题给出直接可执行的修复建议。

## 7. 使用注意事项

- 任务系统的目标是提供真相，不是生成更漂亮的话术
- 静默超时通知必须保守，不能编造业务进展
- 任务终态必须明确，不允许长期悬挂
- 推广到多 agent 前，必须先让 `main` 路径稳定
