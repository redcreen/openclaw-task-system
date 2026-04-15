[English](performance-baseline.md) | [中文](performance-baseline.zh-CN.md)

# Milestone 3 性能基线

## 这是什么

这份文档是 `Milestone 3：系统性能测试与优化` 的第一版 benchmark 合同。

目标不是给用户承诺机器无关的绝对 SLA，而是先把 repo 内可复现、可归因、可回归的性能入口固定下来。

当前基线只覆盖 repo-local、fixture-controlled 的运行时与 operator surface，不把宿主安装漂移或真实 OpenClaw host 状态混进第一轮预算。

## 第一轮 benchmark surface

| Surface | Scenario | 入口 | 固定 fixture | 当前预算 |
| --- | --- | --- | --- | --- |
| runtime lifecycle hooks | `hooks-cycle` | [`scripts/runtime/performance_baseline.py`](../../../scripts/runtime/performance_baseline.py) | 24 active + 32 archived tasks 的 temp task root | median `45ms`，p95 `60ms` |
| same-session rule path | `same-session-routing-rule` | 同上 | 1 个 in-memory running task | median `0.05ms`，p95 `0.1ms` |
| same-session classifier path | `same-session-routing-classifier` | 同上 | 16 active + 16 archived tasks + classifier-enabled temp config | median `115ms`，p95 `150ms` |
| control-plane / operator projection | `system-overview` | 同上 | 48 active + 96 archived tasks + planning / delivery artifacts | median `35ms`，p95 `50ms` |
| Growware preflight | `growware-preflight` | 同上 | 当前 repo root | median `8ms`，p95 `15ms` |
| plugin smoke | `plugin-smoke` | 同上 | 每次迭代一个 fresh temp task root | median `20ms`，p95 `30ms` |

预算规则：

- 这些预算是 repo-local guardrail，不是跨机器通用 SLA。
- 它们来自当前基线测量，并保留了足够 headroom，目的是先保护回归，而不是追求极限数值。
- `plugin_doctor.py`、完整 `main_ops.py dashboard` 和 host-install drift 路径暂时不进第一轮 gate，因为它们还混有宿主环境差异；等 repo-local / host-local 成本拆清后再扩面。

## 命令入口

完整第一轮 benchmark：

```bash
python3 scripts/runtime/performance_baseline.py --json
```

带 profile 和预算门禁的回归入口：

```bash
python3 scripts/runtime/performance_baseline.py \
  --profile-scenario hooks-cycle \
  --profile-scenario same-session-routing-classifier \
  --profile-scenario system-overview \
  --profile-top 8 \
  --enforce-budgets \
  --json
```

只盯单一热点：

```bash
python3 scripts/runtime/performance_baseline.py \
  --scenario system-overview \
  --profile-scenario system-overview \
  --json
```

## 第一轮 baseline（2026-04-14）

首次 baseline 复核命令：

```bash
python3 scripts/runtime/performance_baseline.py \
  --profile-scenario hooks-cycle \
  --profile-scenario same-session-routing-classifier \
  --profile-scenario system-overview \
  --profile-top 8 \
  --enforce-budgets \
  --json
```

当前结果：

| Scenario | Median | p95 | 结论 |
| --- | --- | --- | --- |
| `hooks-cycle` | `30.716ms` | `37.628ms` | runtime lifecycle path 已进入可复跑预算 |
| `same-session-routing-rule` | `0.0084ms` | `0.0088ms` | rule path 很轻，不是当前瓶颈 |
| `same-session-routing-classifier` | `91.4245ms` | `96.8046ms` | 当前主要成本来自 classifier subprocess + inflight lookup |
| `system-overview` | `17.5673ms` | `19.5657ms` | 首轮优化后已进入稳定 guardrail |
| `growware-preflight` | `1.2168ms` | `1.7194ms` | repo-local preflight 代价很低 |
| `plugin-smoke` | `11.5485ms` | `13.6066ms` | smoke path 目前不是性能压力点 |

## 首轮热点归因

首个明确热点是 `system-overview`。

优化前，同一 fixture 上它大约是：

- median `484.315ms`
- p95 `494.1653ms`

profile 直接指出了问题：

- `build_system_overview`
- `build_status_summary`
- `build_queue_snapshot`
- `_build_base_status_summary`

在 48 个 inflight task 上重复扇出，导致 `_build_base_status_summary` 被执行了 2352 次。

## 已落地的首轮优化

优化已经落在 [`scripts/runtime/task_status.py`](../../../scripts/runtime/task_status.py)：

- `list_inflight_statuses` 与 `build_system_overview` 先一次性预加载 inflight base status
- 同一批状态复用单个 queue snapshot，而不是为每个 task 重新构建
- `build_status_summary` 对单任务路径也复用同一批 inflight base status，而不是再做额外 fanout

同一热点在优化后的同一 fixture 上变成：

- median `17.5673ms`
- p95 `19.5657ms`

这轮收益约是 `27x` 量级，已经足够作为 Milestone 3 的第一项 evidence-backed optimization。

## 第二轮 baseline refresh（2026-04-14）

在首轮 `system-overview` 收敛之后，下一批 profile 暴露了两个更具体的热点：

- `hooks-cycle` 里跨 helper / hook path 的重复 inflight 冷读
- `system-overview` 里 planning 时间计算与 delivery artifact `stat` 扫描带来的尾延迟

复核命令：

```bash
python3 scripts/runtime/performance_baseline.py \
  --profile-scenario hooks-cycle \
  --profile-scenario same-session-routing-classifier \
  --profile-scenario system-overview \
  --profile-top 12 \
  --enforce-budgets \
  --json
```

复核结果：

| Scenario | Median | p95 | 结论 |
| --- | --- | --- | --- |
| `hooks-cycle` | `20.5577ms` | `34.4193ms` | hooks path 已重新回到预算内，并显著低于第一轮 gate |
| `same-session-routing-rule` | `0.0039ms` | `0.0043ms` | rule path 仍然足够轻 |
| `same-session-routing-classifier` | `20.3786ms` | `32.1622ms` | inflight lookup 基本退出主导，subprocess path 也回到预算内 |
| `system-overview` | `14.574ms` | `17.1183ms` | 第二轮尾延迟收敛后比首轮 baseline 还低 |
| `growware-preflight` | `1.2391ms` | `3.4425ms` | 仍然不是性能压力点 |
| `plugin-smoke` | `11.2371ms` | `16.0221ms` | smoke path 保持稳定 |

## 已落地的第二轮优化

第二轮优化分成三层：

- [`scripts/runtime/task_state.py`](../../../scripts/runtime/task_state.py) 现在把 inflight snapshot 提升到同进程跨 `TaskStore` 共享，并保留 generation-based invalidation，避免 hook / bridge / adapter 在同一次生命周期里重复冷读同一批 inflight 文件
- [`scripts/runtime/openclaw_hooks.py`](../../../scripts/runtime/openclaw_hooks.py)、[`scripts/runtime/lifecycle_coordinator.py`](../../../scripts/runtime/lifecycle_coordinator.py)、[`scripts/runtime/openclaw_bridge.py`](../../../scripts/runtime/openclaw_bridge.py) 和 [`scripts/runtime/main_task_adapter.py`](../../../scripts/runtime/main_task_adapter.py) 现在贯通同一个 `TaskStore`，让 register / progress / finalize active path 不再重复重建 store / queue 视图
- [`scripts/runtime/task_status.py`](../../../scripts/runtime/task_status.py) 现在在批处理层复用单个 `now_dt`，并对 delivery artifact 建立一次性目录索引，消掉 planning summary 与 delivery projection 的重复 `astimezone` / `stat` 开销

## 第三轮 baseline refresh（2026-04-14）

当重复 inflight rescan 被压缩掉之后，下一轮聚焦 profile 把 repo 自带 classifier 的剩余成本暴露得更清楚了：

- Growware same-session 自然语言 follow-up path 仍然会把 `python3 scripts/runtime/growware_feedback_classifier.py` 当作全新 subprocess 启动
- 主导成本已经不再是 inflight lookup，而是 classifier 进程启动，以及 classifier 决策后仍然要走的 task-state / ETA 读取

聚焦复核命令：

```bash
python3 scripts/runtime/performance_baseline.py \
  --profile-scenario hooks-cycle \
  --profile-scenario same-session-routing-classifier \
  --profile-top 8 \
  --json
```

同一 fixture 上复核到的 classifier path 结果：

- 进程内 fast path 落地前：median `90.0957ms`，p95 `132.2014ms`
- 进程内 fast path 落地后：median `24.9839ms`，p95 `38.5312ms`

这相当于在不改变自定义 classifier 行为契约的前提下，把 repo 自带 classifier path 做到了约 `3.6x` 的 median 改善。

## 已落地的第三轮优化

第三轮优化刻意保持窄范围：

- [`scripts/runtime/openclaw_hooks.py`](../../../scripts/runtime/openclaw_hooks.py) 现在会识别 same-session classifier command 是否解析到当前 runtime root 下 repo 自带的 `growware_feedback_classifier.py`
- 对这个已知本地命令，运行时会直接调用 `growware_feedback_classifier.classify(...)`，不再为每次 follow-up classification 额外启动 subprocess
- 用户自定义 classifier command 仍然保留现有的 `subprocess.run(...)` 路径，所以这次优化不会悄悄扩大成通用命令执行语义变更
- `register_from_payload` 现在还会把已经加载好的 runtime config 继续传给 inbound lifecycle registration，顺手去掉同一路径上的一次额外 config reload

## 回归保护

除了 benchmark gate，结构性回归也已经补上：

- [`tests/test_task_status.py`](../../../tests/test_task_status.py) 现在明确断言 `list_inflight_statuses` 和 `build_system_overview` 都只会对每个 inflight task 加载一次
- [`tests/test_task_state.py`](../../../tests/test_task_state.py) 保护 `TaskStore` inflight cache 的复用、跨 store snapshot 共享，以及写路径失效逻辑
- [`tests/test_openclaw_bridge.py`](../../../tests/test_openclaw_bridge.py) 明确断言同进程注册路径会复用同一个 inflight snapshot / store，而不是重复重建 queue state
- [`tests/test_main_task_adapter.py`](../../../tests/test_main_task_adapter.py) 保护 update path 会复用调用方传入的 `TaskStore`
- [`tests/test_openclaw_hooks.py`](../../../tests/test_openclaw_hooks.py) 明确断言 repo 自带 Growware classifier path 会保持进程内执行，而不会退回 subprocess spawn
- [`tests/test_performance_baseline.py`](../../../tests/test_performance_baseline.py) 校验 benchmark / profile 入口能稳定输出结构化结果

## Milestone 3 收口信号

Milestone 3 现在可以基于 benchmark 证据而不是直觉收口：

- 仓库已经拥有一套带固定 fixture、预算和复核命令的可复现 benchmark / profile 合同
- 最关键的 reviewed 热点已经具备前后对比证据，而不是“感觉快了”
- 改进路径同时受 benchmark budget 和结构性测试保护
- reviewed 的 repo-local 验证基线保持全绿，而 installed-runtime drift 被保留成 activation 准备阶段单独处理的问题

## 收口后的 Carry-Forward 候选

下面这些仍然值得继续测量，但它们现在属于 carry-forward 候选，而不是 Milestone 3 的收口 blocker：

- 在注册重扫和 repo 自带 classifier subprocess 启动都被拿掉之后，`hooks-cycle` 剩余的 active-task 解析和 archive ETA 采样成本
- `system-overview` 的 archive / projection 尾延迟抖动；它在噪声较大的 run 里仍然可能冲过 `50ms` 的 p95 预算
- 在不引入 host-state 噪音的前提下，再把 `main_ops` / `plugin_doctor` 的 repo-local 部分拉进第二轮 surface
