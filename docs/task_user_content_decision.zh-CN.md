[English](task_user_content_decision.md) | [中文](task_user_content_decision.zh-CN.md)

# 用户内容分离决策

## 最终结论

`task_user_content` 已不再是长期有效的 runtime 协议边界。

长期保留的结论是要把两类内容彻底分开：

- runtime-owned control-plane
- 用户真正要看的业务内容

这意味着：

- `[wd]`、调度结果、恢复状态由 runtime 投影
- 用户可见业务内容必须走显式、受控的输出通道
- tool 调度元数据不能直接混进主答复

## 当前保留什么

当前仓库只保留：

- sanitize 与 hard-block 行为
- 历史泄漏审计
- 历史清理工具

## 为什么

runtime 可以可靠信任结构化 planning 状态。

它不能长期可靠地信任一对文本标签，来承担“用户可见输出”和“隐藏 planning 状态”之间的正式协议边界。

## 接受的替代方向

正式接受的方向是输出通道分离：

- scheduling 与 control-plane truth 先留在 runtime state
- runtime 再把这些状态投影成 `[wd]` 或其他控制面消息
- 业务内容只有在安全时才单独投影给用户

## 为什么重要

如果不做这层分离，系统会不断退化成：

- 先把调度状态说给用户
- 再靠 regex 或句式表把不该出现的内部状态抹掉

这不是长期方案。

## 运维后果

当前仓库仍保留 `task_user_content` 相关历史校验，只为了防止旧泄漏模式悄悄回归，而不是继续把它当作正式协议边界。
