# PLAN — R003

## Question and finish line

- **research goal:** Test whether duplicate structure materially changes Python sorting performance.
- **hypothesis:** #3 — duplicate-heavy distributions reduce Python sorting time.
- **primary question:** How does duplicate ratio affect Python sorting across practical input sizes?
- **support / contradict:** At 1M/95%, speedup >1.2× supports; all duplicate arms <1.05× contradict; otherwise cannot decide.
- **minimum complete evidence:** 0%, 50%, 80%, and 95% duplicates across 1K–1M, three repetitions, plus `list.sort()` control.
- **answer produced:** Whether the effect is material and consistent across the tested size/ratio range.
- **ETA to answer:** 8 minutes.

## Evidence package

- **main comparison:** `sorted()` at four sizes and four duplicate ratios.
- **repetitions / coverage:** Three `timeit` repetitions for all 16 conditions.
- **required controls or ablations:** Repeat the same grid with `list.sort()` to check implementation consistency.
- **first command:** `python RUNS/R003/scripts/benchmark_duplicates.py`
- **outputs:** `tests/worker_execution/artifacts/r003_metrics.csv`, optional one plot, `tests/worker_execution/output_REPORT.md`
- **technical lookup:** None.

## Method and resources

- **approach / data:** Seed 42 random floats; replace selected positions with `42.0`; only duplicate ratio varies.
- **metric:** Min/median/max time, max/min spread, and baseline-median/condition-median speedup.
- **execution:** direct
- **paths:** Generate arrays inline; `REPORTS/R001.md`; `REPORTS/R002.md`.
- **compute:** CPU-only; GPU count N/A.
- **parallel strategy:** One timing process so concurrent CPU work does not bias the runtime comparison.
- **utilization plan:** Keep each timed condition isolated and run the grid sequentially.
- **launch:** Use the first command.
- **expected wall-clock:** 8 minutes to the complete comparison.

## Prediction

- **expected:** About 2× speedup at 1M/95%.
- **surprising:** Less than 1.05× across duplicate conditions would contradict the hypothesis.

## Bounds

- **time budget:** 15 minutes.
- **finish:** Complete the evidence package; report once it supports, contradicts, or cannot decide the claim.
- **stop:** One condition exceeds 5 minutes, measurement is invalid, or budget expires.
- **adapt freely:** Change commands, paths, batching, compute, and intermediate analysis without approval.
- **integrity:** Preserve outcomes and mark outcome-driven scientific changes exploratory.

## Working notes

None.

## Meta

- **run_id:** R003
- **created:** 2026-02-23
- **status:** working
