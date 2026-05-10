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

### Plot quality rules (common pitfalls)

- **X-axis = `step` (not `epoch`)** — workers log to wandb with `step=global_step`. Plots that default to `epoch` will be empty or wrong. Always set `x="step"` (or `x="_step"`) on Line/Scalar panels unless the run actually logged epoch as the primary x-axis.
- **Filter runs explicitly** — when a panel shows "no data", the cause is usually that the panel's run filter doesn't match any runs. Set the runset filter to the specific run names (`R001`, `R002`, ...) rather than relying on defaults.
- **Verify metric keys exist** — before referencing `eval/loss` in a panel, confirm runs actually logged that key. Check `wandb.Api().run(<run>).history().columns` if unsure.
- **One y-axis per scale** — don't put loss (0–10) and accuracy (0–1) on the same axis. Split into separate panels or use dual axes.
- **Missing runs in plots** — if a recently-completed run isn't appearing, it may not have synced yet. For offline mode, ensure `wandb sync` ran before generating the Report.

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
Task(
  subagent_type="general-purpose",
  model="sonnet",
  run_in_background=True,
  prompt="
    Read templates/WANDB_REPORTS.md for instructions.
    VERSION={VERSION}, WANDB_PROJECT={PROJECT}, PROJECT_NAME={NAME}, LATEST_RUN={RUN}.
    Generate the wandb Report now.
  ",
)
```

`run_in_background=True` is **required** — without it the Task call blocks the supervisor until the report finishes, defeating the point of a side-channel snapshot. The supervisor continues the loop immediately after spawning; it'll be notified when the sub-agent completes (do not poll). Pick up the report URL from the completion notification and append it to `SYNTHESIS.md → ## wandb Reports`.

**Codex:** Spawn the sub-agent with the same prompt, also detached so the loop continues.

**Other agents:** Execute inline if sub-agents aren't available, or skip.
