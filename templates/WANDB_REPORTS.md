# wandb Report Generation

> Spec for the wandb Report sub-agent. The supervisor spawns this agent
> on significant events. It reads the current research state and produces
> a cumulative, versioned wandb Report snapshot.

---

## When the supervisor triggers this

The supervisor spawns this sub-agent when ANY of these occur:
1. **Paradigm shift** — a core belief was rejected or confidence dropped >= 0.3
2. **Belief resolved** — a belief reached `supported` or `rejected`
3. **Every 5 runs** — periodic snapshot for observability

The supervisor passes: `VERSION` (v1, v2, ...), `WANDB_PROJECT`, `PROJECT_NAME`, `LATEST_RUN`.

Skip if wandb mode is `disabled`.

---

## What to read

- `SYNTHESIS.md` — current narrative
- All `REPORTS/R###.md` since the last Report version (or all, if first snapshot)
- `STATE.md` BeliefState table (current beliefs and confidence)
- `STATE.md` Ledger (full run history)
- `RUNS/R###/metrics/` — training_history.json, eval_results.json from recent runs
- wandb run data from the project (if accessible via API)

---

## What to produce

Generate a wandb Report programmatically using the Reports API:

```python
import wandb
import wandb.apis.reports as wr

report = wr.Report(
    project=WANDB_PROJECT,
    title=f"Research Report {VERSION} — {PROJECT_NAME}",
    description=f"Cumulative research snapshot as of {LATEST_RUN}"
)
```

### Report contents

1. **Narrative** — from SYNTHESIS.md, as markdown blocks
2. **Belief trajectory** — table or line plot showing confidence over runs for each belief
3. **Cross-run metric comparisons** — pull metrics from wandb runs, create comparison panels
4. **Key visualizations** — embed plots from `RUNS/R###/artifacts/` and wandb run panels
5. **Run summary table** — from Ledger, with links to individual wandb runs
6. **Interactive data** — wandb panel grids for metrics that benefit from interactive exploration

### Versioning

Each Report is a versioned snapshot — preserves how understanding evolved:
- v1: initial snapshot
- v2: after first paradigm shift
- v3: after next trigger event
- ...

After saving: `report.save()`

Record the URL in `SYNTHESIS.md` under a `## wandb Reports` section.

---

## How the supervisor spawns this

**Claude Code:**
```
Task(subagent_type="general-purpose", model="sonnet", prompt="
  Read templates/WANDB_REPORTS.md for instructions.
  VERSION={VERSION}, WANDB_PROJECT={PROJECT}, PROJECT_NAME={NAME}, LATEST_RUN={RUN}.
  Generate the wandb Report now.
")
```
Runs in background — loop continues regardless.

**Codex:** Spawn sub-agent with the same prompt.

**Other agents:** Execute inline if sub-agents aren't available, or skip.
