[English](planning_acceptance_record_template.md) | [中文](planning_acceptance_record_template.zh-CN.md)

# Planning Acceptance Record Template

Use this file as the starting point for a new real or semi-real planning acceptance record.

Reference material:

- [planning_acceptance_runbook.md](planning_acceptance_runbook.md)
- [archive/planning_acceptance_record_2026-04-12.md](archive/planning_acceptance_record_2026-04-12.md)

## Copy Template

````md
[English](planning_acceptance_record_YYYY-MM-DD.md) | [中文](planning_acceptance_record_YYYY-MM-DD.zh-CN.md)

# Planning Acceptance Record YYYY-MM-DD

## 1. Basic Info

- Date:
- Operator:
- Acceptance type: `real` / `semi-real`
- Environment:
  - source repo / installed plugin:
  - channel:
  - account / workspace:
  - branch / revision:
- Background:

## 2. Acceptance Goal

- What changed in this slice:
- What this run is expected to prove:
- Which runtime / planning / release-facing boundaries are in scope:

## 3. Sample Input

User input:

```text
<paste the representative request here>
```

## 4. Automation Pre-Checks

Commands run:

```bash
bash scripts/run_tests.sh
python3 scripts/runtime/run_planning_acceptance_bundle.py --json --date YYYY-MM-DD
```

Results:

- broader regression:
- bundle summary:
- planning acceptance steps:
- stable acceptance steps:
- install / doctor / smoke checks:

## 5. User-Visible Observations

### 5.1 First `[wd]`

- Was it visible immediately?
- Did it stay runtime-owned?
- Evidence:

### 5.2 30-second progress follow-up

- Was a real user-visible progress message observed?
- Did it carry a truthful progress summary?
- Conclusion:

### 5.3 Due-time continuation or follow-up delivery

- Was the follow-up materialized or claimed correctly?
- Did it preserve the expected reply target?
- Evidence:

### 5.4 Final closure

- Was `plan_status` fulfilled?
- Was `promise_guard_status` fulfilled?
- Did any happy-path planning anomaly remain?

## 6. Ops-Side Observations

- What did planning / continuity / dashboard views show?
- Were anomaly or overdue projections correct?
- Did the repo's default data directory stay clean after the run?
- Key evidence:

## 7. Pass / Fail Judgment

- Overall result: `pass` / `fail` / `pass-with-notes`
- Severity:
- Summary:
- Uncovered or deferred items:

## 8. Attachments And Evidence

- artifacts:
- relevant JSON outputs:
- task IDs / plan IDs:
- session keys:

## 9. Follow-Up Actions

- next dated evidence needed:
- docs or runbook updates needed:
- validation to repeat after the next planning change:
````
