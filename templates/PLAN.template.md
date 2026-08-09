# PLAN — (run ID)

## Delta
- **what**: (what to change or test — be specific about the analysis, not just "run X")
- **intent**: (why — what we hope to learn, what question this answers)
- **target belief**: #N — (the belief(s) this should discriminate, can target multiple)
- **type**: (literature-review | experiment | analysis | exploration | refactor)

## Literature Grounding

<!-- REQUIRED for every run.
     Literature-review run: status=pending; this run grounds exactly one belief. Fill search scope fields.
     Other run: status=grounded; cite the exact REPORTS/R###.md review and its design implications. -->
- **status before run**: (pending | grounded | refresh-needed)
- **target belief**: #N — (exact wording from BeliefState)
- **review artifact**: (this run | `REPORTS/R###.md`)
- **grounding implications**: (for empirical runs, what prior evidence changed in the design)

<!-- Required only for type=literature-review. Remove these fields for an empirical run. -->
- **search questions**: (direct evidence, mechanism/alternatives, methods/failures, novelty)
- **query families**: (exact planned query families; worker records exact strings used)
- **required counterevidence**: (strongest null/negative/boundary-condition evidence to seek)
- **implementation scan**: (official code, data, metrics, prompts, checkpoints, baselines to find)
- **coverage standard**: (primary-source expectations and acceptable stopping rule; do not pad sparse fields)

## Resources
<!-- Exact resource identities and paths. Identity-equivalent path/API repairs are Class A amendments.
     A different checkpoint, dataset, intervention, or endpoint is not a path repair. -->
- **checkpoint**: (exact path to model checkpoint, if applicable)
- **dataset**: (exact path to dataset)
- **prior artifacts**: (paths to artifacts from earlier runs that this run builds on)
- **output dir**: RUNS/(run ID)/artifacts/
- **precision**: (from INFRA.md — e.g. BF16, FP16, FP32)
- **parallelism**: (from INFRA.md — e.g. "DDP, 4 GPUs", "single GPU", "CPU only")
- **launch**: (from INFRA.md — e.g. `torchrun --nproc_per_node=4`)
- **scratch path**: (from INFRA.md Storage — fast path for intermediates)
- **execution mode**: (direct | slurm — from INFRA.md Job Execution)
- **literature access**: (for literature-review runs: authorized databases/search engines and source policy; otherwise N/A)
- **literature archive**: (for literature-review runs: `LITERATURE/B###/R###/`; otherwise cited archive or N/A)

<!-- Include this section only when execution mode is slurm -->
## SLURM
- **walltime**: (estimated, e.g. `04:00:00`)
- **gpus**: (count needed, e.g. 4)
- **memory**: (estimate, e.g. `128G`)
- **partition**: (from INFRA.md or override, e.g. `gpu`)

<!-- Required for any non-trivial run (training, long benchmarks, anything >30 min).
     Skip ONLY for quick analyses, simple data processing, or runs <10 min total. -->
## Smoke Test
- **what**: (minimum viable version — e.g. "100 steps on 200 examples, batch size 4, 1% of dataset")
- **walltime**: (short, e.g. `00:15:00`)
- **partition**: (use the fast-queue partition from INFRA.md Cluster → Partitions if one exists)
- **gpus**: 1 (smoke tests run on 1 GPU even if the hero run uses many)
- **validate**:
  - No errors (env activates, data loads, model loads, DELTA markers fire)
  - Throughput (steps/sec or tokens/sec) — used to refine the hero run's walltime
  - Peak VRAM (must leave ≥10% headroom at hero-run batch size)
- **abort hero run if**: peak VRAM > 90%, throughput implies hero walltime > 1.5× plan estimate, or any error

## Commands
<!-- Detailed step-by-step. Each step should explain WHAT to do and HOW to interpret results. -->
<!-- Multiple analysis steps that build on each other. Not just "run a script". -->

### Step 1: (name)
(What to do. What to look for. How to interpret.)

### Step 2: (name)
(What to do, building on step 1 results.)

### Step 3: (name)
(Further analysis or visualization.)

<!-- Add more steps as needed. A good plan has 3-6 substantive steps. -->

### Final step: Write report
Write report to `REPORTS/(run ID).md` following the report template.
Include all data inline.

**Plots:** save every plot to `RUNS/(run ID)/artifacts/<filename>` (the `output dir` declared in Resources). When a Plots step in this plan lists bare filenames like `foo.png`, that's the file *label* — the actual save path is `RUNS/(run ID)/artifacts/foo.png`. Never save plots under `REPORTS/`. Embed in the report with `![description](../RUNS/(run ID)/artifacts/foo.png)` — the leading `../` is required because the report lives in `REPORTS/`.

## Success metrics
| Metric | Baseline | Target | How to measure |
|--------|----------|--------|----------------|
| (metric) | (current value) | (what would support) | (method) |
| (metric) | (current value) | (what would contradict) | (method) |

## Predictions
<!-- Predict outcomes BEFORE running. This calibrates the supervisor's beliefs and gives the
     human a reference to compare against. Surprises are signal — predicted outcomes are
     boring. After the run, the report compares actual vs predicted. -->

| Metric | Predicted value | Confidence | Reasoning |
|--------|----------------|------------|-----------|
| (metric) | (predicted) | (low/med/high) | (1 sentence — why this prediction) |

- **Most likely outcome**: (1 sentence — what the supervisor expects to happen)
- **Surprise scenario**: (what result would surprise you, and what would it mean for the beliefs?)

## Stop conditions
- BLOCKER if: (condition)
- AMENDMENT_NEEDED if: a resource identity is valid but a scope-preserving Class B substitution is required
- BLOCKER if: a required resource is unavailable after Class A repair attempts and no scope-preserving amendment exists
- TIMEOUT after: (time budget)

## Context
<!-- Rich context from STATE.md. Include specific numbers, prior findings, anomalies. -->
<!-- Reference specific report files and data artifacts the worker may need. -->

**Relevant beliefs:**
- Belief #N (confidence X): (statement) — (key evidence so far)

**Prior findings:**
- R###: (specific finding with numbers, not just "see report")

## Amendment policy

- **Class A — worker-autonomous repair**: execution-only fixes that preserve the target belief, causal estimand,
  resource identity, model/dataset family, primary endpoint, success threshold, and predictions. Update the live
  plan, increment `plan_version`, append the log, and continue this run.
- **Class B — supervisor-approved amendment**: scope-preserving resource or method change. Emit
  `AMENDMENT_NEEDED` with the exact proposed diff; resume this same run after approval.
- **Class C — scientific redesign**: changes the target, main intervention/contrast, model or dataset family,
  primary endpoint/threshold, predictions after outcome inspection, or a budget/irreversibility boundary. Do not
  amend; preserve evidence and end or report the run so a new plan can be created.
- `PLAN.initial.md` is never edited. Do not revise goals or thresholds in response to observed results.

## Amendment Log

| Version | Timestamp | Actor | Class | Issue / evidence | Exact change | Scientific impact |
|---------|-----------|-------|-------|------------------|--------------|-------------------|
| v1 | (created timestamp) | supervisor | initial | — | Initial plan | Preregistered baseline |

## Meta
- **run_id**: (R###)
- **created**: (date)
- **time_budget**: (minutes)
- **plan_version**: 1
- **status**: planned
