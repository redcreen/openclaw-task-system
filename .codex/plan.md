# Project Plan

## Current Phase

Post-retrofit stabilization and next-slice selection.

## Slices
- Slice: retrofit closure
  - Objective: keep the new control surface and docs stack aligned with the real repo state
  - Dependencies: `.codex/*`, `README`, `docs/*`, and the governance validators
  - Risks: future sync runs drift away from the actual runtime and operator workflow
  - Validation: `validate_gate_set.py --profile deep` returns `ok: True`
  - Exit Condition: structure, docs, and governance stay converged

- Slice: runtime stability
  - Objective: preserve the current Phase 6 baseline for `[wd]`, continuity, planning acceptance, and same-session routing
  - Dependencies: runtime scripts, plugin payload, testsuite
  - Risks: regressions in control-plane projection, future-first semantics, or install drift
  - Validation: `./scripts/run_tests.sh` stays green and acceptance tooling remains usable
  - Exit Condition: runtime and installable payload remain stable after subsequent changes

- Slice: next maintenance priority
  - Objective: choose the next concrete improvement beyond retrofit
  - Dependencies: roadmap boundaries and current operator pain points
  - Risks: repo falls back into ad hoc maintenance with no visible next slice
  - Validation: `status.md` names the next 3 actions and the next focus area
  - Exit Condition: next slice is explicit and scoped
