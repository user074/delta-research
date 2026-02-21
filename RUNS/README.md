# RUNS

One directory per run. Each contains a plan and its artifacts.

## Layout
```
R###/
  PLAN.md       # Supervisor writes, Worker reads (immutable during execution)
  artifacts/    # Worker saves data, logs, outputs here
```

## Contract
- Created by: `scripts/new_run.sh` or **Supervisor**
- PLAN.md follows `templates/PLAN.template.md`
- Worker MUST NOT modify PLAN.md
- Worker MUST NOT modify files outside its run directory (except its REPORT)
- Final report goes to `REPORTS/R###.md`, not here
