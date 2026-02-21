# REPORT — {{RUN_ID}}

## Result
| Metric | Baseline | Observed | Δ | Notes |
|--------|----------|----------|---|-------|
| {{METRIC}} | {{BASELINE}} | {{OBSERVED}} | {{DELTA_VALUE}} | {{NOTES}} |

## Signal
- **score**: {{SIGNAL_SCORE}}
- {{SIGNAL_BULLET_1}}
- {{SIGNAL_BULLET_2}}

## Verdict
<!-- One of: supports | contradicts | unclear | BLOCKER -->
**{{VERDICT}}** — {{VERDICT_TARGET_BELIEF}}

## Confounds
<!-- What could explain the result other than the delta? -->
- {{CONFOUND_1}}

## Next tests
<!-- Top 3 deltas this run suggests. Supervisor may add to frontier. -->
1. {{NEXT_1}}
2. {{NEXT_2}}
3. {{NEXT_3}}

## Artifacts
- `artifacts/{{ARTIFACT}}` — {{DESCRIPTION}}

## Errors
{{ERRORS}}

## Log (abbreviated)
```
{{LOG}}
```

## Meta
- **run_id**: {{RUN_ID}}
- **delta**: {{DELTA}}
- **started**: {{START_TIME}}
- **completed**: {{END_TIME}}
- **status**: {{STATUS}}
