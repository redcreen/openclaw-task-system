[English](output_channel_separation_decision_log.md) | [中文](output_channel_separation_decision_log.zh-CN.md)

# Output Channel Separation Decision Log

## Purpose

This note records the accepted boundary between:

- runtime-owned control-plane output
- user-visible business content
- planning-internal state

## Problem

Tool-assisted planning creates a structural risk:

- the task system already owns a control-plane channel for scheduling state
- the model may still repeat that same scheduling state inside the normal business reply

That produces semantically mixed output:

- the main answer says the follow-up is already scheduled
- the runtime also sends a `[wd]` confirming the schedule

Scheduling state belongs to supervision, not to business content.

## Rejected Direction

The explicitly rejected direction is:

- first allow the model to place scheduling state in ordinary reply text
- then keep adding regex, phrase-list, keyword-filter, or text-cleanup rules to strip it back out

Reject it because:

- the approach does not converge
- it depends on exact wording
- it mixes the channels first and only then tries to separate them
- maintenance cost keeps rising

## Accepted Direction

The accepted design direction is output channel separation:

1. scheduling state stays in tool results and runtime truth first
2. task-system projects that state into runtime-owned `[wd]`
3. user-visible business content uses a separate content channel
4. ordinary reply text must not carry raw scheduling state

## Minimum Implementation In The Current Phase

The minimum implementation for the current phase is:

1. user-visible business content must live inside `<task_user_content> ... </task_user_content>`
2. once a task uses planning tools, runtime forwards only that content block
3. if the block is missing, runtime suppresses user-visible content instead of guessing
4. scheduling success or failure still goes through `[wd]`
5. due-time follow-up content replies in the original thread without `[wd]`
6. runtime must never leak literal `<task_user_content>` tags to the user
7. once a promise guard is armed, the structured-content gate must survive reload and rehydrate

## Additional Product Constraints

Two additional constraints were confirmed in review:

1. scheduling acknowledgements must include a readable follow-up summary
2. when the main user value is the future reminder or future sync itself, the immediate visible output should default to control-plane unless the model has immediate business content to send now

This preserves the intended user semantics:

- scheduling state travels through `[wd]`
- business content appears at the real due time
- the two must not collapse back into one immediate reply

## Design Rationale

This is stricter than a prompt-only reminder, but the boundary is much clearer:

- one channel for business content
- one channel for control-plane state

That is closer to a real architecture boundary than to ad hoc text cleanup.
