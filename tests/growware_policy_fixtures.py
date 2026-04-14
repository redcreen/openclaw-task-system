from __future__ import annotations

import json
from pathlib import Path

from tests.runtime_loader import load_runtime_module


growware_policy_sync = load_runtime_module("growware_policy_sync")


POLICY_README_EN = """[English](README.md) | [中文](README.zh-CN.md)

# Policy Source

## Purpose

This directory is the human-readable policy source for the Growware pilot on `openclaw-task-system`.

The repo now uses a two-layer policy model:

- `docs/policy/*.md` is the human source of truth
- `.policy/` is the compiled machine execution layer

Growware, daemon, and terminal takeover should read `.policy/` at runtime.
"""

POLICY_README_ZH = """[English](README.md) | [中文](README.zh-CN.md)

# Policy Source

## 目的

这个目录是 `openclaw-task-system` 的 Growware 项目本地人类可读 policy source。

现在仓库采用两层 policy 模型：

- `docs/policy/*.md` 是人类真相源
- `.policy/` 是编译后的机器执行层

Growware、daemon 和 terminal takeover 运行时都应读取 `.policy/`。
"""

INTERACTION_EN = """[English](interaction-contracts.md) | [中文](interaction-contracts.zh-CN.md)

# Growware Feedback Intake Policy

## Metadata

- id: `growware.feedback-intake.same-session.v1`
- kind: `interaction-contract`
- status: `active`
- owners:
  - `project-owner`
  - `growware`
- applies_to:
  - `scripts/runtime/growware_feedback_classifier.py`
  - `scripts/runtime/growware_preflight.py`
- effect: `deny-without-approval`

## Rule

Growware intake should treat refinements and bug follow-ups as the active task, and separate goals as new tasks.

## Allowed

- keep same-task steering
- queue independent requests
- keep `inline code` intact

## Forbidden

- bypass `.policy/`
- change classifier signals without approval

## Approval Required

- change signal lists
- change default execution source

## Verification

- `python3 scripts/runtime/growware_policy_sync.py --check --json`
- `python3 scripts/runtime/growware_preflight.py --json`
- `python3 -m unittest tests.test_growware_feedback_classifier tests.test_growware_preflight`

## Machine Notes

- defaultExecutionSource: `daemon-owned`
"""

INTERACTION_ZH = """[English](interaction-contracts.md) | [中文](interaction-contracts.zh-CN.md)

# Growware 反馈 intake policy

## Metadata

- id: `growware.feedback-intake.same-session.v1`
- kind: `interaction-contract`
- status: `active`
- owners:
  - `project-owner`
  - `growware`
- applies_to:
  - `scripts/runtime/growware_feedback_classifier.py`
  - `scripts/runtime/growware_preflight.py`
- effect: `deny-without-approval`

## Rule

Growware intake 要把修订和 bug follow-up 留在当前 task，把独立目标排成新任务。

## Allowed

- 保持同任务 steering
- 独立请求排队
- 保留 `inline code` 不被吞掉

## Forbidden

- 绕过 `.policy/`
- 未批准就改 classifier signals

## Approval Required

- 更改 signal 列表
- 更改默认执行来源

## Verification

- `python3 scripts/runtime/growware_policy_sync.py --check --json`
- `python3 scripts/runtime/growware_preflight.py --json`
- `python3 -m unittest tests.test_growware_feedback_classifier tests.test_growware_preflight`

## Machine Notes

- defaultExecutionSource: `daemon-owned`
"""

VERIFICATION_EN = """[English](verification-rules.md) | [中文](verification-rules.zh-CN.md)

# Growware Verification Rule

## Metadata

- id: `growware.project.local-deploy.v1`
- kind: `verification-rule`
- status: `active`
- owners:
  - `project-owner`
  - `growware`
- applies_to:
  - `scripts/runtime/growware_policy_sync.py`
  - `scripts/runtime/growware_preflight.py`
  - `scripts/runtime/growware_openclaw_binding.py`
  - `scripts/runtime/growware_local_deploy.py`
  - `scripts/runtime/plugin_smoke.py`
- effect: `deny-without-approval`

## Rule

Project-local policy changes must sync `.policy/` and pass preflight before binding or deploy.

## Allowed

- preview binding
- run preflight
- run plugin smoke

## Forbidden

- mutate OpenClaw binding with stale policy
- skip approval for live write steps

## Approval Required

- `growware_openclaw_binding.py --write --restart`
- `growware_local_deploy.py` write steps

## Verification

- `python3 scripts/runtime/growware_policy_sync.py --check --json`
- `python3 scripts/runtime/growware_preflight.py --json`
- `python3 scripts/runtime/growware_openclaw_binding.py --json`
- `python3 scripts/runtime/plugin_smoke.py --json`
"""

VERIFICATION_ZH = """[English](verification-rules.md) | [中文](verification-rules.zh-CN.md)

# Growware 验证规则

## Metadata

- id: `growware.project.local-deploy.v1`
- kind: `verification-rule`
- status: `active`
- owners:
  - `project-owner`
  - `growware`
- applies_to:
  - `scripts/runtime/growware_policy_sync.py`
  - `scripts/runtime/growware_preflight.py`
  - `scripts/runtime/growware_openclaw_binding.py`
  - `scripts/runtime/growware_local_deploy.py`
  - `scripts/runtime/plugin_smoke.py`
- effect: `deny-without-approval`

## Rule

项目本地 policy 变化后，必须先同步 `.policy/` 并通过 preflight，再做 binding 或 deploy。

## Allowed

- 预览 binding
- 跑 preflight
- 跑 plugin smoke

## Forbidden

- policy 过期还直接改 OpenClaw binding
- 跳过 live write 的审批

## Approval Required

- `growware_openclaw_binding.py --write --restart`
- `growware_local_deploy.py` 写入步骤

## Verification

- `python3 scripts/runtime/growware_policy_sync.py --check --json`
- `python3 scripts/runtime/growware_preflight.py --json`
- `python3 scripts/runtime/growware_openclaw_binding.py --json`
- `python3 scripts/runtime/plugin_smoke.py --json`
"""


def write_policy_sources(root: Path) -> None:
    policy_dir = root / "docs" / "policy"
    policy_dir.mkdir(parents=True, exist_ok=True)
    (policy_dir / "README.md").write_text(POLICY_README_EN, encoding="utf-8")
    (policy_dir / "README.zh-CN.md").write_text(POLICY_README_ZH, encoding="utf-8")
    (policy_dir / "interaction-contracts.md").write_text(INTERACTION_EN, encoding="utf-8")
    (policy_dir / "interaction-contracts.zh-CN.md").write_text(INTERACTION_ZH, encoding="utf-8")
    (policy_dir / "verification-rules.md").write_text(VERIFICATION_EN, encoding="utf-8")
    (policy_dir / "verification-rules.zh-CN.md").write_text(VERIFICATION_ZH, encoding="utf-8")


def sync_policy(root: Path) -> dict[str, object]:
    write_policy_sources(root)
    return growware_policy_sync.write_policy_catalog(root)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
