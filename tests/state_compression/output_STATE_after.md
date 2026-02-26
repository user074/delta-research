# STATE — sorting-perf

## Meta
- **project**: sorting-perf
- **goal**: Understand which factors most affect Python sorting performance on real-world data distributions
- **started**: 2026-02-20
- **last_updated**: 2026-02-23
- **total_runs**: 3
- **status**: active

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

| # | Belief | Status | Confidence | Key evidence | Last updated |
|---|--------|--------|------------|--------------|--------------|
| 1 | Timsort's advantage over quicksort grows with nearly-sorted data | active | 0.7 | R001: 3.2x faster on 90%-sorted arrays (1M elements) | 2026-02-21 |
| 2 | Memory allocation is the dominant cost for large arrays (>1M), not comparisons | active | 0.5 | R002: inconclusive — alloc time noisy | 2026-02-22 |
| 3 | Duplicate-heavy distributions reduce sorting time due to equal-element optimizations | supported | 0.82 | R003: discriminating support; 95% duplicates gives 1.8x (1M) to 2.1x (5M); Timsort-specific via heapq confound check | 2026-02-23 |
| 4 | Timsort duplicate-related speedup increases with array size due to galloping/merge behavior (possibly super-linear) | active | 0.5 | R003 new hypothesis: speedup rises from 1.5x (1K) to 2.1x (5M) | 2026-02-23 |
| 5 | Nearly-sortedness and high-duplicate structure compound to produce larger-than-single-factor speedups | active | 0.5 | R003 new hypothesis from combined-properties question | 2026-02-23 |
| 6 | Duplicate-driven sorting speedups are larger for strings than floats due to higher comparison cost | active | 0.5 | R003 suggested follow-up: validate effect on string arrays | 2026-02-23 |

## Ledger

| Run | Delta | Signal | Verdict | Belief | Link |
|-----|-------|--------|---------|--------|------|
| R001 | Compare timsort vs quicksort on nearly-sorted 1M arrays | discriminating | supports | #1 | [R001](REPORTS/R001.md) |
| R002 | Profile memory allocation vs comparison time on random 5M arrays | partial | unclear | #2 | [R002](REPORTS/R002.md) |
| R003 | Benchmark sorting on arrays with 0%, 50%, 80%, and 95% duplicate ratios across sizes 1K-5M | discriminating | supports | #3 | [R003](REPORTS/R003.md) |

## Frontier

| Rank | Delta | Target | Rationale | Blocked by |
|------|-------|--------|-----------|------------|
| 1 | Isolate alloc cost by pre-allocating output buffer and rerun 1M/5M profiling with 50+ trials | #2 | Belief #2 remains maximally uncertain (0.5); directly addresses R002 noise | — |
| 2 | Test combined effect: nearly-sorted + high-duplicate data across 100K-5M; compare against single-factor baselines | #5 | Directly tests whether speedups compound beyond additive expectations | — |
| 3 | Instrument Timsort internals (or proxy counters) to quantify galloping/merge behavior vs duplicate ratio and size | #4 | Mechanism-focused discrimination for size-scaling hypothesis | — |
| 4 | Replicate duplicate-ratio benchmark on string arrays and compare effect sizes vs float arrays | #6 | Tests whether higher comparison cost amplifies duplicate-related gains | — |

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
- R003 indicates strong duplicate effect in Timsort (up to 2.1x at 5M, 95% duplicates); mechanism follow-up now warranted
