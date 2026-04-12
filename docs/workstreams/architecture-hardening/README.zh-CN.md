[English](README.md) | [中文](README.zh-CN.md)

# 架构整改

## 为什么要单独开这条工作流

Phase 0-6 主线已经交付，但实现层还带着两类结构性债务：

- task lifecycle 的所有权分散在 plugin hook 编排、runtime hook 命令和 task mutation helper 之间
- runtime 逻辑同时存在于 `scripts/runtime/` 和 `plugin/scripts/runtime/`，当前主要靠 drift 工具兜底，而不是从设计上消灭双重所有权

这条工作流的目标，就是在继续扩功能前，先把这两个边界收紧。

## 根因摘要

当前问题不是产品契约没立住，而是所有权边界不够硬。

典型症状包括：

- 生命周期 race 之后需要补救式 repair 逻辑
- terminal state 判定分散在多个层次
- 超大入口文件同时承担过多职责
- source/install drift 被当成运维问题，而不是设计问题

## 目标边界模型

整改后的目标模型是：

1. `plugin ingress`
   - 负责接 OpenClaw hook 事件
   - 负责归一化 channel/session 元数据
   - 负责调用 runtime-owned lifecycle 入口

2. `lifecycle coordinator`
   - 统一拥有 `register -> progress -> finalize -> terminal control-plane`
   - 统一决定任务什么时候进入 done / failed / blocked / awaiting-visible-output
   - 统一产出 runtime-owned receipt 和 terminal projection

3. `task truth-source layer`
   - 负责 durable task/session 状态落盘
   - 保持存储层职责，不再承担编排职责

4. `projection / ops layer`
   - 把同一份真相投影给用户和运维
   - 下游消费生命周期结论，而不是再次反推生命周期

## Runtime 真相源目标

runtime tree 必须收敛成单一 canonical source。

目标状态：

- 只有一套 runtime source 允许直接编辑
- 安装态 runtime 文件由这套 source 生成或严格同步
- install drift 工具保留，但它只作为校验，而不是维护者理解所有权的主要方式

## 分阶段整改

### Phase A：抽出 Lifecycle Contract

- 定义 lifecycle coordinator API 和状态迁移
- 明确这些职责到底归谁：
  - receipt 生成
  - visible progress sync
  - finalize skip / retry 规则
  - terminal control-plane projection

退出信号：

- 维护者能明确指出“哪个边界拥有 task lifecycle 决策”

### Phase B：给 Plugin 瘦身

- 把 lifecycle decision 逻辑从 `plugin/src/plugin/index.ts` 往外挪
- 让 plugin 主要只负责 OpenClaw ingress、transport metadata 和 host delivery
- 清掉那些只因生命周期所有权分裂而存在的 repair 逻辑

退出信号：

- plugin 侧 lifecycle repair 路径明显减少

### Phase C：收敛 Runtime Canonical Source

- 选定唯一 canonical runtime tree
- 把另一套 runtime tree 改成 generated 或严格同步产物
- 围绕这个选择补齐 packaging / install 流程文档

退出信号：

- 维护者不再把 `scripts/runtime` 和 `plugin/scripts/runtime` 当成并列真相源

### Phase D：恢复功能扩展

- 继续扩 planning anomaly coverage
- 继续补 planning / channel acceptance 样本

守则：

- 新功能不能继续扩大旧的 split-ownership 模式

## 非目标

- 不改 OpenClaw core
- 不把执行器/agent path 替换成新的 orchestrator
- 不继续扩 regex / phrase list 这类捷径

## 相关文档

- [../../architecture.zh-CN.md](../../architecture.zh-CN.md)
- [../../roadmap.zh-CN.md](../../roadmap.zh-CN.md)
- [../../todo.zh-CN.md](../../todo.zh-CN.md)
- [../../../.codex/status.md](../../../.codex/status.md)
- [../../../.codex/plan.md](../../../.codex/plan.md)
