# Temporary Notes

> 最后更新：2026-04-05
> 角色：这是临时记录文件，不是正式主线。默认按 [ROADMAP.md](/Users/redcreen/.openclaw/workspace/openclaw-task-system/docs/ROADMAP.md) 推进；只有在明确要求“处理 TODO”时，才回读这里并整理回 roadmap。

## 当前焦点

- 总目标：
  - 让 `[wd]` 和所有 task 管理消息在用户视角第一时间可见
  - 让控制面消息始终最高优先级，不被普通 reply 排队
  - 最终覆盖所有 channel
- 当前阶段：
  - `Phase 2 / 最小 control-plane lane / scheduler`
- 当前子步骤：
  - `Step 7 / 收剩余少量 runner / startup / lifecycle 裸日志出口`

## 当前判断

- `Phase 1` 的协议和真相源已经基本定稳
- `Phase 2` 已经把 lane、优先级、terminal/preempt/supersede 冲突、sent/skipped/error 证据链搭起来了
- 当前最主要工作不是继续发散新功能，而是把剩余零散出口继续收进统一 scheduler 证据链

## 最近进展

- 删除了重复的 `docs/README.md`，根目录 `README.md` 作为唯一项目入口
- 把临时记录从根目录迁到 `docs/TODO.md`
- `continuation / host delivery / fulfilled shortcut / entered lifecycle` 已接进统一调度证据链
- 文档口径已统一到：
  - 项目是 OpenClaw 上的“任务运行时 + 控制面”
  - `ROADMAP` 是正式主线
  - `TODO` 只记临时事项

## 下一个动作

1. 继续清点并收口 `Phase 2 / Step 7` 剩余裸日志出口。
2. 当 `Phase 2` 退出条件满足后，切到 `Phase 3` 做统一用户状态投影的最后收口。
