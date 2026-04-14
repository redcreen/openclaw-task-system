# Entry Routing

## Current Entry Direction
- Direction: `tool-first front door rollout verification`
- Status: `active`
- Why Now: `M16` 已完成 repo 自己能交付的统一前门；当前继续在代表性旧仓库上验证真实入口会先升级再输出结构化面板。

## Entry Routing Contract
- `继续 / 进展 / 交接` 的第一步必须先走统一前门，而不是直接自由解释旧 `.codex/status.md`。
- 统一前门必须先触发版本 preflight；旧控制面必须先补到当前代际，再允许继续读取真实状态。
- 统一前门只负责命令路由、版本 preflight 和结构化面板输出；真正的业务逻辑仍留在后端脚本。
- 自然语言 skill 负责把用户意图路由到统一前门，但不能再绕过统一前门自发生成第一屏。
- 宿主或插件级硬接入如果存在，应继续调用同一条统一前门，而不是复制一套平行逻辑。

## Front Door Layers
| Layer | Current Implementation | Responsibility |
| --- | --- | --- |
| natural-language routing | `SKILL.md` + prompt routing | 把用户说的 `项目助手 继续 / 进展 / 交接` 路由到同一条前门 |
| canonical tool front door | `scripts/project_assistant_entry.py` + `bin/project-assistant` | 统一解析模式、仓库路径和子命令别名 |
| mode backends | `continue_entry.py` / `progress_entry.py` / `handoff_entry.py` | 生成对应的结构化第一屏 |
| durable repo state | `.codex/*` + durable docs | 提供继续、进展和交接真正读取的真相层 |

## Preflight Contract
| Mode | Preflight Rule | Why |
| --- | --- | --- |
| `continue` | 先跑 `sync_resume_readiness.py`；旧代际必须先升级 | 不让旧 `.codex` 真相直接误导继续输出 |
| `progress` | 先跑 `sync_resume_readiness.py`；再生成完整看板 | 不让维护者读到过时代际的全局进展 |
| `handoff` | 先跑 `sync_resume_readiness.py`；再生成恢复包 | 不让交接包继续引用旧控制面结构 |

## Structured Output Contract
| Mode | First Output Must Be | Not Allowed First |
| --- | --- | --- |
| `continue` | 表格化 continue 面板 | 自由 prose 摘要 |
| `progress` | 表格化 maintainer dashboard | 只有自然语言长段落 |
| `handoff` | 可复制的结构化交接面板 | 先解释再慢慢拼交接信息 |

## Host / Tool Bridge Boundary
| Boundary | Repo Owns Today | Future Bridge |
| --- | --- | --- |
| tool-shaped entry | `project_assistant_entry.py` + CLI wrapper | 宿主或插件可以直接调用这条统一前门 |
| business logic | 后端脚本继续留在 skill repo | 宿主不应复制 continue/progress/handoff 逻辑 |
| hard host routing | 仅通过文档和统一前门定义边界 | 真正桌面级强绑定需由宿主 / 插件集成承接 |

## Next Entry Checks
1. 在代表性旧代际仓库上继续验证：`continue / progress / handoff` 会先升级再输出结构化面板。
2. 继续检查 task / 新 session 场景是否仍会绕过统一前门；如果会，记录为宿主桥接证据，而不是继续改后端脚本。
3. 如果未来引入插件或宿主硬接入，必须继续复用统一前门，而不是复制另一套命令逻辑。
