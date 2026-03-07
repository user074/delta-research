# PLAN — R003

## Delta
- **what**: Isolate allocation cost on random arrays from `data/synthetic_arrays.npz` by benchmarking in-place sort versus workflows that force an explicit copy/allocation step on sizes 1M, 5M, and 10M, using repeated trials and per-size variance analysis across all 12 CPU cores.
- **intent**: Resolve whether memory allocation is actually the dominant contributor for large-array sorting or whether R002's noisy measurements masked a smaller effect. This delta is selected by bandit reasoning: candidate `#2` targets belief `#2` at confidence `0.5` (highest uncertainty), offers medium-to-high info gain because forced-allocation versus in-place timings should separate costs cleanly, and has medium feasibility because variance control is required but the dataset and hardware already exist.
- **target belief**: #2 — Memory allocation is the dominant cost for large arrays (>1M), not comparisons
- **type**: analysis

## Resources
<!-- Exact paths. Worker uses ONLY these — no assumptions, no substitutions. -->
<!-- If a resource is missing, worker must BLOCKER. -->
- **checkpoint**: N/A
- **dataset**: `data/synthetic_arrays.npz`
- **prior artifacts**: N/A
- **output dir**: RUNS/R003/artifacts/

## Commands
<!-- Detailed step-by-step. Each step should explain WHAT to do and HOW to interpret results. -->
<!-- Multiple analysis steps that build on each other. Not just "run a script". -->

### Step 1: Verify environment and extract random-array slices
Activate `conda activate sorting-perf`, confirm Python 3.11.5 with the listed numpy/matplotlib/pandas versions, and work from `/home/user/sorting-perf`. Load `data/synthetic_arrays.npz`, identify the random-distribution arrays for sizes 1M, 5M, and 10M, and record their exact keys, dtypes, and shapes in the report. If the file does not contain those random arrays exactly, stop with BLOCKER because the plan depends on the Environment-defined dataset.

### Step 2: Build an allocation-isolation benchmark with controlled variants
For each selected random array size, benchmark at least three variants: `(a)` in-place sort on a reused mutable copy, `(b)` explicit allocate-or-copy step immediately followed by sort, and `(c)` allocation-or-copy only without sorting. Run enough repetitions to stabilize medians and dispersion, with a minimum of 50 trials per size/variant unless the time budget forces fewer for 10M arrays. Use multiprocessing to saturate all 12 CPU cores by distributing independent trials across workers. The interpretation logic is: if variant `(c)` plus the gap between `(a)` and `(b)` accounts for most end-to-end time, allocation dominance is supported; if sorting time in `(a)` remains the majority term, the belief is contradicted.

### Step 3: Quantify variance and attribution, not just averages
For every size and variant, compute median, mean, standard deviation, coefficient of variation, and 5th/95th percentile timing. Then derive an attribution table with estimated `allocation_share = median(copy_only) / median(copy_plus_sort)` and `comparison_share = median(in_place_sort) / median(copy_plus_sort)`. Focus interpretation on medians and percentile spread because R002 was explicitly noisy. If variance remains high, report whether the conclusion is still directionally stable across median-based estimates.

### Step 4: Test the belief threshold across sizes
Compare attribution across 1M, 5M, and 10M arrays to check whether the hypothesis only emerges at the upper end of the size range. Use the exact same benchmarking code path for all sizes so differences are attributable to scale rather than implementation drift. Interpret results by size: if allocation share rises and exceeds 50% only at 10M, the belief is partially supported with a size threshold; if it stays below 50% at all sizes, the dominance claim is contradicted.

### Step 5: Visualize and stress-check the conclusion
Generate at least two plots in `RUNS/R003/artifacts/`: one plot of median time by size and variant, and one stacked or side-by-side plot of estimated allocation versus in-place-sort contribution by size. Add a short stress check by comparing conclusions from medians against means; if they disagree materially, call that out as a confound rather than smoothing it away.

### Final step: Write report
Write report to REPORTS/R003.md following the report template.
Include all data inline, generate visualizations, embed plots with ![](path).

## Success metrics
| Metric | Baseline | Target | How to measure |
|--------|----------|--------|----------------|
| Allocation share on 5M random arrays | R002 inconclusive due to noisy allocation timing | `> 0.50` supports the belief that allocation is dominant at large sizes | `median(copy_only) / median(copy_plus_sort)` from repeated trials |
| Allocation share on 10M random arrays | R002 inconclusive due to noisy allocation timing | `> 0.50` strongly supports; `< 0.35` contradicts dominance | Same attribution calculation on 10M random arrays |
| Variance control | R002 described alloc timing as noisy | Coefficient of variation low enough that median-based ranking of variants is stable across sizes | Compare coefficient of variation and 5th/95th percentile spread for each variant |
| Size trend | No confirmed scaling trend yet | Allocation share increases from 1M to 10M if dominance is real | Compare attribution table across 1M, 5M, and 10M |

## Stop conditions
- BLOCKER if: `data/synthetic_arrays.npz` does not contain random arrays for sizes 1M, 5M, and 10M
- BLOCKER if: the environment cannot activate `sorting-perf` or listed packages are unavailable
- BLOCKER if: timing noise remains so extreme that medians do not provide a stable ordering between in-place sort, copy+sort, and copy-only after the planned repetitions
- BLOCKER if: resource not found at specified path
- TIMEOUT after: 90 minutes

## Context
<!-- Rich context from STATE.md. Include specific numbers, prior findings, anomalies. -->
<!-- Reference specific report files and data artifacts the worker may need. -->

**Relevant beliefs:**
- Belief #2 (confidence `0.5`): Memory allocation is the dominant cost for large arrays (`>1M`), not comparisons — current evidence is explicitly inconclusive from R002 because allocation timing was noisy, making this the most uncertain belief and the best next bandit target.
- Belief #3 (confidence `0.45`): Duplicate-heavy distributions reduce sorting time due to equal-element optimizations — also uncertain, but slightly farther from `0.5`; defer until belief #2 is resolved or down-ranked with stronger evidence.
- Belief #1 (confidence `0.7`): Timsort's advantage over quicksort grows with nearly-sorted data — currently less uncertain and not the next best discriminator.

**Prior findings:**
- R001: On `1M` element `90%`-sorted arrays, timsort was `3.2x` faster than quicksort, which raised belief #1 to confidence `0.7`.
- R002: Profiling on random `5M` arrays produced only a `partial` signal and `unclear` verdict for belief #2 because allocation measurements were noisy rather than cleanly separable.
- Frontier comparison for this planning pass: candidate for belief `#3` had uncertainty `high` at confidence `0.45`, info gain `high`, feasibility `high`; candidate for belief `#2` had uncertainty `high` at confidence `0.5`, info gain `med`, feasibility `med`. This run selects `#2` because the confidence is nearest `0.5`, satisfying the supervisor rule to target the most uncertain belief first.
- Available hardware from Environment is CPU-only with `12` cores on an AMD Ryzen 9 5900X and `gpu: N/A`, so the run should maximize throughput with parallel trial execution across all CPU cores rather than leaving repetitions serialized.

## Meta
- **run_id**: R003
- **created**: 2026-03-07
- **time_budget**: 90 minutes
- **status**: planned
