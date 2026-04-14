[English](verification-rules.md) | [中文](verification-rules.zh-CN.md)

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

只要项目本地 policy、OpenClaw 绑定或 local deploy 发生变化，就必须先把文档编译成 `.policy/`，再跑预检和 smoke 验证，最后才允许进入有副作用的绑定或部署动作。

`project-assistant` 负责把文档编译成 `.policy/`，Growware 只负责读取编译结果并执行验证结论。

## Allowed

- 预览 OpenClaw 绑定
- 编译或校验 `.policy/`
- 先跑 preflight 和 plugin smoke，再考虑本地 deploy
- 在人类批准后执行需要 `--write` 或 `--restart` 的本地动作

## Forbidden

- 在 policy 过期时把本地 deploy 当成可直接执行
- 直接跳过 `.policy/` 或 preflight 就修改 OpenClaw 绑定
- 把验证失败当成已经通过
- 把自动化当成可以绕过人工审批的理由

## Approval Required

- `growware_openclaw_binding.py --write --restart`
- `growware_local_deploy.py` 的任何真实写入步骤
- 对 deploy gate、plugin install flow 或审批边界的改动

## Verification

- `python3 scripts/runtime/growware_policy_sync.py --check --json`
- `python3 scripts/runtime/growware_preflight.py --json`
- `python3 scripts/runtime/growware_openclaw_binding.py --json`
- `python3 scripts/runtime/plugin_smoke.py --json`

## Machine Notes

- 这条规则会编译成 `.policy/rules/growware.project.local-deploy.v1.json`
- 如果 `.policy/` 与文档不一致，验证必须失败
- 真实写入前应保持人类审批边界清晰
