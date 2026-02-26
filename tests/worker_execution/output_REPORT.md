# REPORT — R003

## Summary
I benchmarked Python `sorted()` on synthetic arrays with duplicate ratios of 0%, 50%, 80%, and 95% across sizes from 1K to 5M elements, using 5 repetitions per configuration and median as the primary metric. Sorting became consistently faster as duplicate ratio increased, with strong effects at 95% duplicates (for 1M elements: 3.63x speedup vs baseline). This strongly supports belief #3 that duplicate-heavy distributions reduce sorting time.

## Motivation
This run tests belief #3 (confidence 0.45): duplicate-heavy distributions reduce sorting time due to equal-element optimization effects. Per plan thresholds: speedup >1.2x at 95% duplicates (1M) supports the belief; speedup <1.05x across ratios would contradict it.

## Method
1. Used `/Users/jianingqi/miniconda3/envs/agentlab/bin/python` and verified required packages were available there.
2. Generated arrays for sizes `[1_000, 10_000, 100_000, 1_000_000, 5_000_000]` with duplicate ratios `[0.0, 0.5, 0.8, 0.95]`.
3. For each `(size, ratio)`, filled `ratio * size` randomly selected positions with `42.0`; remaining values were random floats. Reproducibility used deterministic seeds derived from base seed 42.
4. Timed `sorted(array.tolist())` for 5 repetitions, recording median/min/max and variance ratio (`max/min`).
5. For confound check, also timed `list.sort()` on `array.tolist()` for the same repetitions.
6. Computed speedup per size as `baseline_median(0% dup) / median(dup_ratio)`.
7. Saved raw data and plots under `tests/worker_execution/artifacts/`.

## Results

### Data

| Size | Dup % | `sorted()` median (s) | min (s) | max (s) | max/min | `list.sort()` median (s) |
|------|-------|------------------------|---------|---------|---------|---------------------------|
| 1,000 | 0 | 0.000063 | 0.000058 | 0.000078 | 1.34 | 0.000053 |
| 1,000 | 50 | 0.000045 | 0.000043 | 0.000056 | 1.31 | 0.000041 |
| 1,000 | 80 | 0.000031 | 0.000029 | 0.000037 | 1.26 | 0.000028 |
| 1,000 | 95 | 0.000022 | 0.000021 | 0.000025 | 1.16 | 0.000020 |
| 10,000 | 0 | 0.000907 | 0.000847 | 0.000928 | 1.10 | 0.000893 |
| 10,000 | 50 | 0.000635 | 0.000610 | 0.000668 | 1.10 | 0.000602 |
| 10,000 | 80 | 0.000386 | 0.000375 | 0.000432 | 1.15 | 0.000368 |
| 10,000 | 95 | 0.000244 | 0.000237 | 0.000259 | 1.10 | 0.000219 |
| 100,000 | 0 | 0.011895 | 0.011028 | 0.012851 | 1.17 | 0.011393 |
| 100,000 | 50 | 0.007971 | 0.007574 | 0.008497 | 1.12 | 0.007994 |
| 100,000 | 80 | 0.004558 | 0.004408 | 0.005050 | 1.15 | 0.004279 |
| 100,000 | 95 | 0.002647 | 0.002597 | 0.002825 | 1.09 | 0.002470 |
| 1,000,000 | 0 | 0.159403 | 0.147269 | 0.167614 | 1.14 | 0.163908 |
| 1,000,000 | 50 | 0.104756 | 0.098788 | 0.113545 | 1.15 | 0.099721 |
| 1,000,000 | 80 | 0.060157 | 0.057925 | 0.065706 | 1.13 | 0.056692 |
| 1,000,000 | 95 | 0.043967 | 0.039685 | 0.044569 | 1.12 | 0.036276 |
| 5,000,000 | 0 | 0.912968 | 0.839873 | 0.922148 | 1.10 | 0.904347 |
| 5,000,000 | 50 | 0.623456 | 0.605593 | 0.655233 | 1.08 | 0.609785 |
| 5,000,000 | 80 | 0.355789 | 0.344005 | 0.377202 | 1.10 | 0.333328 |
| 5,000,000 | 95 | 0.191562 | 0.188248 | 0.210146 | 1.12 | 0.194142 |

Speedup of `sorted()` vs 0% duplicate baseline:

| Size | 50% dup | 80% dup | 95% dup |
|------|---------|---------|---------|
| 1,000 | 1.40x | 2.06x | 2.86x |
| 10,000 | 1.43x | 2.35x | 3.72x |
| 100,000 | 1.49x | 2.61x | 4.49x |
| 1,000,000 | 1.52x | 2.65x | 3.63x |
| 5,000,000 | 1.46x | 2.57x | 4.77x |

Threshold check (from plan):
- Speedup at 95% duplicates, 1M elements = **3.63x** (>1.2x target, supports belief)
- Variance reliability: all measured `max/min` ratios were <2.0 (and far below blocker threshold 5.0)

### Visualizations
![Median sort time vs size](tests/worker_execution/artifacts/plot1_median_time_vs_size.png)
![Speedup vs duplicate ratio](tests/worker_execution/artifacts/plot2_speedup_vs_duplicate_ratio.png)
![Confound check sorted vs list.sort](tests/worker_execution/artifacts/plot3_confound_sorted_vs_listsort.png)

### Analysis
Results show a strong monotonic trend: higher duplicate ratios consistently reduce sort times, and the effect grows with problem size. The discriminating criterion was exceeded by a wide margin (3.63x at 1M, 95% duplicates), so evidence is high-signal rather than marginal.

The confound check (`sorted()` vs `list.sort()`) shows both methods gain similar speedups as duplicates increase. That pattern suggests the effect is not specific to one Python API path and is consistent with core sort behavior under duplicate-heavy keys (likely reduced effective comparison work and favorable run behavior). It does not isolate cache/memory vs comparator-structure effects by itself, but it does confirm the phenomenon is robust across both call styles.

## Signal
- **discrimination**: discriminating
- The tested delta clearly separated expected outcomes: speedups were large and consistent, not near-noise.
- Key observation: at fixed size, speedup scales strongly with duplicate ratio; at high duplicate ratios, large arrays show multi-x gains.

## Verdict
**supports** — belief #3: duplicate-heavy distributions substantially reduce sorting time in Python `sorted()` under this synthetic setup.

## Confounds
- Data construction uses one duplicated value (`42.0`), which is an extreme duplicate pattern; real distributions with many repeated but non-identical values may behave differently.
- Benchmark includes `array.tolist()` each repetition, so timings combine conversion + sorting costs. Relative effects remain clear but pure sort-only effects may differ.
- Single-machine run; CPU state/background load may affect absolute times.

## New hypotheses
- Duplicate-ratio speedup may saturate beyond a dataset-dependent threshold (e.g., diminishing improvement between 80% and 95% for some sizes).

## Next tests
1. Isolate conversion overhead by benchmarking pre-built Python lists only, then compare with current results.
2. Repeat with multi-valued duplicate distributions (e.g., 10, 100, 1000 unique values) to map speedup vs cardinality, not only one repeated value.
3. Vary data order structure (random vs partially sorted + duplicates) to test interaction between run detection and duplicate effects.

## Artifacts
- `tests/worker_execution/artifacts/timings.csv` — per-configuration median/min/max/variance for `sorted()` and `list.sort()`.
- `tests/worker_execution/artifacts/speedups.csv` — computed speedup vs 0%-duplicate baseline.
- `tests/worker_execution/artifacts/raw_results.json` — raw repetition-level timings and run status.
- `tests/worker_execution/artifacts/plot1_median_time_vs_size.png` — log-log time scaling by duplicate ratio.
- `tests/worker_execution/artifacts/plot2_speedup_vs_duplicate_ratio.png` — speedup curves by size.
- `tests/worker_execution/artifacts/plot3_confound_sorted_vs_listsort.png` — confound comparison across APIs.
- `tests/worker_execution/artifacts/run_summary.json` — compact execution summary.

## Meta
- **run_id**: R003
- **delta**: benchmark `sorted()` with varying duplicate ratios and compare against baseline plus `list.sort()` confound check
- **started**: 2026-02-25T20:53:25 (local, inferred from runtime)
- **completed**: 2026-02-25T20:53:51 (local)
- **status**: completed
