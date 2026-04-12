# Close Runtime Source Of Truth Convergence

- Date: 2026-04-12
- Status: resolved

## Problem

After lifecycle ownership moved into `lifecycle_coordinator.py`, the remaining architecture debt was still real: maintainers could still reason about `scripts/runtime/` and `plugin/scripts/runtime/` as two peer-owned trees.

That kept the architecture signal yellow even though the lifecycle checkpoint itself had already closed.

## Thinking

The repo already had most of the needed enforcement pieces:

- `runtime_mirror.py`
- `plugin_doctor.py`
- `scripts/run_tests.sh`
- install-time validation

The real gap was not missing infrastructure. It was that the canonical-source rule was not yet explicit enough in control docs, maintainer docs, and install/doctor entrypoints.

## Solution

Close the source-of-truth convergence slice by making one decision explicit everywhere:

- `scripts/runtime/` is the only canonical editable runtime tree
- `plugin/scripts/runtime/` is a strict synchronized mirror for the installable plugin payload

Then encode that decision into:

- `.codex/status.md`, `.codex/plan.md`, and `.codex/architecture-retrofit.md`
- `README.md`, `docs/architecture.md`, `docs/roadmap.md`, and the architecture-hardening workstream docs
- `plugin/readme.md`
- `plugin_doctor.py`
- `scripts/install_remote.sh`

## Validation

- `python3 /Users/redcreen/.codex/skills/project-assistant/scripts/validate_gate_set.py /Users/redcreen/Project/openclaw-task-system --profile deep`
- `bash /Users/redcreen/Project/openclaw-task-system/scripts/run_tests.sh`

Both passed after the closeout.

## Follow-Ups

- Treat any future plugin-side lifecycle repair logic as an architecture regression, not a local patch.
- Keep mirror enforcement aligned if packaging or release paths change.

## Related Files

- .codex/status.md
- .codex/plan.md
- .codex/architecture-retrofit.md
- scripts/runtime/runtime_mirror.py
- scripts/runtime/plugin_doctor.py
- scripts/install_remote.sh
