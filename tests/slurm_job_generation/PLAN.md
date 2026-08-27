# PLAN — R007

## Question and finish line

- **research goal:** Resolve the quality-efficiency choice between LoRA ranks 16 and 64.
- **hypothesis:** #3 — rank 16 is sufficient for instruction-following quality on this dataset.
- **primary question:** Does rank 64 improve quality enough to justify four times as many adapter parameters?
- **support / contradict:** Rank-64 loss <1.75 or ROUGE-L >0.46 contradicts #3; otherwise supports it.
- **minimum complete evidence:** Both ranks on the exact held-out split with the same evaluator, loss, ROUGE-L, throughput, and peak VRAM.
- **answer produced:** Choose rank 16 or 64 for this dataset and training setup.
- **ETA to answer:** 4 hours 15 minutes total: 15-minute expected queue plus at most 4 hours from launch to report; update the queue estimate at submission.

## Evidence package

- **main comparison:** Train rank 64 and compare it with the exact R006 rank-16 checkpoint.
- **repetitions / coverage:** One matched three-epoch training run per rank on the fixed split.
- **required controls or ablations:** Same evaluator and data manifest; no extra ablation needed.
- **first command:** `sbatch /home/researcher/llm-finetune/RUNS/R007/job.sh`
- **outputs:** `RUNS/R007/metrics/`, `RUNS/R007/artifacts/`, `REPORTS/R007.md`
- **technical lookup:** None.

## Method and resources

- **approach / data:** Fixed 90/10 processed Alpaca split; rank 64/alpha 128, 3 epochs, BF16, lr 2e-4, batch 8.
- **metric:** Held-out loss, perplexity, ROUGE-L, throughput, peak VRAM, and training time.
- **execution:** slurm
- **paths:** `/scratch/researcher/checkpoints/llama-3-8b-base`; `/data/nlp/instruction-tuning/alpaca_cleaned.json`; `/scratch/researcher/checkpoints/R006/lora_r16`; `/scratch/researcher/R006/alpaca_processed`; `/home/researcher/llm-finetune/RUNS/R006/artifacts/dataset_manifest.json`; `/home/researcher/llm-finetune/RUNS/R006/artifacts/lora_r16_results.json`
- **compute:** Human-confirmed 4×A100-80GB, BF16.
- **parallel strategy:** Four-rank DDP because one model replica fits in 80 GB; tensor parallelism is not permitted for this run.
- **utilization plan:** Each rank receives training/evaluation batches; per-device batch 8, global batch 32 before accumulation, with per-rank batch counts recorded.
- **launch:** `torchrun --nproc_per_node=4 RUNS/R007/experiment.py`; partition `gpu`; walltime `04:00:00`; memory `128G`; 4 GPUs.
- **expected wall-clock:** At most 4 hours from launch to complete metrics; optimize elapsed time rather than GPU-hours.

## Prediction

- **expected:** Rank 64 reaches loss 1.76 and ROUGE-L 0.45, not enough to justify the larger adapter.
- **surprising:** Crossing neither quality threshold would show rank is not the expected bottleneck.

## Bounds

- **time budget:** 240 minutes.
- **finish:** Complete the evidence package; report once it supports, contradicts, or cannot decide the claim.
- **stop:** Missing exact checkpoint/split/baseline, non-finite loss, exhausted OOM repair, or timeout.
- **adapt freely:** Change scripts, paths, batching, compute, and analysis without approval; use a fresh job after partial-DDP failure.
- **integrity:** Preserve raw outcomes and mark outcome-driven scientific changes exploratory.

## Smoke test (optional)

- **risk tested:** DDP/env/data loading and batch-8 VRAM before the costly main experiment; maximum 15 minutes.
- **command:** Submit the four-GPU smoke job for one forward/backward/optimizer step.
- **continue when:** Every rank has finite loss, peak VRAM ≤72 GB, and projected main time ≤180 minutes.

## Working notes

None.

## Meta

- **run_id:** R007
- **created:** 2026-04-12
- **status:** working
