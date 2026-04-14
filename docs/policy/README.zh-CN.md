[English](README.md) | [中文](README.zh-CN.md)

# Policy Source

## 目的

这个目录是 `openclaw-task-system` 的 Growware 项目本地人类可读 policy source。

现在仓库采用两层 policy 模型：

- `docs/policy/*.md` 是人类真相源
- `.policy/` 是编译后的机器执行层

Growware、daemon 和 terminal takeover 运行时都应读取 `.policy/`。

## 当前 policy 集合

- [interaction-contracts.md](interaction-contracts.md)：Growware 反馈 intake 与 same-session routing contract
- [verification-rules.md](verification-rules.md)：项目本地验证与 deploy gate contract

## 编译与验证

编译或刷新机器层：

```bash
python3 scripts/runtime/growware_policy_sync.py --write --json
```

不写入，只验证：

```bash
python3 scripts/runtime/growware_policy_sync.py --check --json
```

当 policy 文档变化时，先刷新 `.policy/`，再依赖运行时 intake 或 deploy 行为。
