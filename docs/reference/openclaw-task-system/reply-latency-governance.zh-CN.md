[English](reply-latency-governance.md) | [中文](reply-latency-governance.zh-CN.md)

# 回复时延治理

## 目的

这份文档记录当前针对宿主真实会话回复慢问题的治理专题。

它用来回答：

- 为什么 Milestone 3 已收口后，仓库又重新打开了一条性能相关主线
- 哪些证据说明“慢”是真的，而且慢在什么地方
- 哪些贡献者已经大到值得进入优化队列
- 在恢复 activation 准备之前，必须先满足什么条件

## 触发条件

当前触发点是一条 `2026-04-15 23:44` 之后的真实 Telegram 会话。该会话的回复耗时大约在 `16s-50s`，但 repo-local benchmark 路径仍然保持全绿。

当前已测得的现象包括：

- 总耗时主要落在 LLM 段
- 工具时间只在少数轮次里成为次要贡献
- 静态上下文约 `140,465 chars`
- tool schema surface 是最大的静态块
- startup 和 transcript 累积会把额外上下文继续压到后续轮次

## Durable Audit 入口

后续统一使用 repo 内的审计命令，而不是继续手工拆日志：

```bash
python3 scripts/runtime/session_latency_audit.py --session-key 'agent:main:telegram:direct:8705812936' --json
```

这条命令会输出：

- 每轮总耗时
- LLM 时间与 tool 时间拆解
- 每轮开始前的 transcript chars
- startup 留给后续轮次的 carryover
- 来自 `sessions.json` 的静态 prompt 组成
- top tool / workspace / skill 贡献者

## 当前归因

当前已测得的归因顺序是：

1. 静态 prompt 重量
2. per-turn wrapper tax
3. startup transcript carryover
4. session 生命周期内持续增长的 transcript
5. 少数轮次里的残余工具耗时

这意味着当前用户可见 slowdown 的主因并不是 repo 热路径里的 task lifecycle 代码，而是模型在处理过重的上下文。

## 治理队列

### P0：静态 Prompt 减负

- tool schema surface
- system prompt weight
- 不必要的 skills 暴露
- 不必每轮携带的 workspace bootstrap 文件

### P0：Wrapper 与 Startup 减负

- per-turn task-system wrapper 形状
- startup 读文件行为
- 哪些 startup 产物不应该继续留在后续 transcript 中

### P1：Transcript 增长约束

- 哪些历史产物应该改成摘要，而不是继续保留全文
- 后续轮次默认不该继承哪些内容

### P1：Activation 恢复门槛

- 什么证据足以证明 slowdown 已经被约束住
- 恢复有界 activation 准备时，哪些 guardrail 必须继续保持全绿

## 第一轮小闭环

`TG-2` 的第一轮小闭环已经完成。

这一轮先打默认 planning contract，因为这部分成本由仓库拥有，而且每一轮 planning 都会重复支付：

- 默认 planning system prompt：`1531` -> `954` chars
- 默认 planning runtime wrapper：`1168` -> `696` chars

这次刻意没有先动 tool schema。相比之下，planning prompt 和 wrapper 是更高确定性的减负点，可以先压掉重复成本，同时不改 capability exposure，也不掩盖 startup carryover 语义。

这条紧凑 contract 现在受下面两组测试保护：

- `plugin/tests/tool-planning-flow.test.mjs`
- `tests/test_task_config.py`

## 恢复条件

只有当下面几条同时成立时，activation 准备才允许回到主线：

- 触发会话已经可以通过 audit 命令稳定复跑
- 最大的 prompt/context 贡献者已经有明确的 keep / shrink / remove 决策
- 已选择的 reductions 不会破坏必须保留的 runtime safety 和 agent capability
- 仓库已经写清楚：什么 latency/context 证据足以把该问题视为“有界”而非“继续阻塞主线”

## 验证

治理专题始终建立在现有 repo-local guardrail 之上：

```bash
python3 scripts/runtime/performance_baseline.py --profile-scenario hooks-cycle --profile-scenario same-session-routing-classifier --profile-scenario system-overview --profile-top 8 --enforce-budgets --json
python3 scripts/runtime/session_latency_audit.py --session-key 'agent:main:telegram:direct:8705812936' --json
python3 scripts/runtime/growware_preflight.py --json
python3 -m unittest tests.test_session_latency_audit tests.test_performance_baseline -v
python3 scripts/runtime/runtime_mirror.py --write
python3 scripts/runtime/plugin_doctor.py --json
python3 scripts/runtime/plugin_smoke.py --json
```
