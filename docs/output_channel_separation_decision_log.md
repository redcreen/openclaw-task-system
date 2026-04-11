# output channel separation decision log

[English](output_channel_separation_decision_log.md) | [中文](output_channel_separation_decision_log.zh-CN.md)

### status

- recorded: 2026-04-06
- scope: separating scheduling state from user-visible business content

### problem

Tool-assisted planning introduced a structural ambiguity:

- task-system already had a runtime-owned control-plane path for:
  - `[wd] 已收到...`
  - `[wd] 已安排妥当...`
- but the model could still mention scheduling state in the normal assistant reply

That produced duplicated or mixed user-facing messages such as:

- a normal answer that says `我已经排上了`
- plus a task-system `[wd]` that says the same thing

This was not acceptable because scheduling state is supervision state, not business content.

### rejected direction

The rejected direction is:

- let the model say scheduling state in natural language
- then keep adding regex, phrase lists, or keyword cleanup rules to strip it out

This was rejected because:

- it does not scale
- it is wording-dependent
- it silently mixes two channels first and only then tries to separate them
- it creates an unbounded maintenance burden

### accepted direction

The accepted design is output-channel separation:

1. scheduling state stays in tool results and task truth source
2. task-system projects scheduling state as runtime-owned `[wd]`
3. user-visible business content must travel in a dedicated content channel
4. the normal assistant reply must not carry raw scheduling state

### minimum implementation

The minimum implementation chosen for this phase is:

1. require user-visible business content to be emitted inside:
   - `<task_user_content> ... </task_user_content>`
2. once planning tools are used for a task, runtime only forwards content from that block
3. if no such block exists, runtime suppresses user-facing content instead of guessing
4. scheduling confirmation remains a separate `[wd]` control-plane message
5. delayed follow-up content still replies to the original message and does not carry `[wd]`
6. runtime must never leak the literal `<task_user_content>` markers to the user
7. once a promise guard is armed, the structured-content gate must survive reload and truth-source rehydration

### additional product constraints confirmed in live review

Live review added two more constraints that should now be treated as part of the same design:

1. a scheduling confirmation must include a human-meaningful follow-up summary
   - bad: `[wd] 已安排妥当，将在 2分钟后 回复。`
   - good: `[wd] 已安排妥当：2分钟后同步明天天气。`
2. if a request is primarily about future reminders or future follow-up delivery, the immediate user-visible message should usually be control-plane only
   - do not send the eventual business result immediately unless the model explicitly indicates that an immediate result is required
   - in those future-first cases, the default immediate user-visible output should be `[wd]` scheduling state, and the business result should wait until the due follow-up fires

This keeps the user-facing semantics stable:

- scheduling state is `[wd]`
- future follow-up content is the later business reply
- the immediate main answer should not collapse those two into one mixed message

### rationale

This is stricter than prompt-only guidance, but it keeps the boundary explicit:

- business content channel
- control-plane channel

That boundary is the real solution.

It is better than free-form output cleanup.
