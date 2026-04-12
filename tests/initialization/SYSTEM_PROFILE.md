# System Profile

> Simulated output from hardware profiling commands.
> The agent should use this to generate INFRA.md using the INFRA template.

## nvidia-smi --query-gpu=index,name,memory.total,driver_version --format=csv,noheader,nounits

```
0, NVIDIA A100-SXM4-80GB, 81920, 535.129.03
1, NVIDIA A100-SXM4-80GB, 81920, 535.129.03
2, NVIDIA A100-SXM4-80GB, 81920, 535.129.03
3, NVIDIA A100-SXM4-80GB, 81920, 535.129.03
```

## GPU Compute Capability

```
[(0, (8, 0)), (1, (8, 0)), (2, (8, 0)), (3, (8, 0))]
```

## nvidia-smi topo -m

```
        GPU0    GPU1    GPU2    GPU3    CPU Affinity    NUMA Affinity
GPU0     X      NV12    NV12    NV12    0-63            0
GPU1    NV12     X      NV12    NV12    0-63            0
GPU2    NV12    NV12     X      NV12    0-63            0
GPU3    NV12    NV12    NV12     X      0-63            0
```

## CUDA Version

```
12.2
```

## lscpu (selected fields)

```
Model name:          AMD EPYC 7742 64-Core Processor
CPU(s):              128
Thread(s) per core:  2
Core(s) per socket:  64
```

## free -h

```
              total        used        free      shared  buff/cache   available
Mem:          503Gi       42Gi       380Gi       1.2Gi        81Gi       456Gi
Swap:          16Gi          0B        16Gi
```

## df -h (relevant paths)

```
Filesystem      Size  Used Avail Use% Mounted on
/dev/nvme0n1    1.8T  420G  1.3T  25% /
/dev/nvme1n1    3.6T  1.2T  2.3T  35% /scratch
nas01:/shared   50T   32T   18T   64% /data
```

## Mount types

```
/dev/nvme0n1 on / type ext4 (rw,relatime)
/dev/nvme1n1 on /scratch type ext4 (rw,relatime)
nas01:/shared on /data type nfs4 (ro,relatime)
```

## Python package versions

```
torch: 2.4.0+cu122
flash_attn: not installed
deepspeed: 0.14.0
accelerate: 0.33.0
apex: not installed
bitsandbytes: 0.43.1
xformers: 0.0.27
triton: not installed
vllm: 0.5.0
```

## Python feature checks

```
torch.compile: available
SDPA: available
fused AdamW: available
```

## Project context

- **project**: llm-finetune
- **conda env**: `conda activate llm-ft`
- **python**: 3.11.8
- **working dir**: /home/researcher/llm-finetune
- **checkpoints**: /scratch/researcher/checkpoints
- **datasets**: /data/nlp/instruction-tuning/
- **HuggingFace cache**: /scratch/researcher/.cache/huggingface
- **scheduler**: none (local server, not a cluster)
