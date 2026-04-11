[English](task_user_content_decision.md) | [中文](task_user_content_decision.zh-CN.md)

# 用户内容分离决策

## 核心结论

task-system 要把两类内容彻底分开：

- runtime-owned control-plane
- 用户真正要看的业务内容

这意味着：

- `[wd]`、调度结果、恢复状态由 runtime 投影
- 业务正文要通过结构化内容块或等价的受控路径输出
- tool 调度元数据不能直接混进主答复

## 为什么重要

如果不做这层分离，系统会不断退化成：

- 先把调度状态说给用户
- 再靠 regex 或句式表把不该出现的内部状态抹掉

这不是长期方案。

详细论证见 [task_user_content_decision.md](task_user_content_decision.md)。
