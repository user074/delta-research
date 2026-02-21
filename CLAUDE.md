# Research Loop Guidelines

> These guidelines apply to any coding agent operating in this repo.
> The research loop is agent-agnostic: Claude, Cursor, Copilot, or manual.

## Core loop

```
Supervisor (long-lived)         Worker (short-lived, per run)
  Read STATE.md                   Read PLAN.md
  Select delta from Frontier      Execute commands
  Write PLAN.md                   Save artifacts
  Spawn Worker ─────────────────► Write REPORT.md
  Wait for report ◄──────────────┘
  Compress: update STATE.md
  Recompile DASHBOARD.md
  Check interrupt boundaries
  Repeat
```

## Design principles

1. **Delta-first**: the unit of progress is *what changed → what happened → what it means*
2. **Compression over narration**: compress messy runs into BeliefState + Frontier
3. **Autonomy with crisp interrupts**: default is *keep going*, stop only on boundaries
4. **Single source of truth**: STATE.md is memory and control surface
5. **Clean credit assignment**: one major delta per run

## The contract

### STATE.md (Supervisor owns, Worker reads)
- BeliefState: supported / rejected / conflicting, with evidence-weighted confidence
- Ledger: append-only history (run → delta → metric → signal → verdict)
- Frontier: ranked next deltas, each says what it disambiguates + cost/risk
- Policy: interrupt rules, scoring thresholds, template stats

### PLAN.md (Supervisor writes → Worker reads, immutable)
- Delta definition: what changed / intent / what it disambiguates
- Protocol lock: baseline, controlled vars, eval method (MUST NOT change)
- Commands: exact steps to execute
- Stop conditions: when to BLOCKER

### REPORT.md (Worker writes → Supervisor reads)
- Result table: metric / baseline / observed / delta
- Signal score: 0.0 (no info) to 1.0 (maximally informative)
- Verdict: supports | contradicts | unclear | BLOCKER
- Confounds: what else could explain it
- Next tests: top 3 suggested deltas

## File paths

| Path | Owner | Purpose |
|------|-------|---------|
| `STATE.md` | Supervisor | Beliefs, ledger, frontier, policy |
| `DASHBOARD.md` | Compiler | Human-readable summary |
| `RUNS/R###/PLAN.md` | Supervisor | Execution plan for one run |
| `RUNS/R###/artifacts/` | Worker | Data, logs, outputs |
| `REPORTS/R###.md` | Worker | Structured evidence |
| `ARTIFACTS/plots/` | Compiler | Generated visualizations |

## Worker rules (strict)

- NEVER modify STATE.md
- NEVER modify PLAN.md
- NEVER choose new research directions (suggest only via "Next tests")
- NEVER change protocol lock fields during execution
- Report BLOCKER verdict if stop conditions trigger
- Null results are valuable — report honestly

## Supervisor rules

- Always consult BeliefState and Frontier before selecting a delta
- Compress, don't narrate: update state tables, not prose
- Demote beliefs that lose evidence, promote those that gain it
- Track template stats: which delta types produce signal?
- Respect interrupt boundaries: budget, null streak, BLOCKER, ambiguity
