# PLAN — R007

## Delta
- **what**: Fine-tune Llama-3-8B on instruction-tuning dataset with LoRA rank 16 vs rank 64 to measure accuracy-efficiency tradeoff
- **intent**: Determine whether rank 64 provides meaningful quality improvement over rank 16, or whether rank 16 is sufficient
- **target belief**: #3 — "LoRA rank 16 is sufficient for instruction-following quality on this dataset"
- **type**: experiment

## Resources
- **checkpoint**: /scratch/researcher/checkpoints/llama-3-8b-base
- **dataset**: /data/nlp/instruction-tuning/alpaca_cleaned.json
- **prior artifacts**: RUNS/R006/artifacts/lora_r16_results.json
- **output dir**: RUNS/R007/artifacts/
- **precision**: BF16
- **parallelism**: DDP, 4 GPUs
- **launch**: `torchrun --nproc_per_node=4`
- **scratch path**: /scratch/researcher/
- **execution mode**: slurm

## SLURM
- **walltime**: 04:00:00
- **gpus**: 4
- **memory**: 128G
- **partition**: gpu

## Commands

### Step 1: Prepare data splits
Load alpaca_cleaned.json, split 90/10 train/eval. Tokenize with Llama-3 tokenizer, max_length=2048. Save processed dataset to scratch.

### Step 2: Train LoRA rank 64
Fine-tune llama-3-8b-base with LoRA rank=64, alpha=128, lr=2e-4, batch_size=8, 3 epochs. Use BF16, DDP across 4 GPUs. Save checkpoint and training logs.

### Step 3: Evaluate both ranks
Run evaluation on eval split for both rank 16 (from R006) and rank 64 checkpoints. Compute: loss, perplexity, ROUGE-L on held-out instructions.

### Step 4: Compare and analyze
Generate comparison plots: training curves, eval metrics side-by-side. Compute efficiency metrics (time, VRAM, throughput) for both ranks. Determine if rank 64 quality justifies 4x parameter increase.

### Final step: Write report
Write report to REPORTS/R007.md following the report template.
Include all data inline, generate visualizations, embed plots with ![](path).

## Success metrics
| Metric | Baseline | Target | How to measure |
|--------|----------|--------|----------------|
| eval_loss | 1.82 (R006 rank 16) | < 1.75 to support rank 64 | cross-entropy on eval split |
| ROUGE-L | 0.42 (R006 rank 16) | > 0.46 to support rank 64 | ROUGE-L on instruction responses |
| throughput | 1850 tok/s (R006) | within 20% | tokens per second during training |

## Stop conditions
- BLOCKER if: checkpoint /scratch/researcher/checkpoints/llama-3-8b-base not found
- BLOCKER if: GPU OOM with batch_size=8 (try reducing to 4 before reporting)
- TIMEOUT after: 240 minutes

## Context

**Relevant beliefs:**
- Belief #3 (confidence 0.5): "LoRA rank 16 is sufficient for instruction-following quality" — R006 showed rank 16 achieves eval_loss=1.82, ROUGE-L=0.42
- Belief #1 (confidence 0.7): "Instruction-tuning improves base model performance" — supported by R003-R005

**Prior findings:**
- R006: LoRA rank 16 trained in 47 min on 4x A100, peak VRAM 62GB/GPU, eval_loss=1.82, ROUGE-L=0.42
- R005: Full fine-tune achieves eval_loss=1.65 but requires FSDP and 3x training time

## Meta
- **run_id**: R007
- **created**: 2026-04-12
- **time_budget**: 240 minutes
- **status**: planned
