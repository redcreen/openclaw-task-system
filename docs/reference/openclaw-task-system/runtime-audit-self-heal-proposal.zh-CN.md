[English](runtime-audit-self-heal-proposal.md) | [中文](runtime-audit-self-heal-proposal.zh-CN.md)

# Runtime 日志审计与自修复方案

## 状态

- 状态：`proposal`
- 决策状态：仅讨论稿
- 里程碑状态：当前还不是活跃 roadmap milestone

这份文档描述的是 OpenClaw 宿主侧运维能力的一条候选演进线。

在用户明确确认方向之前，不应把它当作已批准的开发里程碑。

## 为什么需要这份方案

当前仓库已经具备比较完整的 repo-local 验证能力：

- testsuite
- release gate
- main-ops acceptance
- stable acceptance

这些验证仍然必要，但它们无法证明“你机器上的真实 OpenClaw 宿主今天是否健康”。

最近的宿主侧真实证据表明，即使 repo-local 验证是绿的，真实运行环境仍然可能有问题：

- 有 task 长时间停留在 `running`
- `~/.openclaw/delivery-queue/failed/` 里积累了失败外发残留
- cron 运行记录里存在真实的投递错误
- 至少有一条用户可见回复仍然带着内部 `<task_user_content>` 标记

所以缺的不是更多 testcase，而是一条基于真实日志和宿主数据的运行审计与恢复闭环。

## 问题定义

现在宿主侧健康信息分散在多套真相源里：

- `~/.openclaw/tasks/runs.sqlite`
- `~/.openclaw/delivery-queue/failed/`
- `~/.openclaw/cron/runs/*.jsonl`
- `~/.openclaw/logs/config-health.json`
- 最近真实的用户请求与回复摘要

这带来四个运维缺口：

1. 很容易因为 tests 通过，就误判系统“健康”
2. 用户可见质量问题还没有被当成一等健康问题
3. 修复动作仍然是零散手工操作
4. 目前没有一条适合日常人工巡检或定时任务调度的统一指令

## 目标

这条能力线最终应该提供一条稳定指令，满足下面六点：

1. 直接读取 `~/.openclaw` 里的真实宿主数据
2. 从运维视角给出系统健康判断
3. 从用户视角给出行为质量判断
4. 把问题分成 `可自动修复`、`需人工复核`、`只能人工处理`
5. 先支持 dry-run，再支持有限自动修复
6. 后续可以挂到定时任务里跑，但不把宿主专属噪音写回 repo 文档主栈

## 非目标

这份方案不打算做下面这些事：

- 用它替代 tests、acceptance 或 release gate
- 在没有明确策略前自动改写业务回复或用户历史
- 把“没有错误日志”当成“用户体验正常”
- 在没有 dry-run 和安全边界前静默修改宿主数据
- 把每一种 host-side warning 都做成自动修复

## 拟定指令面

统一审计入口：

```bash
python3 scripts/runtime/openclaw_runtime_audit.py
python3 scripts/runtime/openclaw_runtime_audit.py --json
python3 scripts/runtime/openclaw_runtime_audit.py --lookback-hours 48 --recent-limit 20
```

后续计划中的修复入口：

```bash
python3 scripts/runtime/openclaw_runtime_repair.py --dry-run
python3 scripts/runtime/openclaw_runtime_repair.py --apply-safe
python3 scripts/runtime/openclaw_runtime_repair.py --json --dry-run
```

当前仓库已经有第一步的只读审计入口。

它应被视为 Phase 0 的 bootstrap，不应被误认为整套自修复系统已经完成。

## 审计模型

同一套宿主真相源，必须同时产出两种视角。

### 1. 运维视角

这个视角回答：

- 当前宿主是否还值得信任
- 有没有卡死的 running task
- 失败投递是否在积累
- cron 是否最近在持续报错
- 配置健康是否稳定

代表性检查项：

- 超过阈值的 stale running task
- failed delivery 的数量、年龄、重试次数、channel 分布
- 最近 cron error 数量与最新错误摘要
- config health 缺失或 suspicious signature
- 最近 task 的 status / delivery status 分布

### 2. 用户视角

这个视角回答：

- 用户最近问了什么
- 系统实际回复了什么
- 这些回复是否看起来对用户安全
- 是否存在内部标记或控制面信息泄漏

代表性检查项：

- 最近 request / reply 摘要对
- 用户可见输出里出现 `<task_user_content>`
- internal runtime context 或 subagent 噪音混入用户视图
- task 成功结束但没有可用 terminal summary
- 同一用户 / channel / session 上的连续失败

## 拟定问题分层

| 问题类型 | 例子 | 严重级别 | 是否可自动修复 | 默认处理 |
| --- | --- | --- | --- | --- |
| stale task state | task 几天后仍是 `running` | error | 后续可能支持，但默认不自动修 | 先 inspect，再决定 resume / fail / purge |
| retryable delivery residue | 短暂网络失败且目标有效 | warn | 可以 | 走 host retry |
| invalid recipient / binding | Telegram slash 目标无法解析 | warn 或 error | 不可以 | 先修地址或会话绑定 |
| config health drift | suspicious signature 或 health log 缺失 | warn | 不可以 | 先检查配置来源 |
| cron delivery failure | 定时任务执行了，但外发失败 | warn | 后续部分可支持 | 先查 job target 和 rerun |
| user-visible content leak | 已投递回复里仍含 `<task_user_content>` | error | 不应静默自动修 | 立即提升并修输出边界 |
| internal context leak | internal / subagent 文本暴露给用户 | error | 不应静默自动修 | 先修边界再谈重发 |

## 拟定修复策略

自动修复必须分层，并且保守。

### 可进入自动修复候选

这些问题在 dry-run 验证稳定后，可以进入 `--apply-safe`：

- retryable failed delivery，且目标元数据有效
- 已有规则能证明安全的 stale delivery residue cleanup
- 明显重复或被更新结果覆盖的 failed-delivery artifact
- 已确认 outage 清除后的补发重试

### 必须先 dry-run，再人工复核

- stale running task
- reply target 或投递目标不明确的 cron failure
- 部分 config drift
- 同一 audience 的连续失败爆发

### 只能人工处理

- 用户可见内容泄漏
- internal marker 泄漏
- recipient 映射错误
- 会影响 active user task history 的破坏性清理
- 会改变业务回复语义的任何修复

## 拟定架构

### Layer 1：Host-Side Audit Reader

输入：

- `runs.sqlite`
- failed delivery queue
- cron run logs
- config health
- 最近用户可见 task 摘要

输出：

- 稳定 JSON 结构
- 人类可读 markdown 摘要

### Layer 2：规则引擎

把原始信号映射成：

- severity
- finding code
- count
- explanation
- remediation command
- repair eligibility

### Layer 3：Repair Planner

把问题翻译成明确动作：

- `retry-failed-deliveries`
- `reconcile-stale-delivery-artifacts`
- `inspect-stale-running-task`
- `inspect-user-visible-content-leak`
- `inspect-cron-binding`

这个层必须先支持 `--dry-run`。

### Layer 4：Repair Executor

只执行已经被归类为 safe 的动作。

要求：

- 记录它改了什么
- 输出 before / after 差异
- 修复失败时不能静默吞掉

### Layer 5：Scheduled Operation

后续定时任务可以按下面的节奏跑：

1. audit
2. classify
3. 可选地 apply safe fixes
4. 输出 compact summary
5. 把审计记录留在宿主本地

建议的日常审计输出目录：

- `~/.openclaw/logs/runtime-audit/`

默认不要把宿主专属的每日审计产物写回 repo 文档。

## 拟定分阶段落地

### Phase 0：只读审计 bootstrap

目标：

- 先有一条可靠的真实宿主审计命令

范围：

- 运维视角
- 用户视角
- stale task
- failed delivery
- cron error
- config health
- 用户可见 marker 泄漏

当前状态：

- `openclaw_runtime_audit.py` 已经作为 bootstrap 存在

退出条件：

- 这条命令稳定到足以成为日常人工值守入口

### Phase 1：Repair Planning Contract

目标：

- 把审计结果统一翻译成 repair action

范围：

- action kind
- safety class
- dry-run preview
- recommended command

退出条件：

- 主要问题类型都有一致的 repair plan 结构

### Phase 2：Safe Repair Dry-Run

目标：

- 在不改宿主数据的前提下模拟 safe repair

范围：

- retryable failed delivery
- stale delivery cleanup
- 有边界的 cron rerun 建议

退出条件：

- dry-run 结果足够可信，可以给人审阅后执行

### Phase 3：Safe Repair Apply

目标：

- 允许一条明确命令执行 safe subset

退出条件：

- safe repair 路径具备幂等性、可观察性和基本可回退性

### Phase 4：定时日常运行

目标：

- 每天自动审计，必要时执行 safe repair

范围：

- host-local 日志输出
- 有问题时返回非零退出码
- 支持通知或值守摘要

退出条件：

- 定时任务能运行，但不会制造“假健康”结论

## 运行契约

日常人工巡检：

```bash
python3 scripts/runtime/openclaw_runtime_audit.py
```

机器可读巡检：

```bash
python3 scripts/runtime/openclaw_runtime_audit.py --json
```

未来定时执行形态：

```bash
python3 scripts/runtime/openclaw_runtime_audit.py --json && \
python3 scripts/runtime/openclaw_runtime_repair.py --dry-run --json
```

审计命令应该在存在可操作问题时返回非零退出码。

这样 cron 或其他调度器才能把审计失败当成真实事件，而不是装饰性报告。

## 需要先讨论清楚的决策点

在把这份 proposal 升级成活跃 milestone 之前，建议先明确下面几件事：

1. 定时任务先保持 `audit-only`，还是允许自动执行 safe fixes
2. 首批自修复范围是 Feishu、Telegram，还是两者都做
3. stale task 多激进才允许自动恢复或回收
4. 用户可见内容泄漏是否要触发立即高优先级告警
5. 定时摘要最终发到哪里：只写本地日志、回 OpenClaw、还是两者都要

## 推荐下一步

先不要把这条线直接升级成正式开发里程碑。

先把这份方案当作讨论基线，把自动修复边界谈清楚，再把批准后的子集提升成一个有名字的 roadmap candidate 或活跃 workstream。
