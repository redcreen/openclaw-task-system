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

## 新增待办

- 改进 `仍在处理中` 的 30 秒控制面消息。
  - 当前问题：
    - 只说“仍在处理中”对用户来说信息量太低，体感像在傻等。
  - 目标方向：
    - 尽量补充有价值的执行信息，例如：
      - 当前在做什么
      - 预计还有几步
      - 当前大致在第几步
      - 如果卡在外部依赖，要明确说出阻塞点
    - 如果暂时拿不到结构化进度，也要优先给出比“处理中”更有解释力的状态摘要。

- 把 future-first 请求的即时可见输出策略做成结构化 contract。
  - 当前问题：
    - 类似“2分钟后告诉我明天天气，3分钟后告诉我后天天气”这种请求，系统仍可能先发业务结果，打乱“安排状态”和“未来结果”的语义边界。
  - 目标方向：
    - 由 planning/runtime 结构化决定 `main_user_content_mode`
    - future-first 默认先发 `[wd] 已安排妥当...`
    - 未来真正的业务内容留到到点 follow-up 再发
    - 不靠硬编码文本规则去猜哪些句子该抑制

- 改进 `followup-scheduled` 的 `[wd]` 文案摘要能力。
  - 当前问题：
    - 只说“将在 2分钟后 回复”太空泛，用户不知道回复什么。
  - 目标方向：
    - `[wd] 已安排妥当：2分钟后同步明天天气。`
    - `[wd] 已安排妥当：35分钟后提醒你查火车票。`
    - 调度确认消息必须包含人类可读的 follow-up 摘要。
