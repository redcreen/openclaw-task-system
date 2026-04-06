# Temporary Notes

> 最后更新：2026-04-05
> 角色：这是临时记录文件，不是正式主线。默认按 [roadmap.md](./roadmap.md) 推进；只有在明确要求“处理 TODO”时，才回读这里并整理回 roadmap。

## 当前焦点

- 当前正式主线已完成，默认以 [roadmap.md](./roadmap.md) 记录的新候选方向为准。
- 当前新增约束：
  - task-system 的主要职责是监督执行与暴露真实状态，而不是替代 LLM 或原执行架构。

## 当前判断

- 当前系统的大方向已经是 supervisor-first：
  - `[wd]`
  - follow-up
  - watchdog / continuity
  - restart recovery
  - dashboard / triage
  - truth source
- 但还存在一个明确偏离点：
  - runtime 仍然对 delayed / compound 请求做了一部分语义判断与 stopgap 拆解
  - 这部分应被视为兼容桥接，而不是长期职责边界

## 最近进展

- 新增了复合 delayed follow-up 的边界文档：
  - [compound_followup_boundary.md](./compound_followup_boundary.md)
- 新增了 LLM tool-assisted planning 设计稿：
  - [llm_tool_task_planning.md](./llm_tool_task_planning.md)
- 已把“task-system 是监工，不是执行者替身”写进 README、architecture、roadmap

## 下一个动作

1. 评估并实现 `LLM planning health` 信号。
2. 设计 `promise-without-task` 检测与 anomaly 投影。
3. 把当前 runtime 中的 compound/delayed 语义 stopgap 逐步收敛成：
   - 明确的兼容桥接
   - 而不是长期主判断路径。
