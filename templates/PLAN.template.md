# PLAN — {{RUN_ID}}

## Delta
- **what changed**: {{WHAT_CHANGED}}
- **intent**: {{INTENT}}
- **disambiguates**: {{WHAT_THIS_TESTS}}
- **type**: {{DELTA_TYPE}}

## Protocol lock
<!-- These MUST NOT change during execution. If violated, worker must BLOCKER. -->
- **baseline**: {{BASELINE_REF}}
- **controlled vars**: {{CONTROLLED_VARS}}
- **eval method**: {{EVAL_METHOD}}

## Commands
<!-- Exact steps. Worker executes in order. One command per line. -->
```
{{COMMAND_1}}
{{COMMAND_2}}
{{COMMAND_3}}
```

## Success metrics
<!-- What to measure. Worker reports these in the results table. -->
| Metric | Baseline | Target | How to measure |
|--------|----------|--------|----------------|
| {{METRIC_1}} | {{BASELINE_1}} | {{TARGET_1}} | {{HOW_1}} |

## Stop conditions
<!-- Worker must halt and report BLOCKER if any of these trigger. -->
- BLOCKER if: {{BLOCKER_CONDITION_1}}
- BLOCKER if: {{BLOCKER_CONDITION_2}}
- TIMEOUT after: {{TIME_BUDGET}}

## Context
<!-- Relevant beliefs and prior runs. Supervisor fills this from STATE.md. -->
{{CONTEXT}}

## Meta
- **run_id**: {{RUN_ID}}
- **created**: {{DATE}}
- **time_budget**: {{TIME_BUDGET}}
- **status**: planned
