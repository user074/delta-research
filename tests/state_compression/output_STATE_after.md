# STATE — sorting-perf

## Meta
- **project**: sorting-perf
- **goal**: Understand which factors most affect Python sorting performance on real-world data distributions
- **started**: 2026-02-20
- **last_updated**: 2026-02-23
- **total_runs**: 3
- **last_experimental_evidence**: R003
- **direction_recovery_used_since_experiment**: false
- **status**: goal-reached
- **paradigm**: v1

## Environment
- **env activation**: `conda activate sorting-perf`
- **python**: 3.11.5
- **key packages**: numpy 1.26.0, matplotlib 3.8.0, pandas 2.1.0
- **gpu**: N/A
- **confirmed gpu count**: N/A
- **datasets**: `data/synthetic_arrays.npz`
- **working dir**: /home/user/sorting-perf

## BeliefState

| # | Parent | Belief | Status | Confidence | Key evidence | Last updated |
|---|--------|--------|--------|------------|--------------|--------------|
| 1 | — | Timsort's advantage over quicksort grows with nearly-sorted data | active | 0.7 | R001: 3.2× faster on 90%-sorted arrays | 2026-02-21 |
| 2 | — | Allocation and copying account for more than half of copy-plus-sort time above 1M elements | active | 0.5 | R002 timing was too noisy | 2026-02-22 |
| 3 | — | Duplicate-heavy distributions reduce sorting time | supported | 0.85 | R003: at 1M items, 95% duplicates made `sorted()` 5.48× faster; all tested sizes moved in the same direction | 2026-02-23 |

## Ledger

| Run | Question | Key result | Conclusion | Belief | Link |
|-----|----------|------------|------------|--------|------|
| R001 | Does Timsort beat quicksort on nearly-sorted 1M arrays? | Timsort was 3.2× faster | supports | #1 | [R001](REPORTS/R001.md) |
| R002 | Do allocation and copying exceed half of copy-plus-sort time? | Timing was too noisy | cannot decide | #2 | [R002](REPORTS/R002.md) |
| R003 | Do duplicate-heavy inputs reduce Python sorting time? | At 1M items, 95% duplicates made `sorted()` 5.48× faster | supports | #3 | [R003](REPORTS/R003.md) |

## Frontier

| Rank | Experiment question | Target | Decision result | Minimum complete evidence | ETA | Blocked by |
|------|---------------------|--------|-----------------|---------------------------|-----|------------|

## Policy
- `GOAL`: target hypothesis decided and no requested question remains
- `NULL_STREAK`: 3 consecutive completed experiments cannot decide
- `STALL`: no decision-capable experiment can be specified
- `BLOCKER`: selected experiment cannot proceed after bounded repair

## Scratch
- R002 had high variance in allocation measurements.
- R003 answered the target hypothesis in the tested scope; no follow-up run was created.
