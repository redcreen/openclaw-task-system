# 文档首页

[English](README.md) | [中文](README.zh-CN.md)

## 起步阅读

优先先读下面这套 canonical stack；`docs/` 里其他文件都应该是在补充、运维化或归档这些主问题，而不是与它们竞争主入口。

## 正式主文档栈

建议先看这几份：

- [../README.zh-CN.md](../README.zh-CN.md)：项目总览与已交付能力地图
- [roadmap.zh-CN.md](roadmap.zh-CN.md)：正式主线与已交付边界
- [architecture.zh-CN.md](architecture.zh-CN.md)：运行时模型与 truth-source contract
- [test-plan.zh-CN.md](test-plan.zh-CN.md)：发布门槛与验收预期

## 按目标阅读

| 目标 | 阅读这里 |
| --- | --- |
| 先理解项目今天到底交付了什么 | [../README.zh-CN.md](../README.zh-CN.md) |
| 理解运行时分层与 contract | [architecture.zh-CN.md](architecture.zh-CN.md) |
| 区分主线完成项与扩展方向 | [roadmap.zh-CN.md](roadmap.zh-CN.md) |
| 了解发布前要满足什么验证 | [test-plan.zh-CN.md](test-plan.zh-CN.md) |
| 查项目本地 policy source 与编译后的机器层 | [policy/README.zh-CN.md](policy/README.zh-CN.md) |
| 查运维命令与日常操作 | [usage_guide.zh-CN.md](usage_guide.zh-CN.md) |
| 查安装细节与 install drift | [plugin_installation.zh-CN.md](plugin_installation.zh-CN.md) |
| 查稳定参考资料 | [reference/README.zh-CN.md](reference/README.zh-CN.md) |

## 功能索引

- same-session routing：[reference/session_message_routing/README.zh-CN.md](reference/session_message_routing/README.zh-CN.md)
- 项目本地 policy source：[policy/README.zh-CN.md](policy/README.zh-CN.md)
- planning 与 future-first 边界：[llm_tool_task_planning.zh-CN.md](llm_tool_task_planning.zh-CN.md)
- compound delayed 边界：[compound_followup_boundary.zh-CN.md](compound_followup_boundary.zh-CN.md)
- channel 与 continuation lane 决策：[continuation_lane_decision_log.zh-CN.md](continuation_lane_decision_log.zh-CN.md)、[output_channel_separation_decision_log.zh-CN.md](output_channel_separation_decision_log.zh-CN.md)
- 外部对比与架构背景：[external_comparison.zh-CN.md](external_comparison.zh-CN.md)

## 目录角色

- [reference/README.zh-CN.md](reference/README.zh-CN.md)：放稳定 contract、长期设计参考和不适合堆进主入口的精确信息
- [workstreams/README.zh-CN.md](workstreams/README.zh-CN.md)：放仍在推进中的专项整改或探索性工作流，收敛后再回主栈
- [archive/README.zh-CN.md](archive/README.zh-CN.md)：放 dated evidence、已退役方案和需要留档但不该挤占主入口的历史材料
- [devlog/README.zh-CN.md](devlog/README.zh-CN.md)：放对未来维护仍有价值的实现经过、权衡和验证记录

## Markdown 治理

每份文档尽量只回答一个主问题，并放到最窄但稳定的目录里：

- 主入口文档留在仓库根目录或 `docs/`
- 稳定参考资料进入 [reference/](reference/README.zh-CN.md)
- 仍在整改中的专题先放 [workstreams/](workstreams/README.zh-CN.md)
- dated evidence 和退役材料进入 [archive/](archive/README.zh-CN.md)
- 有长期复盘价值的实现叙事进入 [devlog/](devlog/README.zh-CN.md)
