# PLAN — (run ID)

## Delta
- **what**: (what to change or test — be specific about the analysis, not just "run X")
- **intent**: (why — what we hope to learn, what question this answers)
- **target belief**: #N — (the belief(s) this should discriminate, can target multiple)
- **type**: (experiment | analysis | exploration | refactor)

## Resources
<!-- Exact paths. Worker uses ONLY these — no assumptions, no substitutions. -->
<!-- If a resource is missing, worker must BLOCKER. -->
- **checkpoint**: (exact path to model checkpoint, if applicable)
- **dataset**: (exact path to dataset)
- **prior artifacts**: (paths to artifacts from earlier runs that this run builds on)
- **output dir**: RUNS/(run ID)/artifacts/
- **precision**: (from INFRA.md — e.g. BF16, FP16, FP32)
- **parallelism**: (from INFRA.md — e.g. "DDP, 4 GPUs", "single GPU", "CPU only")
- **launch**: (from INFRA.md — e.g. `torchrun --nproc_per_node=4`)
- **scratch path**: (from INFRA.md Storage — fast path for intermediates)
- **execution mode**: (direct | slurm — from INFRA.md Job Execution)

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
Write report to REPORTS/(run ID).md following the report template.
Include all data inline, generate visualizations, embed plots with ![](path).

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
- BLOCKER if: resource not found at specified path
- TIMEOUT after: (time budget)

## Context
<!-- Rich context from STATE.md. Include specific numbers, prior findings, anomalies. -->
<!-- Reference specific report files and data artifacts the worker may need. -->

**Relevant beliefs:**
- Belief #N (confidence X): (statement) — (key evidence so far)

**Prior findings:**
- R###: (specific finding with numbers, not just "see report")

## Meta
- **run_id**: (R###)
- **created**: (date)
- **time_budget**: (minutes)
- **status**: planned
