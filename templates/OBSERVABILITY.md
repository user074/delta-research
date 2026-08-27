# DELTA Observability

> Two logging layers: **DELTA markers** (sparse, for automation) and **full logs** (dense, for analysis).
> Workers emit DELTA markers to stdout for the monitoring script.
> Workers write full logs to `RUNS/R###/logs/` for human analysis and debugging.

---

## Run Directory Structure

Every run must organize outputs into these directories:

```
RUNS/R###/
├── PLAN.md                        # Short editable working guide
├── experiment.py                  # Generated script (SLURM mode only)
├── job.sh                         # SLURM job script (SLURM mode only)
├── slurm-<JOB_ID>.out             # Raw SLURM stdout (SLURM mode only)
├── logs/                          # Dense text logs — name files by what they capture
│   ├── *.log                      # e.g. train.log, eval.log, benchmark.log, analysis.log
│   └── stderr.log                 # Errors, warnings, stack traces
├── metrics/                       # Structured JSON — machine-readable
│   └── *.json                     # e.g. results.json, training_history.json, benchmark_scores.json
├── checkpoints/                   # Large model weights — gitignored, may be redirected to scratch
│   └── (model weights, optimizer states, ...)
├── artifacts/                     # Small outputs referenced by the report
│   ├── *.png                      # Generated plots and visualizations
│   └── (small outputs)            # Generated samples, processed data summaries
└── scripts/                       # Helper scripts generated during the run
    └── *.py / *.sh
```

**Rules:**
- **PLAN.md** — One editable working guide. The worker changes it directly as execution develops; no immutable
  copy, versioning, amendment classes, or approval workflow. Mechanical changes need no note. If results were
  already visible before a material scientific change, append one transparent Working note and treat affected
  results as exploratory.
- **logs/** — Dense, append-only text files. One line per step or event. For humans to analyze what happened in detail. Name files by purpose (e.g. `train.log` for training, `benchmark.log` for benchmarks, `analysis.log` for data analysis).
- **metrics/** — Structured JSON. Machine-readable, used by the report generator and wandb sync. Name files by phase (e.g. `results.json`, `training_history.json`, `scores.json`).
- **checkpoints/** — Large model weights and optimizer states. Separate from `artifacts/` so the whole tree can be gitignored (`RUNS/*/checkpoints/`). On clusters, this directory may be a symlink to a scratch path from INFRA.md (e.g. `/scratch/$USER/{RUN_ID}/`) — the report still references `checkpoints/<file>` regardless.
- **artifacts/** — Small outputs that the report references: plots, generated samples, processed data summaries. NOT model weights — those go in `checkpoints/`. No scripts, no logs.
- **scripts/** — Any Python or shell scripts generated during the run. Keeps artifacts/ clean.
- Workers must create `logs/` and `metrics/` directories. `checkpoints/`, `artifacts/`, and `scripts/` are created as needed.

**Gitignore pattern:**
```
RUNS/*/checkpoints/
RUNS/*/slurm-*.out
RUNS/*/wandb/
```

---

## Full Logging (for analysis)

Full logs capture everything — every step, every metric, every warning. They exist for humans and for the report generator to extract detailed data.

### Log format

One line per step/event, tab-separated for easy parsing. Name the log file after what it captures.

**Training example** (`logs/train.log`):
```
step=0	epoch=0	loss=2.4531	lr=2.00e-04	grad_norm=1.23	tokens_per_sec=1842	timestamp=2026-04-12T14:30:00Z
step=1	epoch=0	loss=2.3912	lr=2.00e-04	grad_norm=1.18	tokens_per_sec=1856	timestamp=2026-04-12T14:30:02Z
```

**Benchmark example** (`logs/benchmark.log`):
```
model=llama-3-8b	batch=32	throughput=1842	latency_ms=17.4	gpu_util=0.94	timestamp=2026-04-12T14:30:00Z
model=llama-3-8b	batch=64	throughput=2103	latency_ms=30.4	gpu_util=0.97	timestamp=2026-04-12T14:30:15Z
```

Every log line must include `timestamp`. Other fields depend on the experiment type.

### Metrics JSON format

Structured JSON in `metrics/`. Name files by phase. One file per distinct output.

**Step-level metrics** (e.g. `metrics/training_history.json`):
```json
[
  {"step": 0, "epoch": 0, "loss": 2.4531, "lr": 2e-4},
  {"step": 1, "epoch": 0, "loss": 2.3912, "lr": 2e-4}
]
```

**Final results** (e.g. `metrics/results.json`):
```json
{
  "eval_loss": 1.782,
  "perplexity": 5.94,
  "rouge_l": 0.423,
  "num_samples": 5000,
  "duration_sec": 142.3
}
```

### Python logging helper

```python
import json
import os
from datetime import datetime, timezone

class ExperimentLogger:
    """Full experiment logger — writes dense logs and structured metrics.

    This is a reference implementation. Workers can adapt it to their needs.
    For very long jobs (100K+ steps), consider writing metrics JSON
    incrementally instead of accumulating in memory.
    """

    def __init__(self, run_dir, log_name="experiment.log"):
        self.log_dir = os.path.join(run_dir, "logs")
        self.metrics_dir = os.path.join(run_dir, "metrics")
        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(self.metrics_dir, exist_ok=True)

        self.log_file = open(os.path.join(self.log_dir, log_name), "w")
        self.history_path = os.path.join(self.metrics_dir, "history.json")
        self.history = []
        self._flush_interval = 1000  # Write JSON every N steps

    def log_step(self, **kwargs):
        """Log a single step to the text log and accumulate for JSON."""
        kwargs.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        line = "\t".join(f"{k}={v}" for k, v in kwargs.items())
        self.log_file.write(line + "\n")
        self.log_file.flush()
        self.history.append(kwargs)
        # Periodic JSON flush to avoid unbounded memory growth
        if len(self.history) % self._flush_interval == 0:
            self.save_history()

    def log_results(self, results: dict, name="results.json"):
        """Write a results JSON file."""
        path = os.path.join(self.metrics_dir, name)
        with open(path, "w") as f:
            json.dump(results, f, indent=2)

    def save_history(self):
        """Write accumulated step history to JSON."""
        with open(self.history_path, "w") as f:
            json.dump(self.history, f, indent=2)

    def close(self):
        self.save_history()
        self.train_log.close()
```

---

## DELTA Markers (for automation)

DELTA markers are the sparse signaling channel. The monitoring script (`scripts/wait_for_job.sh`) filters for `[DELTA-*]` lines only. Everything else in stdout is ignored by automation.

**DELTA markers are NOT logs.** They are signals. A training run that logs 50,000 steps to `train.log` emits maybe 10 DELTA markers total.

### Markers

| Marker | Purpose | When to emit |
|--------|---------|-------------|
| `[DELTA-START]` | Experiment began | Once, at the start of `experiment.py` |
| `[DELTA-PROGRESS]` | Progress update | At meaningful milestones (10%, 25%, 50%, 75%, 90%) |
| `[DELTA-METRIC]` | Key metric report | After evaluation steps, at log intervals |
| `[DELTA-SMOKE-DONE]` | Smoke job passed | Once after smoke validation; permits the main job but does not complete R### |
| `[DELTA-DONE]` | Process/job completed | Once, at the very end after all cleanup |
| `[DELTA-ERROR]` | Recoverable error | On exceptions that don't halt the experiment |
| `[DELTA-BLOCKER]` | Unrecoverable failure | On fatal errors — experiment cannot continue |

### Format

```
[DELTA-START] R### | <ISO timestamp>
[DELTA-PROGRESS] <pct>% | <message>
[DELTA-METRIC] <key>=<value> | <key>=<value>
[DELTA-SMOKE-DONE] R### | elapsed=<duration> | status=smoke_passed
[DELTA-DONE] R### | elapsed=<duration> | status=completed
[DELTA-ERROR] <message>
[DELTA-BLOCKER] R### | <message>
```

### Terminal markers

The monitoring script exits when it sees one of these:
- `[DELTA-SMOKE-DONE]` → exit 0 (smoke success; continue to the main experiment, no report/state update)
- `[DELTA-DONE]` → exit 0 (the monitored process succeeded)
- `[DELTA-BLOCKER]` → exit 1 (fatal failure)

`[DELTA-ERROR]` is **recoverable** — printed to the agent but does not terminate monitoring. Use it for non-fatal exceptions (e.g., one eval batch failed but training continues). Use `[DELTA-BLOCKER]` for truly fatal errors.

`[DELTA-DONE]` does not by itself complete R###. After it appears, the worker checks PLAN.md. If another baseline,
condition, repetition, control, ablation, or analysis is required for the conclusion, continue under the same run
ID. Only the complete evidence package permits `REPORTS/R###.md` and state compression.

All other markers (`START`, `PROGRESS`, `METRIC`, `ERROR`) are informational.

---

## Why flush matters

Stdout is buffered whenever it's redirected to a file or pipe — SLURM `--output`, `tee`, shell `>`, `nohup`, backgrounded processes. Without explicit flushing, DELTA markers may not appear until the process ends — defeating live monitoring in both `slurm` and `direct` modes. Every `print()` call that emits a DELTA marker must use `flush=True`.

Python's `-u` flag (unbuffered) is an alternative but less reliable across all environments. Explicit `flush=True` is the recommended approach.

---

## Python helper

Workers should include this snippet in `experiment.py`:

```python
import sys
from datetime import datetime, timezone

RUN_ID = "R001"  # Set from plan

def delta_start():
    ts = datetime.now(timezone.utc).isoformat()
    print(f"[DELTA-START] {RUN_ID} | {ts}", flush=True)

def delta_progress(pct, message=""):
    print(f"[DELTA-PROGRESS] {pct}% | {message}", flush=True)

def delta_metric(**kwargs):
    pairs = " | ".join(f"{k}={v}" for k, v in kwargs.items())
    print(f"[DELTA-METRIC] {pairs}", flush=True)

def delta_done(elapsed):
    print(f"[DELTA-DONE] {RUN_ID} | elapsed={elapsed} | status=completed", flush=True)

def delta_smoke_done(elapsed):
    print(f"[DELTA-SMOKE-DONE] {RUN_ID} | elapsed={elapsed} | status=smoke_passed", flush=True)

def delta_error(message):
    print(f"[DELTA-ERROR] {message}", flush=True)

def delta_blocker(message):
    print(f"[DELTA-BLOCKER] {RUN_ID} | {message}", flush=True)
    sys.exit(1)
```

### Usage — both layers together

```python
import time

PROJECT_ROOT = "/home/researcher/llm-finetune"  # From INFRA.md project root
RUN_DIR = os.path.join(PROJECT_ROOT, "RUNS/R007")
logger = ExperimentLogger(RUN_DIR)  # Full logs
delta_start()                        # Automation signal

try:
    # --- Setup ---
    delta_progress(0, "loading model and data")
    model = load_model(...)
    dataset = load_dataset(...)

    # --- Training loop ---
    total_steps = len(dataloader) * num_epochs
    last_reported_pct = -1
    for epoch in range(num_epochs):
        for step, batch in enumerate(dataloader):
            loss = train_step(model, batch)
            lr = scheduler.get_last_lr()[0]

            global_step = epoch * len(dataloader) + step
            pct = int(100 * global_step / total_steps)

            # Full log — EVERY step (dense, for analysis)
            logger.log_step(
                step=global_step, epoch=epoch,
                loss=f"{loss:.4f}", lr=f"{lr:.2e}",
            )

            # DELTA progress — milestones only (sparse, for automation)
            if pct in (10, 25, 50, 75, 90) and pct > last_reported_pct:
                delta_progress(pct, f"epoch {epoch} step {step} loss={loss:.4f}")
                last_reported_pct = pct

            # DELTA metric — at log interval (sparse, for automation)
            if global_step % log_interval == 0:
                delta_metric(loss=f"{loss:.4f}", step=global_step, lr=f"{lr:.2e}")

    # --- Evaluation ---
    delta_progress(95, "running evaluation")
    eval_metrics = evaluate(model, eval_dataset)
    logger.log_eval(eval_metrics)     # Full results to JSON
    delta_metric(**{k: f"{v:.4f}" for k, v in eval_metrics.items()})

    # --- Save ---
    save_checkpoint(model)
    logger.close()
    elapsed = time.time() - start_time
    delta_done(f"{elapsed:.1f}s")

except Exception as e:
    logger.close()
    delta_blocker(str(e))
```

**Summary of the two layers:**

| Aspect | Full logs (`logs/` + `metrics/`) | DELTA markers (stdout) |
|--------|----------------------------------|----------------------|
| Audience | Humans, report generator | Monitoring script, agent |
| Density | Every step | 5-10 signals per run |
| Format | Tab-separated text + JSON | `[DELTA-*]` prefixed lines |
| Purpose | Analyze training dynamics | Know when to continue the loop |
| Storage | `RUNS/R###/logs/`, `RUNS/R###/metrics/` | SLURM stdout or terminal |

---

## wandb integration

When wandb is enabled, workers log to all three channels: full logs (local), wandb (remote dashboard), and DELTA markers (automation).

```python
import wandb

wandb.init(project=WANDB_PROJECT, name=RUN_ID, config=config)

# In training loop — all three channels:
logger.log_step(step=global_step, loss=loss_val, lr=lr)   # Full local log
wandb.log({"loss": loss_val, "lr": lr}, step=global_step)  # wandb dashboard
if global_step % log_interval == 0:
    delta_metric(loss=f"{loss_val:.4f}", step=global_step)  # Sparse automation

# At the end:
logger.close()
wandb.finish()
delta_done(f"{elapsed:.1f}s")
```

The three channels serve different audiences:

| Channel | Audience | Density | Where |
|---------|----------|---------|-------|
| Full logs | Humans, report generator | Every step | `RUNS/R###/logs/` + `metrics/` |
| wandb | Humans, wandb Report sub-agent | Every step | wandb dashboard |
| DELTA markers | Monitoring script, agent | 5-10 per run | stdout |

All three should be emitted when wandb is enabled. Full logs + DELTA markers are always required regardless of wandb mode.

---

## Execution Workflow

INFRA.md → Job Execution → `mode` selects the workflow: `direct` (agent runs `experiment.py` itself) or `slurm` (agent submits to a scheduler). Both modes share the DELTA markers, `ExperimentLogger`, run directory structure, and wandb integration above — only the launch and monitoring plumbing differ.

---

### Direct Mode

The agent runs `experiment.py` directly on the local machine — no scheduler, no `job.sh`, no `slurm-*.out`. The agent process owns the run lifecycle.

#### Step 0 — Optional risk probe

Skip this step unless the working plan names one concrete costly-run failure risk that a short probe can resolve.
A smoke test is not a general readiness gate and must use at most 10% of the run budget.

The smoke test is a setup step inside the same R### as the main experiment. A passing smoke test does not produce
`REPORTS/R###.md`, enter the Ledger, update beliefs, or complete the run; continue immediately to the main command.

**Procedure:**
1. Generate `experiment_smoke.py` — same code as `experiment.py`, parameterized for the smoke config (small dataset slice, few steps, small batch, 1 GPU)
2. Run and capture: `python {PROJECT_ROOT}/RUNS/{RUN_ID}/experiment_smoke.py 2>&1 | tee {PROJECT_ROOT}/RUNS/{RUN_ID}/logs/smoke.out`
3. Extract throughput, peak VRAM (e.g. `nvidia-smi --query-gpu=memory.used --format=csv` during the run), time per step
4. Compare against the plan's single `continue when` condition; adapt the working plan/code directly if needed
5. On success, immediately run the measurement. If the probe cannot resolve its named risk within its cap, stop
   only if that risk is an actual blocker.

#### Step 1 — Generate `experiment.py`

Identical content to SLURM mode (see Step 1 below): DELTA helpers, `ExperimentLogger`, wandb logging when enabled, try/except wrapping with `delta_blocker()`, `delta_progress()` at milestones, `delta_metric()` at log intervals, `flush=True` on every print. No `job.sh` is generated.

**Wandb env vars** — set them at the top of `experiment.py` before `wandb.init()`, so the run is reproducible without depending on shell state:

```python
import os
RUN_ID = "R001"
PROJECT_ROOT = "/home/researcher/llm-finetune"  # from INFRA.md
RUN_DIR = os.path.join(PROJECT_ROOT, "RUNS", RUN_ID)

os.environ.setdefault("WANDB_PROJECT", "delta-research")  # from INFRA.md → wandb
os.environ.setdefault("WANDB_MODE", "online")             # direct usually has internet
os.environ.setdefault("WANDB_RUN_NAME", RUN_ID)
os.environ["WANDB_DIR"] = os.path.join(RUN_DIR, "wandb")
```

Direct mode typically uses `WANDB_MODE=online` (local dev box has internet). Use `offline` only when explicitly required by INFRA.md.

#### Step 2 — Run and monitor

Foreground (default — agent sees DELTA markers live):

```bash
mkdir -p {PROJECT_ROOT}/RUNS/{RUN_ID}/logs
python {PROJECT_ROOT}/RUNS/{RUN_ID}/experiment.py 2>&1 | tee {PROJECT_ROOT}/RUNS/{RUN_ID}/logs/run.out
```

There's no `wait_for_job.sh` — the foreground pipe blocks until the process exits. Exit code is the Python process's: 0 after `delta_done()`, 1 after `delta_blocker()` (which calls `sys.exit(1)`).

Background (for long runs the agent shouldn't block on):

```bash
nohup python {PROJECT_ROOT}/RUNS/{RUN_ID}/experiment.py > {PROJECT_ROOT}/RUNS/{RUN_ID}/logs/run.out 2>&1 &
echo $! > {PROJECT_ROOT}/RUNS/{RUN_ID}/run.pid
# Poll for terminal markers:
tail -f {PROJECT_ROOT}/RUNS/{RUN_ID}/logs/run.out | grep --line-buffered -E '\[DELTA-(DONE|BLOCKER)\]'
```

When wandb is enabled, share the run URL with the human at submission time — that's the primary live dashboard, same as SLURM mode.

#### Step 3 — Post-job processing

- If wandb mode is `offline`: `wandb sync {PROJECT_ROOT}/RUNS/{RUN_ID}/wandb/`
- If wandb mode is `online` (typical for direct): nothing to sync — run is already on the dashboard
- Read `logs/run.out` and `logs/stderr.log` for any details not captured by markers
- After every condition in the planned evidence package is complete, write `REPORTS/{RUN_ID}.md`. One successful
  command is not enough when the conclusion requires additional conditions, controls, or ablations.

#### Step 4 — Failure recovery

If the process exits non-zero (DELTA-BLOCKER or unhandled exception):
1. Read `logs/run.out` and `logs/stderr.log` to diagnose
2. Common fixes: OOM → reduce batch / enable gradient checkpointing; missing dependency → `pip install`; CUDA error → check GPU is visible (`nvidia-smi`) and not held by another process; env mismatch → re-validate against INFRA.md `validated env activation`
3. Apply the fix to `experiment.py`, re-run. Iterate up to 2-3 times.
4. Only escalate to BLOCKER if the failure is structural — wrong assumption in the plan, missing data, or environment issue requiring human action. Write `RUNS/{RUN_ID}/BLOCKER.md` using `templates/BLOCKER.template.md`; do not write a research report, append the Ledger, increment the run count, or allocate a new ID.

Recovery happens *inside the run*. If it succeeds, the supervisor sees one report covering the complete outcome.

---

### SLURM Mode

When execution mode is `slurm`, the worker generates self-contained scripts and submits via SLURM. The agent runs on the login node — never execute GPU workloads directly.

#### Step 0 — Optional risk probe

Do not create a smoke job by default. Use one only when the working plan names a concrete failure risk for an
expensive job and a probe bounded to at most 10% of the run budget can resolve it.

Smoke and hero are one research run. A completed smoke job is not research evidence and must not trigger a report,
state compression, publication, or a new R###. Continue to the main job under the same plan and run ID.

**Procedure:**
1. Generate `experiment_smoke.py` — same code as `experiment.py`, but parameterized for the smoke config (small dataset slice, few steps, small batch, 1 GPU)
2. Generate `job_smoke.sh` — same env activation, but with the smoke walltime, GPUs, and the fast-queue partition (from INFRA.md → Cluster → Partitions, if one exists)
3. Submit and wait: `JOB_ID=$(sbatch --parsable {PROJECT_ROOT}/RUNS/{RUN_ID}/job_smoke.sh)` then `bash scripts/wait_for_job.sh ${JOB_ID} {PROJECT_ROOT}/RUNS/{RUN_ID}/slurm-smoke-${JOB_ID}.out`
4. Read the smoke output to extract: throughput (steps/sec or tokens/sec), peak VRAM, time per step
5. Compare against the plan's single `continue when` condition. Edit the working plan/scripts directly when the
   result requires a path, batch, precision, resource, or walltime change.
6. On success, `experiment_smoke.py` emits `[DELTA-SMOKE-DONE]`; `wait_for_job.sh` exits 0 without treating R### as complete.
7. On success, submit the measurement immediately. If the probe cannot resolve its named risk within its cap, stop
   only when that risk is an actual blocker; do not invent another gate.

**A smoke test is justified only when all are true:**
- The main run is materially expensive relative to the probe
- One specific failure risk is plausible and observable in the probe
- The probe consumes at most 10% of the run budget
- Its result will immediately change execution or authorize the measurement; it is not generic validation

**Common things smoke tests catch** (each one is a wasted hero run if missed):
- Dataset path not mounted on compute nodes
- OOM at hero batch size
- Precision mismatch (FP16 NaNs, BF16 loss-scale issue)
- Slow DataLoader bottleneck (GPU util <50%)
- Walltime underestimate (smoke 10min × 100 = 1000min, but plan said 480min)
- DELTA markers not firing because of stdout buffering

#### Step 1 — Generate `experiment.py`

Write `RUNS/{RUN_ID}/experiment.py` — a standalone Python script that:
- Includes the DELTA marker helpers (from Python helper section above)
- Includes the `ExperimentLogger` (from Full Logging section above)
- Includes wandb logging when wandb mode is not `disabled`
- Implements the plan commands — can use Python code, `subprocess` calls, `torchrun`, `accelerate launch`, or call existing scripts
- Wraps the entire execution in try/except with `delta_blocker()` on fatal errors
- Calls `delta_start()` at the beginning, `delta_done()` at the end
- Emits `delta_progress()` at milestones (10%, 25%, 50%, 75%, 90%)
- Emits `delta_metric()` at log intervals (sparse — NOT every step)
- Logs to `ExperimentLogger` at EVERY step (dense — for analysis)
- Uses `flush=True` on ALL print calls (critical for SLURM output buffering)

#### Step 2 — Generate `job.sh`

Write `RUNS/{RUN_ID}/job.sh` using the INFRA.md submission template:
- **All paths must be absolute.** Read `project root` from INFRA.md Job Execution. Prefix all project-relative paths with it.
- Set `#SBATCH --output={PROJECT_ROOT}/RUNS/{RUN_ID}/slurm-%j.out`
- Add `cd {PROJECT_ROOT}` as the first command after the SBATCH header — this anchors all relative paths
- Set `#SBATCH` directives from the plan's SLURM section (walltime, GPUs, memory, partition)
- Use the **validated env activation** from INFRA.md Job Execution — must be the exact form proven by the SLURM test job, not a generic `conda activate <name>` or bare `source activate` (`.bashrc` is usually not sourced under sbatch). For conda use the absolute `source /<prefix>/etc/profile.d/conda.sh && conda activate <env>`; for uv/venv use `source /abs/path/.venv/bin/activate` (or prepend the venv's `bin/` to `PATH`); for pixi use `eval "$(pixi shell-hook --manifest-path /abs/path/pixi.toml)"`
- Set wandb env vars: `WANDB_PROJECT`, `WANDB_MODE`, `WANDB_RUN_NAME`, `WANDB_DIR={PROJECT_ROOT}/RUNS/{RUN_ID}/wandb`
- Launch command: `python {PROJECT_ROOT}/RUNS/{RUN_ID}/experiment.py`

**Why absolute paths:** Compute nodes may start in a different CWD (e.g. `/home/user` or `/tmp`). Even with `cd`, the `#SBATCH --output` path is resolved before any commands run, so it must be absolute. Model checkpoints and dataset paths from the plan are already absolute.

#### Step 3 — Submit and monitor

```bash
# Submit — capture job ID (use absolute paths)
JOB_ID=$(sbatch --parsable {PROJECT_ROOT}/RUNS/{RUN_ID}/job.sh)
echo "Submitted job ${JOB_ID}"

# Block until completion — streams DELTA markers
bash {PROJECT_ROOT}/scripts/wait_for_job.sh ${JOB_ID} {PROJECT_ROOT}/RUNS/{RUN_ID}/slurm-${JOB_ID}.out
```

**Do NOT manually poll `squeue -j` or `tail -f` the output file in a loop.** `wait_for_job.sh` already does this with a FIFO-based reader and a 30s safety net for vanished jobs. Repeated `squeue` polling wastes tokens and adds latency. The script blocks until DELTA-SMOKE-DONE / DELTA-DONE / DELTA-BLOCKER, then exits with the right code.

**For long jobs**, the human-facing observability is wandb. The DELTA markers in stdout give the agent automation signals (start, milestones, done); wandb gives the human a live dashboard with metrics, plots, and ETA. If wandb is enabled, share the run URL with the human at submission time so they can watch progress without reading the SLURM output.

#### Step 4 — Post-job processing

After the job completes:
- If wandb mode is `offline`, sync: `wandb sync RUNS/{RUN_ID}/wandb/`
- Read the full SLURM output file for any details not captured by markers
- After every job/condition in the planned evidence package is complete, write `REPORTS/{RUN_ID}.md`.

#### Step 5 — Failure recovery

If `wait_for_job.sh` exits non-zero (DELTA-BLOCKER, vanished, timeout):
1. Read the SLURM output file and `RUNS/{RUN_ID}/logs/stderr.log` to diagnose
2. Common fixes: OOM → reduce batch / enable gradient checkpointing; missing path → check the path is mounted on compute nodes; env activation failed → re-validate against INFRA.md `validated env activation`; CUDA error → check GPU was actually requested
3. Apply the fix to `experiment.py` or `job.sh`, resubmit. Iterate up to 2-3 times.
4. Only escalate to BLOCKER if the failure is structural. Write `RUNS/{RUN_ID}/BLOCKER.md` using `templates/BLOCKER.template.md`; do not write a
   research report, append the Ledger, increment the run count, or allocate a new ID.

Recovery happens *inside the run*. If it succeeds, the supervisor sees one report covering the complete outcome.
Don't surface mid-run failures unless they are genuine blockers.
