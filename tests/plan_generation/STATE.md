# STATE — sorting-perf

## Meta
- **project**: sorting-perf
- **goal**: Understand which factors most affect Python sorting performance on real-world data distributions
- **started**: 2026-02-20
- **last_updated**: 2026-02-22
- **total_runs**: 2
- **last_experimental_evidence**: R002
- **direction_recovery_used_since_experiment**: false
- **status**: active
- **paradigm**: v1

---

## Environment
- **conda/venv**: `conda activate sorting-perf`
- **python**: 3.11.5
- **key packages**: numpy 1.26.0, matplotlib 3.8.0, pandas 2.1.0
- **gpu**: N/A
- **confirmed gpu count**: N/A
- **CPU**: AMD Ryzen 9 5900X (12 cores)
- **checkpoints**: N/A
- **datasets**: `data/synthetic_arrays.npz` (pre-generated arrays: random, nearly-sorted, reversed, many-duplicates; sizes 1K to 10M)
- **working dir**: /home/user/sorting-perf

---

## BeliefState

| # | Parent | Belief | Status | Confidence | Key evidence | Last updated |
|---|--------|--------|--------|------------|--------------|--------------|
| 1 | — | Timsort's advantage over quicksort grows with nearly-sorted data | active | 0.7 | R001: 3.2x faster on 90%-sorted arrays (1M elements) | 2026-02-21 |
| 2 | — | Buffer allocation and copying account for more than half of copy-plus-sort time on random arrays above 1M elements | active | 0.5 | R002: inconclusive — alloc/copy timing noisy, need better isolation | 2026-02-22 |
| 3 | — | Duplicate-heavy distributions reduce sorting time due to equal-element optimizations | active | 0.45 | seed — untested | 2026-02-20 |

## Ledger

| Run | Question | Key result | Conclusion | Belief | Link |
|-----|----------|------------|------------|--------|------|
| R001 | Does Timsort beat quicksort on nearly-sorted 1M arrays? | Timsort was 3.2× faster | supports | #1 | [R001](REPORTS/R001.md) |
| R002 | Do allocation and copying exceed half of copy-plus-sort time? | Timing was too noisy to isolate the fraction | cannot decide | #2 | [R002](REPORTS/R002.md) |

## Frontier

| Rank | Experiment question | Target | Decision result | Minimum complete evidence | ETA | Blocked by |
|------|---------------------|--------|-----------------|---------------------------|-----|------------|
| 1 | Do 95% duplicates speed up `sorted()` at 1M elements? | #3 | Median speedup >1.2× supports; <1.05× contradicts | Matched 0%/95% arms, three repetitions each, max/min <2× | 8 min | — |
| 2 | Do allocation and copying exceed half of copy-plus-sort time? | #2 | Fraction >0.50 supports; <0.50 contradicts | Paired baseline/preallocated measurements at 5M and 10M with intervals excluding 0.50 | 25 min | — |

## Policy

### Interrupt boundaries
- `GOAL`: target hypothesis adequately supported or contradicted and no explicit question remains
- `BUDGET`: 2 hours cumulative
- `NULL_STREAK`: 3 consecutive completed experiments that cannot decide
- `STALL`: no decision-capable experiment can be specified
- `BLOCKER`: worker returns BLOCKER
- `AMBIGUITY`: frontier empty AND regeneration fails
- `IRREVERSIBLE`: irreversible action needs human approval

### Constraints
- One coherent hypothesis question per run
- Worker must not modify STATE.md or choose directions
- Keep baseline, treatment, repetitions, controls, and necessary ablations under one R###
- Setup, retries, individual conditions, plots, and analysis are not separate runs
- Among complete experiments capable of answering, choose the shortest total ETA
- Do not invent follow-up work after the target hypothesis is decided
- Scientific literature search is forbidden while an experiment exists; one bounded recovery is allowed only
  after experimental failure plus an empty regenerated Frontier

## Scratch
- R002 had high variance in alloc measurements — might need to pin CPU frequency or use median of 50+ trials
- Consider testing PyPy vs CPython as a follow-up if alloc hypothesis is confirmed
