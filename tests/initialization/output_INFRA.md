# INFRA — llm-finetune

> Hardware profile, optimization playbook, and storage topology.
> Auto-generated during init (local) or filled with human assistance (cluster).
> Workers read this for device placement, precision, and parallelism decisions.
> Re-run environment agent to update after hardware changes.

---

## Compute

### GPUs

| Index | Model | VRAM (GB) | Compute Capability | Driver | CUDA |
|-------|-------|-----------|-------------------|--------|------|
| 0 | NVIDIA A100-SXM4-80GB | 80 | 8.0 | 535.129.03 | 12.2 |
| 1 | NVIDIA A100-SXM4-80GB | 80 | 8.0 | 535.129.03 | 12.2 |
| 2 | NVIDIA A100-SXM4-80GB | 80 | 8.0 | 535.129.03 | 12.2 |
| 3 | NVIDIA A100-SXM4-80GB | 80 | 8.0 | 535.129.03 | 12.2 |

- **total GPU count**: 4
- **human-confirmed GPU count**: 4
- **topology**: NVLink (`NV12` full mesh across all 4 GPUs, CPU affinity `0-63`, NUMA node `0`)
- **CUDA_VISIBLE_DEVICES**: `0,1,2,3`

### CPU
- **model**: AMD EPYC 7742 64-Core Processor
- **cores (physical)**: 64
- **threads**: 128

### Memory
- **RAM**: 503 GiB
- **swap**: 16 GiB

---

## Optimization Playbook

### Precision
- **recommended**: bf16
- **rationale**: A100 GPUs are compute capability 8.0 and have native BF16 support, so BF16 is the right default for fine-tuning and inference without FP16 loss scaling.
- **torch dtype**: `torch.bfloat16`
- **autocast**: `torch.autocast("cuda", dtype=torch.bfloat16)`
- **grad scaler**: not needed for BF16

### Attention
- **mechanism**: SDPA
- **package**: `PyTorch 2.4 native SDPA with Flash/MemEfficient backend auto-selection`
- **usage**: `model = AutoModel.from_pretrained(path, attn_implementation="sdpa", torch_dtype=torch.bfloat16)`
- **notes**: `flash-attn` is not installed, so the current best path is PyTorch 2.4 SDPA. This A100 host supports Flash Attention 2, so installing `flash-attn` is a clear upgrade for transformer training and long-context inference.

### Compilation
- **available**: yes — PyTorch 2.4.0+cu122
- **recommended mode**: `"reduce-overhead"` for fixed-shape training; use `"max-autotune"` for steady-state inference benchmarks after installing `triton`
- **usage**: `model = torch.compile(model, mode="reduce-overhead")`
- **caveats**: The `torch.compile` API is present in PyTorch 2.4, but `triton` is not installed; do not rely on CUDA TorchInductor speedups until Triton is installed and the compiled path is benchmarked. First iteration pays compilation cost, and highly dynamic shapes can trigger graph breaks or recompilation. Disable for debugging with `TORCH_COMPILE_DISABLE=1`.

### Parallelism
- **strategy**: DDP
- **launch command**: `torchrun --nproc_per_node=4 script.py`
- **accelerate config**: Use `accelerate launch --multi_gpu --num_processes=4 script.py` for Hugging Face workflows. If the model does not fit within 80 GB on one GPU, switch to FSDP `FULL_SHARD` or DeepSpeed ZeRO-3.
- **rationale**: This machine has 4 identical A100-80GB GPUs connected by NVLink, so DDP is the fastest default when the model fits on a single GPU. For larger models, keep the same 4-GPU node and move to FSDP or DeepSpeed rather than relying on checkpointing alone.
- **all-GPU work rule**: Launch four DDP ranks and shard training/evaluation samples so every confirmed GPU processes real batches; run independent conditions concurrently only when that shortens wall-clock time without biasing the comparison.
- **tensor parallel fallback**: Forbidden while one BF16 model replica fits in 80 GB; use tensor/model sharding only for a measured single-GPU memory or indivisible-operation constraint.
- **utilization evidence**: Record launch-to-result wall-clock time, aggregate throughput, per-rank sample/batch counts, and peak allocated memory inside the experiment; use sampled GPU utilization when already available, never a separate gate.
- **batch sizing**: In BF16, increase the per-device microbatch during a smoke test until peak allocation remains below about 72 GB (90% of each 80 GB GPU), leaving headroom for activations and allocator fragmentation. Sequence length and optimizer state make a fixed batch number unsafe; use FSDP for full fine-tuning when model plus optimizer state cannot fit on one GPU.
- **gradient accumulation**: Compute `grad_accum_steps = target_effective_batch / (per_device_batch × 4)`. For example, target 256 with `per_device_batch=8` requires `256 / (8 × 4) = 8` accumulation steps.
- **CPU parallelism**: 64 physical cores are available. Use `n_jobs=64` for CPU-bound preprocessing and start DataLoader workers around 16 total, then scale toward 24-32 only if preprocessing is the bottleneck.

### Data Loading
- **num_workers**: 4 per GPU to start (16 total). That is enough to keep 4 A100s busy without immediately oversubscribing the 64-core host.
- **pin_memory**: `True` (always, when using GPU — enables async CPU→GPU transfer)
- **persistent_workers**: `True` (avoids worker respawn overhead between epochs)
- **prefetch_factor**: 4 when reading from `/data` over NFS; reduce to 2 if the dataset is staged onto `/scratch`
- **non_blocking transfers**: "Use `.to(device, non_blocking=True)` with `pin_memory=True` for overlapped data transfer"
- **storage notes**: `/data/nlp/instruction-tuning/` is an NFS4 read-only mount, while `/scratch` is local NVMe. For repeated epochs, shuffle-heavy training, or preprocessing, stage hot shards to `/scratch` to avoid network-storage stalls.

### GPU-CPU Transfer Pitfalls

**Rules for workers:**
1. **Never call `.item()`, `.cpu()`, or `.numpy()` inside a training loop step.** Each call forces GPU→CPU sync and stalls the pipeline. Instead, accumulate loss on GPU and log every N steps:
   ```python
   # BAD — sync every step
   loss_val = loss.item()
   
   # GOOD — sync every N steps
   if step % log_interval == 0:
       loss_val = loss.item()
   ```
2. **Never call `torch.cuda.synchronize()` unless measuring exact wall-clock time.** It blocks until all GPU work completes.
3. **Avoid Python-side conditionals on tensor values** (e.g. `if loss < threshold`). This forces a sync. Move the conditional to GPU or check periodically.
4. **Use `non_blocking=True`** for all `.to(device)` calls on data. Without it, each transfer blocks until complete.
5. **Avoid repeated small allocations on GPU.** Pre-allocate buffers where possible. Frequent alloc/free causes fragmentation and triggers garbage collection.
6. **For metrics/logging**, accumulate on GPU, sync once at log time:
   ```python
   running_loss = torch.zeros(1, device='cuda')
   for step, batch in enumerate(loader):
       loss = model(batch)
       running_loss += loss.detach()
       if step % log_interval == 0:
           avg_loss = (running_loss / log_interval).item()  # single sync
           running_loss.zero_()
   ```

### Training Efficiency
- **fused optimizers**: PyTorch 2.4 reports fused AdamW support, so prefer `torch.optim.AdamW(..., fused=True)`. `apex` is not installed, so do not depend on `FusedAdam`.
- **gradient clipping**: "Use `torch.nn.utils.clip_grad_norm_` — already on GPU, no sync needed"
- **channels last**: Use `model = model.to(memory_format=torch.channels_last)` for CNN or vision workloads on Ampere; this is usually unnecessary for pure transformer fine-tuning.
- **tf32**: Ampere A100 GPUs support TF32. Set `torch.backends.cuda.matmul.allow_tf32 = True` and `torch.backends.cudnn.allow_tf32 = True` for faster FP32 matmuls when exact FP32 is not required.
- **cudnn benchmark**: "Set `torch.backends.cudnn.benchmark = True` for fixed-size inputs (speeds up conv layer autotuning)"
- **empty cache sparingly**: "Avoid `torch.cuda.empty_cache()` in training loops — it forces sync and slows allocation. Use only if OOM during eval/generation."

### Inference Optimization
- **torch.inference_mode**: "Use `with torch.inference_mode():` instead of `torch.no_grad()` — stricter, faster"
- **batched inference**: `vllm 0.5.0` is installed — use it for high-throughput batched LLM generation with continuous batching and PagedAttention
- **tensor parallelism**: Use vLLM with `tensor_parallel_size=4` only when the model or required operation cannot fit on one 80 GB GPU; otherwise shard independent examples across four DDP/multiprocess workers.
- **static KV cache**: For repeated generation, pre-allocate KV cache or use an engine that reuses cache blocks to reduce allocation churn
- **quantization**: `bitsandbytes 0.43.1` is installed, so 4-bit and 8-bit quantization are available for inference when BF16 no longer fits comfortably in 80 GB.

### Installed Accelerators

| Package | Version | Notes |
|---------|---------|-------|
| torch | 2.4.0+cu122 | `torch.compile`, SDPA, and fused AdamW are available; built against CUDA 12.2 |
| flash-attn | not installed | A100 cc 8.0 supports Flash Attention 2, but the package is not present so the stack falls back to SDPA |
| deepspeed | 0.14.0 | ZeRO stage 2/3 and offload support are available for large-model training |
| accelerate | 0.33.0 | Hugging Face multi-GPU launcher for DDP and FSDP workflows |
| apex | not installed | No Apex fused optimizers or fused layer norm |
| bitsandbytes | 0.43.1 | 8-bit and 4-bit quantization for inference or memory-constrained fine-tuning |
| xformers | 0.0.27 | Alternative memory-efficient ops; secondary to PyTorch SDPA on this host |
| triton | not installed | `torch.compile` exists, but standalone `triton` is an optimization gap for TorchInductor-backed compile speedups |
| vllm | 0.5.0 | Fast batched LLM inference with PagedAttention and tensor parallelism |

---

## Storage

### Paths

| Purpose | Path | Speed class | Capacity (free) | Notes |
|---------|------|-------------|-----------------|-------|
| working dir | `/home/researcher/llm-finetune` | fast-local | `1.8T (1.3T free)` | Lives on `/` backed by local NVMe (`/dev/nvme0n1`, ext4) |
| datasets | `/data/nlp/instruction-tuning/` | network | `50T (18T free)` | Shared NFS4 mount on `nas01:/shared`; read-only and higher latency than local NVMe |
| checkpoints | `/scratch/researcher/checkpoints` | fast-local | `3.6T (2.3T free)` | Lives on `/scratch` backed by local NVMe (`/dev/nvme1n1`, ext4); best location for frequent checkpoint writes |
| scratch / temp | `/scratch` | fast-local | `3.6T (2.3T free)` | Local NVMe workspace for temporary artifacts, staged datasets, and intermediate outputs |
| HuggingFace cache | `/scratch/researcher/.cache/huggingface` | fast-local | `3.6T (2.3T free)` | Already on fast local storage; keep `HF_HOME` here to avoid root volume and NFS bottlenecks |

### Guidance
- **fast writes (checkpoints, intermediates)**: `/scratch/researcher/checkpoints` and `/scratch/researcher/`
- **large reads (datasets, model weights)**: `/data/nlp/instruction-tuning/` for the canonical shared dataset; copy hot subsets to `/scratch` when local read speed matters
- **avoid for large files**: `/home/researcher/llm-finetune` and the root filesystem for bulk datasets, checkpoints, or model caches; keep those on `/scratch`
- **HF_HOME**: `export HF_HOME=/scratch/researcher/.cache/huggingface`

---

## Cluster

N/A — local machine. No SLURM, PBS, or LSF scheduler was detected, so the cluster-only subsections are intentionally skipped as directed by the template.

---

## Job Execution

- **mode**: direct
- **project root**: `/home/researcher/llm-finetune`
- **env manager**: conda
- **validated env activation**:
  ```bash
  conda activate llm-ft
  ```
- **wandb mode**: disabled (not configured in the supplied profile)
- **wandb project**: N/A
- **wandb entity**: N/A
- **test job status**: not run
- **test job notes**: Local direct-execution server; a scheduler test job is not applicable. The activation command is the command captured in the supplied profile.

---

## Recommended Optimizations

| # | Optimization | Command | Impact | Status | Notes |
|---|-------------|---------|--------|--------|-------|
| 1 | Install Flash Attention 2 | `pip install flash-attn --no-build-isolation` | high | pending | A100 cc 8.0 supports FA2; current stack falls back to PyTorch 2.4 SDPA |
| 2 | Install Triton | `pip install triton` | medium | pending | PyTorch 2.4 exposes `torch.compile`, but standalone `triton` is not installed for stronger TorchInductor-backed compile speedups |

---

## Profiling Source
- **method**: auto-profiled
- **profiled on**: 2026-08-27
- **host**: not captured in `SYSTEM_PROFILE.md`
- **notes**: Generated from `tests/initialization/SYSTEM_PROFILE.md` for a local server profile. The supplied profiling fixture did not include a hostname field.
