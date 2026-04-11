# Temporary Notes

> 最后更新：2026-04-11
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
- 已改进 running 态的 30 秒控制面消息：
  - 优先展示当前推进目标与阶段感，而不再只说“仍在处理中”
  - progress 更新会记录轻量 `progress_update_count`，供短跟进文案使用
- 已改进 `followup-scheduled` 的 `[wd]` 摘要 fallback：
  - 即使模型未显式给出 `followup_summary`，runtime 也会回退到基于时间表达与 follow-up message 的可读摘要
- 已补 `LLM planning health` 最小信号：
  - 基于 runtime truth source 投影 `recent success / timeout / tool-call completion / promise-without-task`
  - 已进入 `task_status / health_report / main_ops planning / dashboard / triage`
- 已补 `promise-without-task` 的 recovery 投影与文案：
  - `task_status / health_report / main_ops planning` 会给出结构化 recovery action
  - running 态短跟进会明确“补建真实任务 / 明确撤回承诺”的后续处理方向
- 已补 `planner-timeout` 的 recovery 投影与文案：
  - timeout 不再只落回泛化 `planning health` 提示
  - `dashboard / triage / running short followup` 会优先指向源 task 的恢复动作
- 已把 `overdue follow-up / pending plan` 的恢复动作对齐到 health 与 triage：
  - 不再只给泛化运维提示
  - 会直接给 source task / follow-up task 的检查命令
- 已把 future-first 的 `main_user_content_mode` contract 补进 acceptance 与 ops 投影：
  - `planning_acceptance.py` 会正式验证 `main_user_content_mode=none` 的 immediate-output contract
  - `task_status / main_ops health / planning` 会投影 future-first 计数与主要 mode

## 下一个动作

1. 继续扩 planning health 的真实样本覆盖与降级策略。
2. 把当前 runtime 中的 compound/delayed 语义 stopgap 逐步收敛成：
   - 明确的兼容桥接
   - 而不是长期主判断路径。

## 新增待办

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

- 扩 Phase 6 到更广的 planning coverage。
  - 当前状态：
    - Phase 6 最小闭环已经完成：
      - tool-created follow-up plan
      - promise guard
      - `promise-without-task` anomaly
      - overdue follow-up claim / ops projection
  - 下一步方向：
    - 扩更多 planning anomaly 类型与 recovery 文案
    - 扩更多 future-first / compound-request 真实例子
    - 评估更多 channel / agent 是否默认启用 tool-assisted planning
    - 在最小闭环之上继续补真实通道验收样本

- 收口 install drift 的真实安装态验证。
  - 当前状态：
    - drift truth source / dashboard / triage / only-issues 投影已经完成
    - 本地 OpenClaw 安装仍可能被 dangerous-code 检测拦住
  - 下一步方向：
    - 在允许的安装路径下验证 installable payload 真正进入本地安装态
    - 如果仍不能通过 `openclaw plugins install ./plugin`，明确项目内认可的同步/部署路径
    - 形成一份更稳定的“源码 payload -> 本地安装态”操作手册

- 提供更简单的 task CLI 查询入口。
  - 当前问题：
    - 运维上要查 task / queue / continuity，仍然主要依赖 `python3 scripts/runtime/main_ops.py ...`。
    - 对已经在用 `openclaw` CLI 的人来说，这条路径不够直觉，也不够短。
  - 当前状态：
    - 已补 `python3 scripts/runtime/task_cli.py ...` 薄包装入口：
      - `tasks`
      - `task <task_id>`
      - `session '<session_key>'`
    - 复用了现有 truth source，不新增第二套状态模型。
    - 文档示例已同步到 usage guide / README。
  - 后续方向：
    - 如果后面要进一步缩短命令，可再评估是否挂到宿主 `openclaw` CLI 下。

- same-session message routing 子项目已完成收口。
  - 当前状态：
    - 连续输入已正式路由到 `steering / queueing / control-plane / collect-more`
    - runtime-owned classifier、`[wd]` 回执、collecting-window、stable acceptance 已落地
  - 交付文档与入口：
    - [session_message_routing/README.md](./session_message_routing/README.md)
    - [session_message_routing/decision_contract.md](./session_message_routing/decision_contract.md)
    - [session_message_routing/test_cases.md](./session_message_routing/test_cases.md)
    - [session_message_routing/development_plan.md](./session_message_routing/development_plan.md)
    - `python3 scripts/runtime/same_session_routing_acceptance.py --json`


task_user_content 问题；
最初设计是为了解决 task tool 进入llm调用链时， 有些llm回复的中间结果（特别是任务安排类的中间结果，案例是帮我查一下杭州的天气在查一下宁波的天气，2分钟后告诉我杭州天气，3分钟后告诉我宁波天气类似这种；你也可以翻找下日志，看下第一条task_user_content出现时用的用例），不要给用户返回，被task 系统来接管，然后改写； 
但是这个问题现在污染面有点儿大，如何判断哪些是中间结果，需要被改写？ 
如果无法判定这一点，或者这一点很难来判断，那么task_user_content 这个机制还不如取消掉； 所以先从根本上分析下，能否准确的判断哪些是中间内容，如果能就继续修改bug，如果不能就彻底废弃；
参考分析与样例：
- [task_user_content_decision.md](../docs/task_user_content_decision.md)
- 当前状态：
  - Phase 4 已完成：运行时主链路已废弃 `task_user_content` 作为协议
  - Phase 5 已完成：历史清理工具、物理删除与测试收口已经落地
