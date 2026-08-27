# REPORT — R003: Do duplicate-heavy inputs reduce Python sorting time?

## Answer

The result supports the hypothesis for this synthetic-float setup: 95% duplicates made sorting 1.8× faster at 1M elements and 2.1× faster at 5M. `list.sort()` showed the same pattern while `heapq.nsmallest` improved only 1.05×, although this run does not prove the exact Timsort mechanism.

## Motivation

Belief #3 predicted that duplicate-heavy distributions reduce sorting time. Before this run it had no experimental evidence and confidence 0.45.

## Questions tested

1. **Primary:** Does 95% duplication materially reduce `sorted()` time, with >1.2× supporting and <1.05× contradicting belief #3?
2. **Secondary:** Is the effect present in `list.sort()` but absent from a non-Timsort comparison?

## Method

- **approach:** Vary duplicate ratio and array size while holding value type and timing procedure fixed.
- **data:** Seed-42 synthetic floats at 1K, 10K, 100K, 1M, and 5M elements; duplicate ratios 0%, 50%, 80%, and 95%.
- **comparisons:** `sorted()` main grid, `list.sort()` control, and `heapq.nsmallest` alternative.
- **metrics:** Median runtime and speedup relative to the 0% baseline.
- **repetitions:** Seven per condition.
- **environment:** CPython with NumPy on one CPU machine.
- **parallel execution:** CPU-only, one timing process; GPU count N/A.
- **scientific changes during execution:** None.

## Experiments

| Experiment | Why it is needed | Comparison / conditions |
|------------|------------------|-------------------------|
| Main size/duplicate grid | Tests the empirical claim across scale | 5 sizes × 4 ratios |
| Algorithm control | Checks whether the effect is Timsort-specific | `list.sort()` and `heapq.nsmallest` at 1M/95% |

## Results

| Experiment / condition | Primary result | Uncertainty / repetitions | Meaning |
|------------------------|----------------|---------------------------|---------|
| `sorted()`, 1M/95% | 1.8× speedup | 7 repetitions, max/min 1.12 | Supports |
| `sorted()`, 5M/95% | 2.1× speedup | 7 repetitions, max/min 1.09 | Supports across scale |
| `list.sort()`, 1M/95% | 1.8× speedup | 7 repetitions | Same direction |
| `heapq.nsmallest`, 1M/95% | 1.05× speedup | 7 repetitions | Little change outside Timsort |

- **wall-clock to answer:** 12 minutes from launch to complete report.
- **GPU use, if applicable:** N/A — CPU-only experiment.

## Analysis

The effect exceeded the 1.2× support threshold at both large sizes and remained stable over seven repetitions. The `list.sort()` control reproduced it, while `heapq.nsmallest` did not. This makes duplicate ratio a material sorting-performance factor in the tested setup, but the controls do not isolate which Timsort behavior causes the gain.

## Ablations (optional)

The algorithm control acted as the necessary ablation: changing from Timsort to `heapq.nsmallest` reduced the observed gain from 1.8× to 1.05×.

## Limitations and tested scope

The result covers synthetic floats with one repeated value on this CPython environment. Other value types and duplicate distributions could change the magnitude. It does not directly measure Timsort internals.

## Conclusion

- **answer:** supports hypothesis/belief #3.
- **decisive evidence:** 95% duplicates produced 1.8× speedup at 1M and 2.1× at 5M over seven repetitions.
- **confidence:** 0.45 → 0.85 because the effect was large, stable, and reproduced across sizes.
- **next experiment:** None — the stated empirical hypothesis is decided in this scope.

## Reproducibility

- **command:** `python RUNS/R003/scripts/benchmark_duplicates.py`
- **parallelism:** One CPU timing process; no GPU ranks.
- **metrics:** `../RUNS/R003/metrics/benchmark_data.csv`
- **artifacts:** None needed.

## Meta

- **run_id**: R003
- **started**: 2026-02-23 10:00
- **completed**: 2026-02-23 10:12
- **execution**: direct
- **slurm_job_id**: N/A
- **wandb_run**: N/A
