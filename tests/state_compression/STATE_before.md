# STATE — sorting-perf

## Meta
- **project**: sorting-perf
- **goal**: Understand which factors most affect Python sorting performance on real-world data distributions
- **started**: 2026-02-20
- **last_updated**: 2026-02-22
- **total_runs**: 2
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
| 3 | — | Duplicate-heavy distributions reduce sorting time due to equal-element optimizations | active | 0.45 | seed — untested | 2026-02-20 |

## Ledger

| Run | Delta | Signal | Verdict | Belief | Link |
|-----|-------|--------|---------|--------|------|
| R001 | Compare timsort vs quicksort on nearly-sorted 1M arrays | discriminating | supports | #1 | [R001](REPORTS/R001.md) |
| R002 | Profile memory allocation vs comparison time on random 5M arrays | partial | unclear | #2 | [R002](REPORTS/R002.md) |

## Frontier

| Rank | Delta | Target | Uncertainty | Info gain | Feasibility | Rationale | Blocked by |
|------|-------|--------|-------------|-----------|-------------|-----------|------------|
| 1 | Benchmark sorting on arrays with 50%, 80%, 95% duplicate ratios across sizes 1K-10M | #3 | high | high | high | Direct test of duplicate optimization | — |
| 2 | Isolate alloc cost by pre-allocating output buffer | #2 | high | med | med | R002 noisy — pre-allocation removes alloc entirely | — |

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
