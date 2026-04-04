# CodexQuotaBar

一个原生 macOS 状态栏小程序，用来显示 `Codex` 剩余额度。

默认行为：

- 菜单栏显示 `Codex xx%`
- 每 60 秒自动刷新一次
- 下拉菜单展示各窗口额度、重置时间、手动刷新、退出
- 数据源使用 `openclaw status --usage --json`

## 构建

```bash
cd /Users/redcreen/.openclaw/workspace/openclaw-task-system
swift build
```

## 直接运行

```bash
cd /Users/redcreen/.openclaw/workspace/openclaw-task-system
swift run CodexQuotaBar
```

## 打包成 `.app`

```bash
cd /Users/redcreen/.openclaw/workspace/openclaw-task-system
chmod +x scripts/build_codex_quota_bar_app.sh
./scripts/build_codex_quota_bar_app.sh
open dist/CodexQuotaBar.app
```

## 可选环境变量

- `CODEX_QUOTA_OPENCLAW_PATH`
  - 自定义 `openclaw` 可执行文件路径

如果 `openclaw status --usage --json` 本身拿不到额度，这个小程序也会在菜单里直接显示对应错误。  
