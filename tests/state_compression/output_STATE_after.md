# STATE — sorting-perf

## Meta
- **project**: sorting-perf
- **goal**: Understand which factors most affect Python sorting performance on real-world data distributions
- **started**: 2026-02-20
- **last_updated**: 2026-02-23
- **total_runs**: 3
- **status**: active
- **paradigm**: v1

---

## Environment
- **conda/venv**: `conda activate sorting-perf`
- **python**: 3.11.5
- **key packages**: numpy 1.26.0, matplotlib 3.8.0, pandas 2.1.0
- **gpu**: N/A
- **checkpoints**: N/A
- **datasets**: `data/synthetic_arrays.npz`
- **working dir**: /home/user/sorting-perf

---

## BeliefState

| # | Parent | Belief | Status | Confidence | Key evidence | Last updated |
|---|--------|--------|--------|------------|--------------|--------------|
| 1 | — | Timsort's advantage over quicksort grows with nearly-sorted data | active | 0.7 | R001: 3.2x faster on 90%-sorted arrays (1M elements) | 2026-02-21 |
| 2 | — | Memory allocation is the dominant cost for large arrays (>1M), not comparisons | active | 0.5 | R002: inconclusive — alloc time noisy | 2026-02-22 |
| 3 | — | Duplicate-heavy distributions reduce sorting time due to equal-element optimizations | supported | 0.85 | R003: discriminating support; 95% duplicates gave 1.8x speedup at 1M and 2.1x at 5M; `list.sort()` matched while `heapq.nsmallest` showed only 1.05x | 2026-02-23 |
| 4 | 3 | Timsort's galloping mode has a super-linear benefit with more duplicates as array size grows | active | 0.5 | R003 new hypothesis: scaling trend showed speedup increasing with size, suggesting size-dependent duplicate benefit | 2026-02-23 |
| 5 | — | Nearly-sortedness and high duplicate ratios compound to produce larger sorting speedups than either factor alone | active | 0.5 | R003 new hypothesis: R001 nearly-sorted speedup and R003 duplicate speedup may compound on mixed-structure data | 2026-02-23 |

## Ledger

| Run | Delta | Signal | Verdict | Belief | Link |
|-----|-------|--------|---------|--------|------|
| R001 | Compare timsort vs quicksort on nearly-sorted 1M arrays | discriminating | supports | #1 | [R001](REPORTS/R001.md) |
| R002 | Profile memory allocation vs comparison time on random 5M arrays | partial | unclear | #2 | [R002](REPORTS/R002.md) |
| R003 | Benchmark sorting with varying duplicate ratios | discriminating | supports | #3 | [R003](REPORTS/R003.md) |

## Frontier

| Rank | Delta | Target | Uncertainty | Info gain | Feasibility | Rationale | Blocked by |
|------|-------|--------|-------------|-----------|-------------|-----------|------------|
| 1 | Test combined effect: nearly-sorted + high-duplicate data. If speedups compound (>4x), it would explain why Timsort dominates on real-world benchmarks. | #5 | high | high | high | Direct test of the new compound-effects belief with a clear discriminating outcome either way | — |
| 2 | Profile Timsort's internal merge operations with duplicates — count galloping steps vs element-by-element merges to confirm the mechanism. | #4 | high | high | med | Best direct mechanism test for the new size-scaling duplicate hypothesis | — |
| 3 | Isolate alloc cost by pre-allocating output buffer | #2 | high | med | med | R002 remained noisy; this removes the suspected dominant cost directly | — |
| 4 | Test with string arrays instead of floats — string comparison is more expensive, so algorithmic savings should be more visible. | #3 | low | med | high | Extends a now-supported belief to a more comparison-heavy datatype and checks practical scope | — |

## Policy

### Interrupt boundaries
- `BUDGET`: 2 hours cumulative
- `NULL_STREAK`: 3 consecutive null-signal runs
- `BLOCKER`: worker returns BLOCKER
- `AMBIGUITY`: frontier empty AND regeneration fails
- `IRREVERSIBLE`: irreversible action needs human approval

### Scoring
- Signal: `discriminating` (clearly moved a belief) | `partial` (some evidence) | `null` (no info)
- Verdict: `supports` | `contradicts` | `unclear` | `BLOCKER`

### Constraints
- One major delta per run
- Worker must not modify STATE.md or choose directions

## Scratch
- R002 had high variance in alloc measurements — might need to pin CPU frequency or use median of 50+ trials
