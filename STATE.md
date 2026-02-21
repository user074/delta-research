# STATE — Delta Research

## Meta
- **project**: Delta Research
- **goal**: Investigate structured research loops for iterative hypothesis testing
- **started**: 2026-02-21
- **last_updated**: 2026-02-21
- **total_runs**: 0
- **status**: active

---

## BeliefState
<!-- Each belief is supported, rejected, or conflicting. Confidence is evidence-weighted. -->
<!-- Update after every run. Promote at ≥0.8, demote at ≤0.2, mark conflicting if evidence splits. -->

| # | Belief | Status | Confidence | Key evidence | Last updated |
|---|--------|--------|------------|--------------|--------------|
| 1 | _seed belief — edit this_ | supported | 0.5 | — (seed) | 2026-02-21 |

## Ledger
<!-- Append-only. One row per completed run. This is the canonical history. -->

| Run | Delta | Metric | Signal | Verdict | Link |
|-----|-------|--------|--------|---------|------|

## Frontier
<!-- Ranked next deltas. Each says what it disambiguates and its cost/risk. -->
<!-- Supervisor picks top non-blocked entry. Regenerate when empty. -->

| Rank | Delta | Disambiguates | Cost | Risk | Blocked by |
|------|-------|---------------|------|------|------------|
| 1 | _first experiment — edit this_ | _what question this answers_ | low | low | — |

## Policy
<!-- Meta-rules governing the loop. Update when patterns emerge. -->

### Interrupt boundaries (stop loop when)
- `BUDGET`: cumulative wall-clock exceeds 60min
- `NULL_STREAK`: 3 consecutive signal < 0.2 runs
- `BLOCKER`: worker returns verdict = BLOCKER
- `AMBIGUITY`: frontier is empty AND regeneration fails
- `IRREVERSIBLE`: next delta requires irreversible action (human approval needed)

### Scoring
- Signal score: 0.0 = no information gained, 1.0 = maximally informative
- Verdict options: `supports` | `contradicts` | `unclear` | `BLOCKER`
- Belief promotion threshold: 0.8
- Belief demotion threshold: 0.2

### Run constraints
- One major delta per run (clean credit assignment)
- Default time budget per run: 10 min
- Worker must not modify STATE.md or choose new directions

### Template stats
<!-- Track what kinds of deltas produce signal. Updated by supervisor. -->

| Delta type | Runs | Avg signal | Notes |
|------------|------|------------|-------|
| — | 0 | — | no data yet |

## Scratch
<!-- Free-form. Open questions, hunches, things to remember between cycles. -->

