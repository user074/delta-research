# PLAN — (run ID)

> This is a short editable guide for one coherent experiment, not an approval contract. Spend at most 5 minutes
> normally and never more than 10 minutes planning. Keep it under 400 words excluding commands and scheduler text.
> Start once the question, complete evidence package, first command, and real bounds are clear.

## Question and finish line

- **research goal:** (how this run helps answer the human's question)
- **hypothesis:** (#N and the exact claim)
- **primary question:** (single question this run will answer)
- **support / contradict:** (numeric or observable fork)
- **minimum complete evidence:** (smallest sample, repetitions, comparison, and essential control/ablation needed)
- **answer produced:** (what decision becomes possible after the complete package)
- **ETA to answer:** (setup + queue + execution + analysis)

## Evidence package

<!-- Everything needed for one credible conclusion shares this R###. Do not split the baseline, treatment, seeds,
     metrics, controls, ablations, smoke test, retry, plot, or analysis into separate runs. Do not pad the package
     after the stated claim is answered. -->
- **main comparison:** (treatment vs baseline)
- **repetitions / coverage:** (minimum needed)
- **required controls or ablations:** (only those needed to interpret the claim; otherwise None)
- **first command:** `(shortest command that begins the package)`
- **outputs:** (`RUNS/(run ID)/metrics/...`, `RUNS/(run ID)/artifacts/...`, `REPORTS/(run ID).md`)
- **technical lookup:** (one implementation/API/safety question with a time limit, or None; never scientific literature)

## Method and resources

- **approach / data:** (intervention, dataset/split/sample, what stays fixed)
- **metric:** (primary metric and aggregation)
- **execution:** (direct | slurm)
- **paths:** (exact checkpoint/dataset/prior-artifact paths, or None)
- **compute:** (exact human-confirmed GPU count, or CPU-only; include GPU model and precision)
- **parallel strategy:** (DDP by default when one replica fits; otherwise state the exact reason for FSDP/tensor/model sharding or condition-level parallelism)
- **utilization plan:** (useful work assigned to every confirmed GPU; per-device/global batch or condition placement)
- **launch:** (exact command; for N-GPU DDP use `torchrun --nproc_per_node=N`; for SLURM include partition, walltime, memory, and GPUs)
- **expected wall-clock:** (launch-to-complete-evidence estimate; optimize this rather than GPU-hours)

## Prediction

- **expected:** (one sentence with the expected result)
- **surprising:** (one result that would materially change the hypothesis)

## Bounds

- **time budget:** (minutes)
- **finish:** (complete the evidence package; report once it supports, contradicts, or cannot decide the claim)
- **stop:** (only budget, safety, irreversible action, unavailable resource, or invalid measurement)
- **adapt freely:** Change commands, paths, batching, compute, and intermediate analysis without approval.
- **integrity:** Do not erase outcomes or present an outcome-driven scientific change as if it was chosen earlier.

<!-- Optional only for a named failure that could waste a costly experiment. It uses at most 10% of the budget and
     flows directly into the evidence package. It never completes the run. -->
## Smoke test (optional)

- **risk tested:** (specific failure risk, or delete this section)
- **command:** (smallest probe)
- **continue when:** (one observable condition)

## Working notes

<!-- Keep None unless the scientific comparison or interpretation changes. Mechanical fixes need no entry. -->

None.

## Meta

- **run_id:** (R###)
- **created:** (date)
- **status:** working
