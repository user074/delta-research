# PLAN — R003

## Question and finish line

- **research goal:** Test whether duplicate structure materially changes Python sorting performance.
- **hypothesis:** #3 — duplicate-heavy distributions reduce Python sorting time.
- **primary question:** Does replacing 95% of values with one duplicate speed up `sorted()` at 1M elements?
- **support / contradict:** Speedup >1.2× supports; <1.05× contradicts; otherwise cannot decide.
- **minimum complete evidence:** Matched 0% and 95% duplicate arms, three repetitions each, identical timing code, primary max/min <2×.
- **answer produced:** Whether duplicate ratio materially affects sorting in this tested setup.
- **ETA to answer:** 8 minutes total.

## Evidence package

- **main comparison:** Seeded 1M-float baseline versus 95% positions replaced by `42.0`.
- **repetitions / coverage:** Three randomized-order repetitions per arm.
- **required controls or ablations:** None; the claim is empirical and scoped to `sorted()`.
- **first command:** `cd /home/user/sorting-perf && conda activate sorting-perf && python RUNS/R003/scripts/benchmark_duplicates.py`
- **outputs:** `RUNS/R003/metrics/duplicate_speedup.json`; `REPORTS/R003.md`
- **technical lookup:** None.

## Method and resources

- **approach / data:** NumPy seed 42; matched random-float lists; only duplicate ratio changes.
- **metric:** Baseline median time divided by duplicate-heavy median.
- **execution:** direct
- **paths:** Generate arrays inline; prior context in `REPORTS/R001.md`.
- **compute:** CPU-only on AMD Ryzen 9 5900X; GPU count N/A.
- **parallel strategy:** One timing process so concurrent CPU work does not bias the runtime comparison.
- **utilization plan:** Keep the timed process isolated; CPU utilization is not the scientific objective of this GPU rule.
- **launch:** Use the first command.
- **expected wall-clock:** 8 minutes to the complete comparison.

## Prediction

- **expected:** About 2× speedup.
- **surprising:** Less than 1.05× would contradict hypothesis #3 in this scope.

## Bounds

- **time budget:** 10 minutes.
- **finish:** Complete the evidence package; report once it supports, contradicts, or cannot decide the claim.
- **stop:** Invalid measurement, unavailable resources, or expired budget.
- **adapt freely:** Change commands, paths, batching, compute, and intermediate analysis without approval.
- **integrity:** Preserve raw outcomes and mark outcome-driven scientific changes exploratory.

## Working notes

None.

## Meta

- **run_id:** R003
- **created:** 2026-08-27
- **status:** working
