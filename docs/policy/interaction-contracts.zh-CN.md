[English](interaction-contracts.md) | [中文](interaction-contracts.zh-CN.md)

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
  - `plugin/scripts/runtime/growware_feedback_classifier.py`
  - `scripts/runtime/growware_project.py`
  - `scripts/runtime/growware_preflight.py`
  - `docs/reference/openclaw-task-system/growware-pilot.md`
- effect: `deny-without-approval`

## Rule

Growware 的项目本地 intake 要把 `feishu6-chat` 里的自然语言反馈当成项目级执行信号，而不是普通闲聊。

同一条活跃任务上的修辞修正、补充说明和 bug follow-up 应该留在当前 task 上；明显独立的新目标应该排成新任务；默认执行来源应该是 daemon-owned。

运行时必须读取编译后的 `.policy/`，而不是直接依赖 prose 说明或旧的 `.growware/policies` 目录来做最终判断。

## Allowed

- 继续把同一条反馈当成当前 task 的修辞修正或 bug follow-up
- 把明显独立的新目标排成新的 Growware task
- 从文档重新编译 `.policy/` 并刷新运行时输入
- 继续保持 `feishu6-chat` 的 intake 与 approval 语义

## Forbidden

- 直接跳过 `.policy/`，只靠聊天上下文决定 intake
- 把 daemon-owned 以外的执行来源伪装成默认源
- 未经批准就更改 classifier signals、默认执行来源或 channel 角色
- 把旧的 `.growware/policies` 当作运行时最终真相源

## Approval Required

- 更改 `sameSessionClassifier` 的 signal 列表
- 更改 `defaultExecutionSource`
- 更改 `feedbackChannel` 的角色或 provider/accountId
- 取消或放宽 same-session routing 的项目本地默认收敛

## Verification

- `python3 scripts/runtime/growware_policy_sync.py --check --json`
- `python3 scripts/runtime/growware_preflight.py --json`
- `python3 -m unittest tests.test_growware_feedback_classifier tests.test_growware_preflight`

## Machine Notes

- defaultExecutionSource: `daemon-owned`
- sameSessionClassifier.minConfidence: `0.78`
- sameSessionClassifier.steeringSignals:
  - `这个不是很自然语言`
  - `正常人说话`
  - `改自然一点`
  - `改一下`
  - `改成`
  - `不要了`
  - `不对`
  - `太机械`
  - `换个说法`
  - `再顺一点`
  - `更自然`
  - `this is not natural`
  - `make it sound natural`
  - `rewrite this reply`
  - `change the wording`
  - `remove this wording`
- sameSessionClassifier.queueingSignals:
  - `另外`
  - `再做一个`
  - `顺便`
  - `新增`
  - `新需求`
  - `also`
  - `another task`
  - `new task`
  - `separately`
- sameSessionClassifier.bugSignals:
  - `有问题`
  - `报错`
  - `失败`
  - `不工作`
  - `不生效`
  - `bug`
  - `broken`
  - `error`
- sameSessionClassifier.ideaSignals:
  - `我想`
  - `希望`
  - `想法`
  - `建议`
  - `idea`
  - `proposal`
- completionNotification.alwaysNotify: `true`
- completionNotification.includeExecutionSource: `true`
- completionNotification.channelRef: `feedbackChannel`
- 这条规则会编译成 `.policy/rules/growware.feedback-intake.same-session.v1.json`
- 运行时只应消费编译后的机器层结果
- 如果文档与 `.policy/` 不一致，应该视为失败而不是自动脑补
