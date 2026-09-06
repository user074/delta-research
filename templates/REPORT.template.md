# REPORT — (run ID): (plain-English question)

> A run is one coherent attempt to answer one hypothesis. Write this like a compact research paper, not an activity
> log. Setup, smoke tests, retries, seeds, individual conditions, plots, and ablations are parts of this run—not
> separate runs. Keep the main answer and all decision-relevant numbers inline.

## Answer

<!-- At most 80 words. First sentence says the result supports, contradicts, or cannot yet decide the hypothesis in
     the tested scope. Give the decisive number, what it means, and at most one limitation. Use plain English and
     no internal loop vocabulary. -->

## Motivation

<!-- Why does this question matter to the research goal? State the hypothesis and what was uncertain before. -->

## Questions tested

<!-- One primary question. Add a secondary question only when it is required to interpret the primary result. -->
1. **Primary:** (question with the support/contradict threshold)
2. **Secondary, if needed:** (necessary mechanism, robustness, or alternative-explanation question; otherwise omit)

## Method

- **approach:** (intervention and what stayed fixed)
- **data:** (dataset, split, sample size, generation, seed policy)
- **comparisons:** (treatment, baseline, and only necessary controls)
- **metrics:** (primary metric and decision threshold)
- **repetitions:** (number and aggregation)
- **environment:** (model/checkpoint, software, hardware)
- **parallel execution:** (confirmed GPU count, DDP/other layout, per-device/global batch or condition placement; if not DDP on multiple GPUs, give the exact reason)
- **scientific changes during execution:** (only changes that affect interpretation; otherwise None)

## Experiments

<!-- List the coherent evidence package. The main comparison, repetitions, required controls, and any
     verdict-changing ablations stay in this R###. Do not list setup or debugging as experiments. -->
| Experiment | Why it is needed | Comparison / conditions |
|------------|------------------|-------------------------|
| Main test | Directly answers the primary question | (baseline vs treatment) |
| (control or ablation, if needed) | (alternative it rules out) | (conditions) |

## Results

<!-- Put every number needed to judge the answer inline. Use one compact table where possible. A plot is optional
     and limited to one only when it communicates the result better than the table. -->
| Experiment / condition | Primary result | Uncertainty / repetitions | Meaning |
|------------------------|----------------|---------------------------|---------|
| (condition) | (number) | (spread / N) | (supports, contradicts, or inconclusive) |

- **wall-clock to answer:** (elapsed setup/queue/execution/analysis when available; always include launch-to-results time)
- **GPU use, if applicable:** (N/N confirmed GPUs did useful work; per-rank samples/batches and throughput, plus peak memory or sampled utilization when already collected)

## Analysis

<!-- Answer each question directly. Explain why the comparison supports the conclusion, what necessary controls or
     ablations showed, and any surprising result. Do not add a literature review or process narration. -->

## Ablations (optional)

<!-- Include only when an ablation was necessary to decide the claim or rule out an explanation that could reverse
     it. Keep all related ablations in this run. Delete this section when none was needed. -->

## Limitations and tested scope

<!-- Exact model/data/runtime/hardware scope, plus only a limitation or alternative explanation that could reverse
     the conclusion. Write "No material limitation identified within the tested scope" when appropriate. -->

## Conclusion

- **answer:** (supports | contradicts | cannot decide) hypothesis/belief #N
- **decisive evidence:** (one sentence with exact result)
- **confidence:** (before → proposed after, with a short reason)
- **next experiment:** (None if decided; otherwise at most one experiment needed to answer the same unresolved
  question—not a new research direction)

## Reproducibility

- **command:** `(exact main command or job ID)`
- **parallelism:** (launcher, world size, and global/per-device batch or condition-to-GPU assignment)
- **metrics:** `../RUNS/(run ID)/metrics/(file)`
- **artifacts:** `../RUNS/(run ID)/artifacts/(file)` (only useful artifacts)

## Meta

- **run_id**: (R###)
- **started**: (timestamp)
- **completed**: (timestamp)
- **execution**: (direct | slurm)
- **attempts**: (attempt IDs, job/process IDs and status/evidence paths, including failed attempts)
- **worker model / effort**: (effective values)
- **model usage**: (input/cached/output tokens when exposed, including retries; unavailable otherwise)
- **slurm_job_id**: (job ID, if applicable)
- **wandb_run**: (URL, if applicable)
