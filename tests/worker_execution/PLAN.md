# PLAN — R003

## Delta
- **what**: Benchmark Python's `sorted()` on arrays with varying duplicate ratios (50%, 80%, 95%) across sizes 1K to 10M to test whether duplicate-heavy distributions reduce sorting time
- **intent**: Determine if Timsort's equal-element optimizations produce measurable speedup on high-duplicate data, and how the effect scales with array size
- **target belief**: #3 — Duplicate-heavy distributions reduce sorting time due to equal-element optimizations
- **type**: experiment

## Resources
- **checkpoint**: N/A
- **dataset**: Generate synthetic arrays inline (numpy random with controlled duplicate ratios)
- **prior artifacts**: None needed — this is a fresh benchmark
- **output dir**: RUNS/R003/artifacts/

## Commands

### Step 1: Generate test arrays
For each size in [1_000, 10_000, 100_000, 1_000_000, 5_000_000]:
- Generate a baseline array of random floats (0% duplicates)
- Generate arrays with 50%, 80%, 95% duplicate ratios
- For N% duplicates: fill N% of positions with the value 42.0, rest are random floats
- Use `numpy.random.seed(42)` for reproducibility

### Step 2: Benchmark sorting
For each (size, duplicate_ratio) combination:
- Time `sorted(array.tolist())` using `timeit` with at least 5 repetitions
- Record median time (not mean — reduces outlier sensitivity)
- Also record min and max for variance assessment
- Important: convert numpy array to list first (`sorted()` is the target, not `numpy.sort()`)

### Step 3: Compute speedup relative to baseline
For each size:
- Compute speedup = baseline_median / duplicate_median for each duplicate ratio
- If speedup > 1.2 at 95% duplicates, that's meaningful evidence for belief #3
- If speedup < 1.05 across all ratios, that contradicts belief #3

### Step 4: Visualize results
- Plot 1: Median sort time vs array size, one line per duplicate ratio (log-log scale)
- Plot 2: Speedup vs duplicate ratio, one line per array size
- Save both to RUNS/R003/artifacts/

### Step 5: Check for confounds
- Is the speedup (if any) from fewer unique values reducing cache misses, rather than Timsort's equal-element optimization?
- Test: compare `sorted()` vs `list.sort()` — if both show same speedup, it's likely cache/memory, not algorithm-specific

### Final step: Write report
Write report to REPORTS/R003.md following the report template.
Include all timing data inline, generate visualizations, embed plots with ![](path).

## Success metrics
| Metric | Baseline | Target | How to measure |
|--------|----------|--------|----------------|
| Speedup at 95% duplicates, 1M elements | 1.0x (random baseline) | >1.2x would support #3 | median(baseline) / median(95%-dup) |
| Speedup at 95% duplicates, 1M elements | 1.0x (random baseline) | <1.05x would contradict #3 | same ratio |
| Variance (max/min ratio) | — | <2.0 for reliable results | max_time / min_time per config |

## Stop conditions
- BLOCKER if: any single benchmark takes >5 minutes (suggests size too large)
- BLOCKER if: variance (max/min) exceeds 5x (results unreliable)
- TIMEOUT after: 15 minutes

## Context
**Relevant beliefs:**
- Belief #3 (confidence 0.45): Duplicate-heavy distributions reduce sorting time due to equal-element optimizations — untested seed belief

**Prior findings:**
- R001: Timsort 3.2x faster than quicksort on 90%-sorted arrays at 1M elements — shows Timsort does exploit structure
- R002: Memory alloc profiling was noisy, inconclusive on whether alloc or comparisons dominate

## Meta
- **run_id**: R003
- **created**: 2026-02-23
- **time_budget**: 15 minutes
- **status**: planned
