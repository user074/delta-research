# PLAN — R003

## Delta
- **what**: Benchmark sorting latency on duplicate-heavy arrays at duplicate ratios 50%, 80%, and 95% across array sizes 1K, 10K, 100K, 1M, and 10M; compare against low-duplicate/random baseline from the same dataset split.
- **intent**: Determine whether increasing duplicate ratio materially reduces sort time, and whether the effect size grows with input size.
- **target belief**: #3 — Duplicate-heavy distributions reduce sorting time due to equal-element optimizations.
- **type**: experiment

## Resources
- **checkpoint**: N/A
- **dataset**: `/Users/jianingqi/Github/delta-research/data/synthetic_arrays.npz`
- **prior artifacts**: `/Users/jianingqi/Github/delta-research/REPORTS/R001.md`, `/Users/jianingqi/Github/delta-research/REPORTS/R002.md`
- **output dir**: RUNS/R003/artifacts/

## Commands

### Step 1: Validate inputs and extract benchmark matrix
Confirm dataset exists and contains required distribution groups for duplicate ratios (50/80/95 or nearest matching labels), plus random baseline arrays for each target size. Build a run matrix of `(size, distribution, trial_id)` with at least 30 timing trials per cell. If exact duplicate labels are missing, map to closest available duplicate-heavy groups and record mapping explicitly in the report.

### Step 2: Execute controlled timing benchmark
For each matrix cell, run Python built-in sort (`list.sort()` or equivalent consistent path) under consistent process conditions: warm-up runs, fixed seed order, repeated trials, and median + IQR capture. Record raw trial times to `RUNS/R003/artifacts/timing_raw.csv` and summary table to `RUNS/R003/artifacts/timing_summary.csv`.

### Step 3: Quantify duplicate-ratio effect size
Compute per-size speedup ratios relative to random baseline: `speedup = median_time_random / median_time_duplicate_ratio`. Estimate uncertainty via bootstrap 95% CI (or nonparametric CI from trial medians). Mark each size/ratio cell as:
- supports-local if CI lower bound > 1.05
- contradicts-local if CI upper bound < 1.00
- unclear-local otherwise

### Step 4: Trend and robustness checks
Test monotonicity by checking whether speedup(95%) >= speedup(80%) >= speedup(50%) for each size (allow 5% tolerance for near-equality). Run sensitivity check using trimmed mean (10%) in addition to median; if conclusions differ, flag confound and downgrade signal strength.

### Step 5: Visualize and decision mapping
Generate plots:
- `RUNS/R003/artifacts/speedup_vs_size.png` (lines by duplicate ratio)
- `RUNS/R003/artifacts/time_distribution_boxplots.png` (per size/ratio)
Produce a decision table mapping observed outcomes to Belief #3 update direction (supports/contradicts/unclear).

### Final step: Write report
Write report to REPORTS/R003.md following the report template.
Include all data inline, generate visualizations, embed plots with ![](path).

## Success metrics
| Metric | Baseline | Target | How to measure |
|--------|----------|--------|----------------|
| Median speedup for 95% duplicates vs random at >=3 largest sizes (100K/1M/10M) | Unknown (untested) | >1.20 supports belief | Compute median-time ratio with 95% CI from repeated trials |
| Monotonic duplicate effect (95% >= 80% >= 50%) across sizes | Unknown (untested) | Holds for >=4/5 sizes supports mechanism consistency | Compare per-size speedup ladder with 5% tolerance |
| Evidence against belief | Unknown (untested) | Speedup ~1.0 or <1.0 for most sizes contradicts belief | CI-based classification contradicts-local in >=3/5 sizes |

## Stop conditions
- BLOCKER if: required dataset groups (random + duplicate-heavy at target ratios or mappable equivalents) are absent.
- BLOCKER if: benchmark cannot complete at least 20 valid trials per cell after retries.
- BLOCKER if: resource not found at specified path
- TIMEOUT after: 90 minutes

## Context

**Relevant beliefs:**
- Belief #3 (confidence 0.45): Duplicate-heavy distributions reduce sorting time due to equal-element optimizations — currently seed-only, untested.
- Belief #2 (confidence 0.5): Allocation-cost claim remained unclear in R002 due to noise; this run should avoid over-interpreting alloc effects and focus on distribution-driven timing differences.

**Prior findings:**
- R001: On nearly-sorted arrays (1M), timsort was 3.2x faster than quicksort, showing distribution strongly affects runtime.
- R002: Allocation vs comparison isolation on random 5M arrays was inconclusive due to high variance in alloc measurements.
- Scratch note in STATE: variance issues suggest robust aggregation (median, many trials) is necessary; this plan uses >=30 trials/cell and CI-based decisions.

## Meta
- **run_id**: R003
- **created**: 2026-02-26
- **time_budget**: 90
- **status**: planned
