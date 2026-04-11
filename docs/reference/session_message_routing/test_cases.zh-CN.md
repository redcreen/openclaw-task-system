# Test Cases

[English](test_cases.md) | [中文](test_cases.zh-CN.md)

### 1. 目标

这份文件把设计样例直接整理成后续自动化测试候选。

每条 case 都至少包含：

- 初始运行态
- 用户连续输入
- 预期 classification
- 预期 execution decision
- 预期 `[wd]`

### 2. 一眼看懂的总图

```mermaid
flowchart TD
    classDef c1 fill:#e8f1fb,stroke:#4a88c7,color:#0f2b46,stroke-width:1.2px;
    classDef c2 fill:#efe7ff,stroke:#7a56d1,color:#26184f,stroke-width:1.2px;
    classDef c3 fill:#e7f8ec,stroke:#2c9b63,color:#113b27,stroke-width:1.2px;
    classDef c4 fill:#fff1e6,stroke:#d97706,color:#5b3306,stroke-width:1.2px;

    A["control-plane"]:::c1
    B["steering"]:::c2
    C["queueing"]:::c3
    D["collect-more"]:::c4

    B --> B1["merge-before-start"]
    B --> B2["interrupt-and-restart"]
    B --> B3["append-as-next-step"]
    C --> C1["queue-as-new-task"]
    D --> D1["enter-collecting-window"]
```

### 3. 核心 case 表

| Case | 初始状态 | 连续输入 | classification | decision |
|---|---|---|---|---|
| A | 无 active task | `帮我查杭州天气` | `queueing` | `queue-as-new-task` |
| B | active task = `整理简历`，尚未开始 | `顺便改成偏产品经理方向` | `steering` | `merge-before-start` |
| C | active task = `整理简历`，running 且无副作用 | `再口语一点` | `steering` | `interrupt-and-restart` |
| D | active task = `写文件并已落盘` | `再补一段结论` | `steering` | `append-as-next-step` |
| E | active task = `整理简历` | `另外再查一下杭州天气` | `queueing` | `queue-as-new-task` |
| F | active task = `整理简历` | `先别开始，我还会继续补两条` | `collect-more` | `enter-collecting-window` |
| G | active task = 任意 | `继续` | `control-plane` | `handle-as-control-plane` |

### 4. 详细样例

#### Case B: 未开始时的 steering merge

**初始状态**

- active task: `整理简历并输出产品经理方向版本`
- stage: `queued`

**输入**

1. `帮我看一下这份简历`
2. `顺便改成偏产品经理方向`

**预期**

- classification: `steering`
- decision: `merge-before-start`
- `[wd]`:
  - `[wd] 已把这条补充并入当前任务；因为当前任务还没正式开始执行。`

#### Case C: 运行中但可安全重启

**初始状态**

- active task: `整理简历并输出产品经理方向版本`
- stage: `running-no-side-effects`

**输入**

1. `帮我把这份简历整理成更完整的版本`
2. `再口语一点`

**预期**

- classification: `steering`
- decision: `interrupt-and-restart`
- `[wd]`:
  - `[wd] 已按这条补充重启当前任务；因为当前执行仍处于可安全改写阶段。`

#### Case D: 已有副作用，不直接重跑

**初始状态**

- active task: `写 README 草稿`
- stage: `running-with-side-effects`
- 已写出部分文件

**输入**

1. `把 README 重写一遍`
2. `最后再补一段结论`

**预期**

- classification: `steering`
- decision: `append-as-next-step`
- `[wd]`:
  - `[wd] 这条已记入当前任务的后续步骤；因为当前执行已产生外部动作，不直接中断重跑。`

#### Case E: 明确新目标

**初始状态**

- active task: `整理简历`
- stage: `running`

**输入**

1. `帮我整理这份简历`
2. `另外再查一下杭州天气`

**预期**

- classification: `queueing`
- decision: `queue-as-new-task`
- `[wd]`:
  - `[wd] 这条已单独排队；因为它引入了新的独立目标，不覆盖当前任务。`

#### Case F: collect-more

**初始状态**

- active task: `无` 或 `queued`

**输入**

1. `我接下来会连续发三条，你先别开始`
2. `第一条：整理目录`
3. `第二条：补 README`
4. `第三条：最后给我总结`

**预期**

- 第 1 条 classification: `collect-more`
- decision: `enter-collecting-window`
- `[wd]`:
  - `[wd] 先不开始执行；我会继续收集你接下来的补充后再一起处理。`

### 5. classifier 歧义 case

这类 case 用来验证“什么时候需要 LLM classifier”。

| Case | 输入 | 为什么歧义 | 预期 |
|---|---|---|---|
| H | `再补一点业务视角` | 可能是补充当前文案，也可能是新分析任务 | 触发 classifier |
| I | `再来一个版本` | 可能是当前任务继续，也可能是新任务 | 触发 classifier |
| J | `这个也一起看` | 依赖上文指代，规则不够 | 触发 classifier |

这些 case 的重点不是固定唯一结果，而是验证：

1. runtime 能识别它们是歧义场景
2. runtime 会触发 classifier
3. runtime 能给出 decision trace 和 `[wd]`

### 6. 自动化测试建议

建议后续拆成 3 层测试：

1. pure contract tests
   - 输入状态 + 输入消息
   - 断言 classification / decision / wd 模板

2. classifier trigger tests
   - 断言哪些场景必须触发 classifier
   - 断言明显场景不会误触发 classifier

3. end-to-end session tests
   - 连续输入多条消息
   - 断言最终 task queue / steering trace / wd receipt

### 6.1 receipt coherence 回归项

这组 case 专门防止一种断层：truth source 里的 routing decision 是对的，但用户最终看到的文案还是旧的、泛化的，或者被静默跳过。

| Case | 初始状态 | 连续输入 | 预期 |
|---|---|---|---|
| K | 已存在 queued early-ack marker | 后续消息被 runtime 判成 `same-session-routing-receipt` | plugin 仍然要发 runtime-owned `[wd]`，不能因为旧的 queue ack marker 就直接跳过 |
| L | 同 session 里只剩 stale observed 占位消息，例如 `在么`，或 `received/manual-review` 任务，没有 `queued/running` task | 用户发来新的第一条真实请求 | runtime 会复用这条 observed task 作为 pre-start takeover target，并返回 merge 风格的 runtime-owned `[wd]` |

### 7. review 时重点看什么

这份 case 包 review 时，建议重点看 4 件事：

1. 哪些 case 应该完全靠规则
2. 哪些 case 必须进 classifier
3. 哪些 running stage 允许中断重启
4. `[wd]` 是否足够短、够真、够清楚
