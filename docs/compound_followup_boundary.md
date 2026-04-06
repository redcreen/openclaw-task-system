# Compound follow-up boundary

> Status: open design boundary
> Scope: delayed reply and continuation semantics for mixed-intent user requests

## problem

The current task system handles two classes of requests well:

1. a normal task that should execute now
2. a pure delayed reply such as `3分钟后回复333`

It becomes ambiguous when one user message mixes both:

- `你先查一下天气，然后5分钟后回复我信息`
- `先处理这个问题，10分钟后再提醒我看结果`
- `先去查一下，再过一会儿回来继续`

These are not just "delay phrases". They are compound task requests with at least two intent segments:

- an immediate task
- a delayed follow-up task

## why regex-only handling is the wrong long-term answer

It is tempting to keep adding more parsing rules for:

- `然后`
- `之后`
- `再`
- `并且`
- `回复我信息`

But that approach does not scale.

Reasons:

1. natural language is open-ended
2. the delayed part may be vague or implicit
3. the delayed part may depend on whether the immediate part succeeded
4. the message may contain more than two intent segments
5. a rule can easily look correct on one phrase and fail on another

So this class of problem should not be treated as a regex-completion problem.

## what the current shipped system does

Today the shipped system supports:

- direct delayed reply recognition for clear, single-intent phrases
- a stopgap for some simple compound requests:
  - immediate work remains a normal task
  - a post-run delayed follow-up can be materialized when the intent is obvious

This stopgap exists to avoid user-visible breakage, but it is not the final model.

## correct architectural direction

The right long-term direction is:

1. parse the inbound request into a structured task plan
2. separate immediate work from delayed follow-up work
3. let the runtime create the needed task graph explicitly
4. make the delayed part observable as a first-class follow-up task

Conceptually:

```text
user request
  -> intent decomposition
  -> task plan
      - immediate task
      - delayed follow-up task
      - dependency and ordering
  -> task-system runtime
```

This is a planning problem, not a pure pattern-matching problem.

## product boundary for now

Current boundary:

- clear single-intent delayed replies are fully supported
- simple compound follow-up patterns may be recognized as a compatibility bridge
- complex or ambiguous compound requests should not rely on hardcoded phrase growth forever

Therefore:

- shipping behavior may include pragmatic stopgaps
- roadmap direction must move toward structured planning or tool-assisted task decomposition

## why this matters

Without this boundary, the system drifts into:

- more hardcoded phrase rules
- more brittle delayed-follow-up behavior
- more hidden mismatches between what the agent promises and what the runtime actually scheduled

That would weaken the task system's core contract:

> if the system promises a delayed action, there must be a real scheduled task behind it.

## next design question

One strong candidate direction is:

- expose task-system task creation and follow-up scheduling as explicit LLM-callable tools

That would let the model choose between:

- normal immediate execution
- explicit delayed follow-up creation
- multi-step task decomposition

This question is intentionally left open for the next roadmap discussion.
