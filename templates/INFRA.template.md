# INFRA — (project name)

> Hardware profile, optimization playbook, and storage topology.
> Auto-generated during init (local) or filled with human assistance (cluster).
> Workers read this for device placement, precision, and parallelism decisions.
> Re-run environment agent to update after hardware changes.

---

## Compute

### GPUs
<!-- One row per GPU. If no GPUs, write "N/A — CPU only" and skip GPU-related playbook sections. -->

| Index | Model | VRAM (GB) | Compute Capability | Driver | CUDA |
|-------|-------|-----------|-------------------|--------|------|
| 0 | (e.g. A100-SXM4-80GB) | 80 | 8.0 | 535.129.03 | 12.2 |

- **total GPU count**: (N)
- **topology**: (NVLink / PCIe — from `nvidia-smi topo -m` if available)
- **CUDA_VISIBLE_DEVICES**: (e.g. `0,1,2,3`)

### CPU
- **model**: (e.g. AMD EPYC 7742)
- **cores (physical)**: (N)
- **threads**: (N)

### Memory
- **RAM**: (e.g. 256 GB)
- **swap**: (e.g. 16 GB)

---

## Optimization Playbook
<!-- Derived from detected hardware during profiling. Workers copy relevant parts into their scripts. -->
<!-- If hardware changes, re-run the environment agent to regenerate this section. -->
<!-- This is a concrete playbook, not generic advice. Every recommendation should be specific to the detected hardware. -->

### Precision
<!-- Based on GPU compute capability:
     cc >= 9.0 (H100, H200, B200)  → BF16 native, FP8 for supported ops
     cc >= 8.0 (A100, L40S)        → BF16 (native, no loss scaling)
     cc 7.0-7.5 (V100, T4)        → FP16 with AMP (loss scaling required)
     cc < 7.0 or no GPU            → FP32 -->
- **recommended**: (bf16 | fp16 | fp32)
- **rationale**: (e.g. "A100 (cc 8.0) has native BF16; avoids FP16 loss scaling overhead")
- **torch dtype**: (e.g. `torch.bfloat16`)
- **autocast**: (e.g. `torch.autocast('cuda', dtype=torch.bfloat16)`)
- **grad scaler**: (e.g. "not needed for BF16" or "required for FP16: `torch.amp.GradScaler()`")

### Attention
<!-- Based on installed packages, GPU architecture, and PyTorch version:
     cc >= 10.0 (B200) + flash-attn >= 4.0    → Flash Attention 4 (Blackwell-native)
     cc >= 9.0 (H100/H200) + flash-attn >= 3.0 → Flash Attention 3 (Hopper-optimized, FP8 support)
     cc >= 8.0 + flash-attn >= 2.0             → Flash Attention 2
     PyTorch >= 2.2                            → SDPA with FlashAttention/MemEfficient backend auto-selection
     PyTorch >= 2.0                            → SDPA (basic)
     Neither                                   → Standard (will be slow for long sequences)
     
     Note: Recent PyTorch versions (2.4+) integrate Flash Attention backends into SDPA,
     but standalone flash-attn often has newer kernels. Check both. -->
- **mechanism**: (Flash Attention 4 | Flash Attention 3 | Flash Attention 2 | SDPA | standard)
- **package**: (e.g. "flash-attn 3.1.0" or "PyTorch 2.4 native SDPA with Flash backend")
- **usage**: (e.g. `model = AutoModel.from_pretrained(path, attn_implementation="flash_attention_2")`)
- **notes**: (e.g. "FA3 on H100 supports FP8 attention for additional speedup on long sequences")

### Compilation
<!-- Based on PyTorch version and GPU architecture:
     PyTorch >= 2.0    → torch.compile available
     cc >= 8.0 + triton installed → torch.compile with inductor backend (best performance)
     cc >= 9.0 (H100)  → torch.compile benefits are largest (Triton kernels optimized for Hopper)

     torch.compile modes:
       "default"       — safe, moderate speedup
       "reduce-overhead" — uses CUDA graphs, best for fixed-shape inputs (training loops)
       "max-autotune"  — tries many kernel variants, slow first run but fastest steady-state -->
- **available**: (yes — PyTorch X.Y | no)
- **recommended mode**: (e.g. `"reduce-overhead"` for training, `"max-autotune"` for inference benchmarks)
- **usage**: `model = torch.compile(model, mode="reduce-overhead")`
- **caveats**: (e.g. "First iteration is slow (compilation). Use `torch._dynamo.config.cache_size_limit` if many dynamic shapes. Disable for debugging: `TORCH_COMPILE_DISABLE=1`")

### Parallelism
<!-- Based on GPU count, topology, and model size:
     0 GPUs             → CPU multiprocessing
     1 GPU              → single GPU, no parallelism overhead
     2-8 same node, model fits 1 GPU   → DDP with torchrun
     2-8 same node, model > 1 GPU VRAM → FSDP (ZeRO Stage 3) or DeepSpeed ZeRO
     Multi-node         → FSDP or DeepSpeed with NCCL backend

     Sharding strategy for multi-GPU when model fits in 1 GPU:
       DDP — replicate model on each GPU, sync gradients. Fastest when model fits.
     When model doesn't fit in 1 GPU:
       FSDP SHARD_GRAD_OP (≈ ZeRO-2) — shard optimizer states + gradients. Model stays replicated.
       FSDP FULL_SHARD (≈ ZeRO-3) — shard everything. Lowest memory, higher communication.
       Prefer FSDP over gradient checkpointing when you have multiple GPUs — FSDP distributes
       memory across GPUs while gradient checkpointing trades compute for memory on a single GPU.
       Use both together only when model is very large relative to total VRAM. -->
- **strategy**: (single-GPU | DDP | FSDP SHARD_GRAD_OP | FSDP FULL_SHARD | DeepSpeed ZeRO-2 | DeepSpeed ZeRO-3 | CPU-only)
- **launch command**: (e.g. `torchrun --nproc_per_node=4 script.py`)
- **accelerate config**: (e.g. "Use `accelerate launch --multi_gpu --num_processes=4` if using HuggingFace Accelerate")
- **rationale**: (e.g. "4 GPUs with NVLink — DDP is fastest; switch to FSDP FULL_SHARD if model exceeds single-GPU VRAM")
- **batch sizing**: (e.g. "80GB A100 at BF16: ~32 per-device batch for 7B model. Effective batch = per_device × n_gpus × grad_accum_steps.")
- **gradient accumulation**: (e.g. "If target effective batch is 256 and per_device_batch=32 on 4 GPUs: grad_accum_steps = 256 / (32 × 4) = 2")
- **CPU parallelism**: (e.g. "64 cores — use `n_jobs=64` for joblib, `num_workers=8` for DataLoader")

### Data Loading
<!-- These settings have outsized impact on GPU utilization. A poorly configured DataLoader
     can leave GPUs idle 30-50% of the time waiting for data. -->
- **num_workers**: (e.g. "4 per GPU — total 16 for 4 GPUs. Too many causes CPU contention; too few starves GPUs.")
- **pin_memory**: `True` (always, when using GPU — enables async CPU→GPU transfer)
- **persistent_workers**: `True` (avoids worker respawn overhead between epochs)
- **prefetch_factor**: (e.g. "2-4 — preloads this many batches per worker. Increase if IO is the bottleneck.")
- **non_blocking transfers**: "Use `.to(device, non_blocking=True)` with `pin_memory=True` for overlapped data transfer"
- **storage notes**: (e.g. "Dataset on NFS — consider copying to local scratch before training, or use larger prefetch_factor to hide latency")

### GPU-CPU Transfer Pitfalls
<!-- These are the most common silent performance killers. Agents consistently write code
     that triggers unnecessary GPU↔CPU synchronization. -->

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
<!-- Additional optimizations that compound with the above. -->
- **fused optimizers**: (e.g. "apex FusedAdam available — 5-10% faster than torch.optim.Adam" or "Use `torch.optim.AdamW(fused=True)` on PyTorch 2.0+")
- **gradient clipping**: "Use `torch.nn.utils.clip_grad_norm_` — already on GPU, no sync needed"
- **channels last**: (e.g. "Use `model = model.to(memory_format=torch.channels_last)` for CNN workloads on Ampere+ — enables tensor core acceleration for conv ops")
- **tf32**: (e.g. "Ampere+ GPUs: `torch.backends.cuda.matmul.allow_tf32 = True` and `torch.backends.cudnn.allow_tf32 = True` for faster FP32 matmuls with minimal precision loss")
- **cudnn benchmark**: "Set `torch.backends.cudnn.benchmark = True` for fixed-size inputs (speeds up conv layer autotuning)"
- **empty cache sparingly**: "Avoid `torch.cuda.empty_cache()` in training loops — it forces sync and slows allocation. Use only if OOM during eval/generation."

### Inference Optimization
<!-- For evaluation, benchmarking, and generation workloads. -->
- **torch.inference_mode**: "Use `with torch.inference_mode():` instead of `torch.no_grad()` — stricter, faster"
- **batched inference**: (e.g. "vLLM installed — use for batched LLM generation with continuous batching and PagedAttention")
- **tensor parallelism**: (e.g. "For models that don't fit on 1 GPU during inference: vLLM `tensor_parallel_size=4`")
- **static KV cache**: (e.g. "For repeated generation: pre-allocate KV cache to avoid reallocation")
- **quantization**: (e.g. "bitsandbytes installed — 4-bit/8-bit quantization available for fitting larger models in VRAM. Use for inference; avoid for training unless necessary.")

### Installed Accelerators
<!-- Packages that enable hardware-specific optimizations. -->

| Package | Version | Notes |
|---------|---------|-------|
| torch | (version) | (e.g. "2.4.0 — SDPA with FA backend, torch.compile stable") |
| flash-attn | (version or "not installed") | (e.g. "v2.5 — supports Ampere+; v3.x for Hopper") |
| deepspeed | (version or "not installed") | (e.g. "ZeRO stage 2/3, offloading") |
| accelerate | (version or "not installed") | (e.g. "HF Accelerate — simplified multi-GPU launch") |
| apex | (version or "not installed") | (e.g. "fused optimizers, fused layer norm") |
| bitsandbytes | (version or "not installed") | (e.g. "8-bit/4-bit quantization") |
| xformers | (version or "not installed") | |
| triton | (version or "not installed") | (e.g. "required for torch.compile inductor backend") |
| vllm | (version or "not installed") | (e.g. "fast batched inference with PagedAttention") |

---

## Storage

### Paths
<!-- Speed class: fast-local (NVMe/SSD), slow-local (HDD), network (NFS/GPFS/Lustre), cloud (S3/GCS). -->
<!-- Fill capacity from `df -h`. Detect NFS via `df -T` or `mount`. Detect SSD vs HDD via `lsblk -d -o NAME,ROTA`. -->

| Purpose | Path | Speed class | Capacity (free) | Notes |
|---------|------|-------------|-----------------|-------|
| working dir | (path) | (speed class) | (free space) | |
| datasets | (path) | (speed class) | (free space) | (e.g. "shared NFS, read-only") |
| checkpoints | (path) | (speed class) | (free space) | (e.g. "local NVMe, not backed up") |
| scratch / temp | (path) | (speed class) | (free space) | (e.g. "purged after 30 days") |
| HuggingFace cache | (path) | (speed class) | | (set HF_HOME to avoid ~/.cache) |

### Guidance
<!-- Derived from the paths table. Workers follow this for file placement. -->
- **fast writes (checkpoints, intermediates)**: (path — e.g. /scratch/user/)
- **large reads (datasets, model weights)**: (path — e.g. /data/shared/)
- **avoid for large files**: (paths — e.g. "/home — NFS, small quota, backed up")
- **HF_HOME**: (e.g. `export HF_HOME=/scratch/user/.cache/huggingface`)

---

## Cluster
<!-- Fill this section only for SLURM/PBS/LSF managed clusters. -->
<!-- For local machines, write "N/A — local machine" and skip. -->

### Connection
- **scheduler**: (SLURM | PBS | LSF | N/A — local machine)
- **login host**: (e.g. `login.cluster.edu`)
- **cluster docs**: (URL — paste any wiki/handbook the user provides, or "none")

### Partitions
<!-- One row per partition the user has access to. Probe via `sinfo -o "%P %a %l %D %G"`.
     Capture multiple partitions when they exist — debug/short partitions usually have
     much shorter queue times than the default GPU partition. -->

| Partition | Account | QOS | Max walltime | GPUs/job | Typical use |
|-----------|---------|-----|--------------|----------|-------------|
| (e.g. gpu) | (mylab) | (normal) | (48:00:00) | (8) | (default for runs >1h) |
| (e.g. gpu-debug) | (mylab) | (debug) | (1:00:00) | (2) | (quick tests, fast queue) |

- **default partition**: (which one to use for typical runs)
- **fast-queue partition**: (which one to use for short tests when queue is busy)
- **available accounts**: (from `sacctmgr show user $USER` — e.g. `mylab,gpu-allocation`)

### Modules & Env
- **available CUDA modules**: (from `module avail cuda` — e.g. `cuda/12.1, cuda/12.2, cuda/12.4`)
- **standard module loads**: (e.g. `module load cuda/12.2 anaconda3`)
- **conda env path**: (absolute, accessible from compute — e.g. `/opt/conda/envs/llm-ft`. The compute nodes mount the same filesystem, so installing on the login node is enough.)

### Storage Policy
<!-- CRITICAL: clusters have multiple filesystems with different rules. The agent cannot
     auto-detect which path is "approved" for which use — ask the user. Common pattern:
     home is small/backed-up (NOT for large files), Lustre/GPFS for bulk data, scratch for temp. -->

- **home directory**: (e.g. `/mnt/home/$USER` — small quota, backed up, NOT for large files)
- **large data / datasets**: (e.g. `/mnt/lustre/datasets/` — bulk parallel storage, no backup)
- **checkpoints / model outputs**: (e.g. `/mnt/lustre/$USER/checkpoints/` — fast writes, no quota)
- **scratch / temp**: (e.g. `/scratch/$USER/` — node-local SSD, may be purged after job)
- **HuggingFace cache**: (e.g. `/mnt/lustre/$USER/.cache/huggingface` — set `HF_HOME` to avoid filling home)
- **shared group storage**: (e.g. `/mnt/lustre/labshared/` — group-readable, ask before writing)

### Quotas
- **home**: (e.g. `50 GB used / 100 GB limit` — from `quota -s`)
- **other**: (e.g. `lustre: no quota`, `scratch: 5 TB`, file-count limits if any)

### Conventions
<!-- Lab/group/cluster conventions that aren't discoverable from commands. Ask the user. -->

- **walltime convention**: (e.g. "request the minimum needed — short jobs get higher priority")
- **GPU request convention**: (e.g. "request 1 GPU unless training needs more — queue time grows with count")
- **fairshare considerations**: (e.g. "lab share is shared with 5 others — long jobs reduce others' priority")
- **forbidden actions**: (e.g. "do not run GPU work on login node, do not write >1GB to home")
- **other**: (anything else the user mentioned — local quirks, lab rules, on-call)

### Submission Template
<!-- Use the partition + storage policy above. All paths absolute. -->

```bash
#!/bin/bash
#SBATCH --job-name=(name)
#SBATCH --partition=(partition)
#SBATCH --account=(account)
#SBATCH --nodes=1
#SBATCH --gpus-per-node=(N)
#SBATCH --cpus-per-task=(N)
#SBATCH --mem=(N)G
#SBATCH --time=(walltime)
#SBATCH --output=(project_root)/RUNS/(run_id)/slurm-%j.out

# Anchor to project root — all relative paths resolve from here
cd (project_root)

(module loads)
(conda/venv activation)

# wandb configuration (if enabled)
export WANDB_PROJECT=(project)
export WANDB_MODE=(online | offline)
export WANDB_RUN_NAME=(run_id)
export WANDB_DIR=(project_root)/RUNS/(run_id)/wandb

(launch command)
```

---

## Job Execution
<!-- Filled during init. Determines how workers run experiments. -->
<!-- mode=direct: worker executes commands directly (local server). -->
<!-- mode=slurm: worker generates experiment.py + job.sh, submits via sbatch. -->

- **mode**: (direct | slurm)
- **project root**: (absolute path to project root, accessible from compute nodes — e.g. `/mnt/shared/user/my-project`)
  <!-- All relative paths in job scripts (RUNS/, REPORTS/, scripts/) are resolved against this. -->
  <!-- Must be on a filesystem mounted on both login and compute nodes. -->
  <!-- Validated by the SLURM test job during init. -->
- **validated env activation**:
  <!-- Exact commands proven to work on compute nodes. -->
  <!-- For SLURM: must use absolute conda path, correct module loads. -->
  <!-- Validated by the SLURM test job during init. -->
  ```bash
  (e.g. module load cuda/12.2 anaconda3)
  (e.g. /opt/conda/bin/conda activate llm-ft)
  ```
- **wandb mode**: (online | offline | disabled)
- **wandb project**: (project name, or N/A)
- **wandb entity**: (entity/team, or N/A)
- **test job status**: (passed | failed | not run)
- **test job notes**: (e.g. "compute nodes have no internet — using WANDB_MODE=offline")

---

## Recommended Optimizations
<!-- After profiling, the environment agent identifies gaps between what's installed and what
     the hardware supports. Each item is actionable — a command to run, not just advice.
     
     Status: pending → applied (after execution) or skipped (user declined).
     Impact: high / medium / low — how much performance improvement to expect.
     
     The agent presents these to the human, asks for permission, then executes and updates
     both this section (status) and the Playbook (now reflects the new capability). -->

| # | Optimization | Command | Impact | Status | Notes |
|---|-------------|---------|--------|--------|-------|
<!-- Examples of what the agent might detect and suggest:

  GPU supports FA but flash-attn not installed:
  | 1 | Install Flash Attention 2 | `pip install flash-attn --no-build-isolation` | high | pending | cc 8.0 supports FA2; currently falling back to SDPA |

  torch.compile available but triton missing:
  | 2 | Install Triton | `pip install triton` | medium | pending | Enables inductor backend for torch.compile |

  Multi-GPU but no efficient launch tool:
  | 3 | Install Accelerate | `pip install accelerate` | medium | pending | Simplifies multi-GPU launch for HF workflows |

  HF cache on slow storage:
  | 4 | Move HF cache to fast storage | `export HF_HOME=/scratch/user/.cache/huggingface` + add to shell rc | medium | pending | Currently on NFS (~/.cache), /scratch is local NVMe |

  Old PyTorch missing features:
  | 5 | Upgrade PyTorch | `pip install torch==2.4.0 --index-url https://download.pytorch.org/whl/cu122` | high | pending | Current 1.13 lacks torch.compile, SDPA, fused AdamW |

  No quantization support for inference:
  | 6 | Install bitsandbytes | `pip install bitsandbytes` | low | pending | Enables 4/8-bit quantization for fitting larger models |

  DeepSpeed not installed for large model training:
  | 7 | Install DeepSpeed | `pip install deepspeed` | medium | pending | Enables ZeRO offloading for models exceeding GPU VRAM |
-->

---

## Profiling Source
<!-- How this file was generated. Helps identify stale info. -->
- **method**: (auto-profiled | manual | web-assisted | ssh-profiled)
- **profiled on**: (date)
- **host**: (hostname)
- **notes**: (e.g. "cluster docs from https://docs.cluster.edu/gpu-partitions")
