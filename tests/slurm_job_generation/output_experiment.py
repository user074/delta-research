#!/usr/bin/env python3
"""R007: compare LoRA rank 64 with the R006 rank-16 baseline.

This file is intentionally standalone for execution on a SLURM compute node.
It is launched with ``torchrun --nproc_per_node=4`` for both smoke and hero
execution so the tested distributed path is the path used by the experiment.
"""

import gc
import hashlib
import json
import math
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


RUN_ID = "R007"
PROJECT_ROOT = Path("/home/researcher/llm-finetune")
RUN_DIR = PROJECT_ROOT / "RUNS" / RUN_ID
LOG_DIR = RUN_DIR / "logs"
METRICS_DIR = RUN_DIR / "metrics"
ARTIFACT_DIR = RUN_DIR / "artifacts"
REPORT_PATH = PROJECT_ROOT / "REPORTS" / f"{RUN_ID}.md"

BASE_CHECKPOINT = Path("/scratch/researcher/checkpoints/llama-3-8b-base")
DATASET_PATH = Path("/data/nlp/instruction-tuning/alpaca_cleaned.json")
RANK16_RESULTS_PATH = PROJECT_ROOT / "RUNS/R006/artifacts/lora_r16_results.json"
RANK16_HISTORY_PATH = PROJECT_ROOT / "RUNS/R006/metrics/training_history.json"
R006_DATASET_MANIFEST = PROJECT_ROOT / "RUNS/R006/artifacts/dataset_manifest.json"
RANK16_CHECKPOINT = Path("/scratch/researcher/checkpoints/R006/lora_r16")
PROCESSED_DATASET_PATH = Path("/scratch/researcher/R006/alpaca_processed")
RANK64_CHECKPOINT = Path("/scratch/researcher/checkpoints") / RUN_ID / "lora_r64"

WORLD_SIZE = 4
SEED = 42
MAX_LENGTH = 2048
EPOCHS = 3
INITIAL_BATCH_SIZE = 8
LEARNING_RATE = 2e-4
EFFICIENCY_PROTOCOL = "r007-comparable-v1"
OPTIMIZER_NAME = "adamw_torch_fused"
ADAM_BETA1 = 0.9
ADAM_BETA2 = 0.999
ADAM_EPSILON = 1e-8
WEIGHT_DECAY = 0.0
LR_SCHEDULER_TYPE = "linear"
WARMUP_RATIO = 0.0
GRADIENT_ACCUMULATION_STEPS = 1
MAX_GRAD_NORM = 1.0
TARGET_MODULES = [
    "q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"
]

os.environ.setdefault("WANDB_PROJECT", "llm-finetune")
os.environ.setdefault("WANDB_MODE", "offline")
os.environ.setdefault("WANDB_RUN_NAME", RUN_ID)
os.environ.setdefault("WANDB_DIR", str(RUN_DIR / "wandb"))
os.environ.setdefault("WANDB_ENTITY", "mylab")
os.environ.setdefault("HF_HOME", "/scratch/researcher/.cache/huggingface")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


# DELTA marker helpers from templates/OBSERVABILITY.md.
def delta_start() -> None:
    ts = datetime.now(timezone.utc).isoformat()
    print(f"[DELTA-START] {RUN_ID} | {ts}", flush=True)


def delta_progress(pct: int, message: str = "") -> None:
    print(f"[DELTA-PROGRESS] {pct}% | {message}", flush=True)


def delta_metric(**kwargs: Any) -> None:
    pairs = " | ".join(f"{key}={value}" for key, value in kwargs.items())
    print(f"[DELTA-METRIC] {pairs}", flush=True)


def delta_done(elapsed: str) -> None:
    print(
        f"[DELTA-DONE] {RUN_ID} | elapsed={elapsed} | status=completed",
        flush=True,
    )


def delta_smoke_done(elapsed: str) -> None:
    print(
        f"[DELTA-SMOKE-DONE] {RUN_ID} | elapsed={elapsed} | status=smoke_passed",
        flush=True,
    )


def delta_error(message: str) -> None:
    print(f"[DELTA-ERROR] {message}", flush=True)


def delta_blocker(message: str) -> None:
    print(f"[DELTA-BLOCKER] {RUN_ID} | {message}", flush=True)
    sys.exit(1)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ExperimentLogger:
    """Dense, append-only text logging plus structured JSON metrics."""

    def __init__(self, run_dir: Path, log_name: str = "train.log") -> None:
        self.log_dir = run_dir / "logs"
        self.metrics_dir = run_dir / "metrics"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = (self.log_dir / log_name).open("a", encoding="utf-8")
        job_id = os.environ.get("SLURM_JOB_ID", "direct")
        restart = os.environ.get("TORCHELASTIC_RESTART_COUNT", "0")
        self.history_path = self.metrics_dir / f"training_history-{job_id}-attempt-{restart}.json"
        self.history: List[Dict[str, Any]] = []

    def log_step(self, **kwargs: Any) -> None:
        kwargs.setdefault("timestamp", utc_now())
        line = "\t".join(f"{key}={value}" for key, value in kwargs.items())
        self.log_file.write(line + "\n")
        self.log_file.flush()
        self.history.append(kwargs)
        if len(self.history) % 1000 == 0:
            self.save_history()

    def log_results(self, results: Dict[str, Any], name: str = "results.json") -> None:
        path = self.metrics_dir / name
        with path.open("w", encoding="utf-8") as handle:
            json.dump(results, handle, indent=2)

    def save_history(self) -> None:
        with self.history_path.open("w", encoding="utf-8") as handle:
            json.dump(self.history, handle, indent=2)

    def close(self) -> None:
        if self.log_file.closed:
            return
        self.save_history()
        self.log_file.close()


def require_path(path: Path, description: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"required {description} not found: {path}")


def required_numeric_metric(payload: Dict[str, Any], name: str) -> float:
    """Read one metric from the versioned, like-for-like efficiency schema."""
    efficiency = payload.get("efficiency")
    if not isinstance(efficiency, dict) or name not in efficiency:
        raise RuntimeError(f"R006 artifact is missing required measured metric: {name}")
    value = efficiency[name]
    if not isinstance(value, (int, float)):
        raise RuntimeError(f"R006 metric {name} is not numeric: {value!r}")
    return float(value)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_r006_data() -> Dict[str, Any]:
    """Prove that the immutable processed split is the one documented by R006."""
    for path, description in (
        (DATASET_PATH, "source dataset"),
        (PROCESSED_DATASET_PATH, "R006 processed dataset"),
        (R006_DATASET_MANIFEST, "R006 dataset manifest"),
        (RANK16_CHECKPOINT, "R006 rank-16 checkpoint"),
        (RANK16_RESULTS_PATH, "R006 rank-16 results"),
        (RANK16_HISTORY_PATH, "R006 rank-16 training history"),
    ):
        require_path(path, description)
    with R006_DATASET_MANIFEST.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    expected = {
        "source_path": str(DATASET_PATH),
        "processed_path": str(PROCESSED_DATASET_PATH),
        "tokenizer_path": str(BASE_CHECKPOINT),
        "split_seed": SEED,
        "eval_fraction": 0.10,
        "max_length": MAX_LENGTH,
    }
    mismatches = {
        key: {"expected": value, "observed": manifest.get(key)}
        for key, value in expected.items()
        if manifest.get(key) != value
    }
    recorded_sha = manifest.get("source_sha256")
    if not isinstance(recorded_sha, str) or len(recorded_sha) != 64:
        mismatches["source_sha256"] = {"expected": "64-char SHA-256", "observed": recorded_sha}
    elif sha256_file(DATASET_PATH) != recorded_sha:
        mismatches["source_sha256"] = {"expected": recorded_sha, "observed": "current source differs"}
    if mismatches:
        raise RuntimeError(f"R006 dataset provenance mismatch: {mismatches}")
    with RANK16_RESULTS_PATH.open("r", encoding="utf-8") as handle:
        prior = json.load(handle)
    training_config = prior.get("training_config")
    expected_training = {
        "base_checkpoint": str(BASE_CHECKPOINT),
        "lora_rank": 16,
        "lora_alpha": 32,
        "lora_dropout": 0.05,
        "bias": "none",
        "target_modules": TARGET_MODULES,
        "learning_rate": LEARNING_RATE,
        "optimizer": OPTIMIZER_NAME,
        "adam_beta1": ADAM_BETA1,
        "adam_beta2": ADAM_BETA2,
        "adam_epsilon": ADAM_EPSILON,
        "weight_decay": WEIGHT_DECAY,
        "lr_scheduler_type": LR_SCHEDULER_TYPE,
        "warmup_ratio": WARMUP_RATIO,
        "gradient_accumulation_steps": GRADIENT_ACCUMULATION_STEPS,
        "max_grad_norm": MAX_GRAD_NORM,
        "epochs": EPOCHS,
        "per_device_batch_size": INITIAL_BATCH_SIZE,
        "precision": "bf16",
        "max_length": MAX_LENGTH,
    }
    if not isinstance(training_config, dict):
        raise RuntimeError("R006 results lack the versioned training_config required for a rank-only contrast")
    config_mismatches = {
        key: {"expected": value, "observed": training_config.get(key)}
        for key, value in expected_training.items()
        if training_config.get(key) != value
    }
    if config_mismatches:
        raise RuntimeError(f"R006 training configuration is not rank-comparable: {config_mismatches}")
    return manifest


def format_example(example: Dict[str, Any]) -> Tuple[str, str]:
    instruction = str(example.get("instruction", "")).strip()
    context = str(example.get("input", "")).strip()
    response = str(example.get("output", example.get("response", ""))).strip()
    prompt = f"### Instruction:\n{instruction}\n"
    if context:
        prompt += f"\n### Input:\n{context}\n"
    prompt += "\n### Response:\n"
    return prompt, response


def collate_preserving_labels(
    features: List[Dict[str, Any]], tokenizer: Any, torch_module: Any
) -> Dict[str, Any]:
    """Pad inputs while preserving R006 response-only `-100` label masking."""
    max_length = max(len(feature["input_ids"]) for feature in features)
    batch_size = len(features)
    input_ids = torch_module.full(
        (batch_size, max_length), tokenizer.pad_token_id, dtype=torch_module.long
    )
    attention_mask = torch_module.zeros((batch_size, max_length), dtype=torch_module.long)
    labels = torch_module.full((batch_size, max_length), -100, dtype=torch_module.long)
    for row, feature in enumerate(features):
        length = len(feature["input_ids"])
        input_ids[row, :length] = torch_module.tensor(feature["input_ids"], dtype=torch_module.long)
        attention_mask[row, :length] = torch_module.tensor(
            feature["attention_mask"], dtype=torch_module.long
        )
        labels[row, :length] = torch_module.tensor(feature["labels"], dtype=torch_module.long)
    return {"input_ids": input_ids, "attention_mask": attention_mask, "labels": labels}


class LabelPreservingCollator:
    def __init__(self, tokenizer: Any) -> None:
        self.tokenizer = tokenizer

    def __call__(self, features: List[Dict[str, Any]]) -> Dict[str, Any]:
        import torch

        return collate_preserving_labels(features, self.tokenizer, torch)


def lcs_length(left: List[str], right: List[str]) -> int:
    """Memory-efficient longest-common-subsequence length for ROUGE-L."""
    if len(left) < len(right):
        left, right = right, left
    previous = [0] * (len(right) + 1)
    for left_token in left:
        current = [0]
        for index, right_token in enumerate(right, start=1):
            if left_token == right_token:
                current.append(previous[index - 1] + 1)
            else:
                current.append(max(current[-1], previous[index]))
        previous = current
    return previous[-1]


def rouge_l_f1(prediction: str, reference: str) -> float:
    predicted_tokens = prediction.split()
    reference_tokens = reference.split()
    if not predicted_tokens or not reference_tokens:
        return 0.0
    overlap = lcs_length(predicted_tokens, reference_tokens)
    precision = overlap / len(predicted_tokens)
    recall = overlap / len(reference_tokens)
    if precision + recall == 0.0:
        return 0.0
    return 2.0 * precision * recall / (precision + recall)


def evaluate_generation(
    model: Any,
    tokenizer: Any,
    eval_dataset: Any,
    torch_module: Any,
    dist_module: Any,
    rank: int,
    local_rank: int,
    world_size: int,
    batch_size: int = 8,
) -> Tuple[float, List[int]]:
    """Shard held-out generation across ranks and compute exact mean ROUGE-L."""
    model.eval()
    device = torch_module.device("cuda", local_rank)
    local_score_sum = 0.0
    local_count = 0
    local_indices = list(range(rank, len(eval_dataset), world_size))
    original_padding_side = tokenizer.padding_side
    tokenizer.padding_side = "left"
    try:
        for start in range(0, len(local_indices), batch_size):
            indices = local_indices[start : start + batch_size]
            rows = [eval_dataset[index] for index in indices]
            prompts = [row["prompt_text"] for row in rows]
            references = [row["reference_text"] for row in rows]
            inputs = tokenizer(
                prompts,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=MAX_LENGTH,
            )
            inputs = {key: value.to(device, non_blocking=True) for key, value in inputs.items()}
            prompt_width = inputs["input_ids"].shape[1]
            with torch_module.inference_mode(), torch_module.autocast(
                "cuda", dtype=torch_module.bfloat16
            ):
                generated = model.generate(
                    **inputs,
                    max_new_tokens=256,
                    do_sample=False,
                    pad_token_id=tokenizer.pad_token_id,
                    eos_token_id=tokenizer.eos_token_id,
                )
            predictions = tokenizer.batch_decode(
                generated[:, prompt_width:], skip_special_tokens=True
            )
            batch_scores = [
                rouge_l_f1(prediction.strip(), reference.strip())
                for prediction, reference in zip(predictions, references)
            ]
            local_score_sum += sum(batch_scores)
            local_count += len(batch_scores)
    finally:
        tokenizer.padding_side = original_padding_side

    totals = torch_module.tensor(
        [local_score_sum, float(local_count)], device=device, dtype=torch_module.float64
    )
    dist_module.all_reduce(totals, op=dist_module.ReduceOp.SUM)
    count_tensor = torch_module.tensor([local_count], device=device, dtype=torch_module.int64)
    gathered_counts = [torch_module.zeros_like(count_tensor) for _ in range(world_size)]
    dist_module.all_gather(gathered_counts, count_tensor)
    per_rank_counts = [int(value.item()) for value in gathered_counts]
    return float(totals[0].item()) / max(1.0, float(totals[1].item())), per_rank_counts


def evaluate_adapter_checkpoint(
    adapter_path: Path,
    tokenizer: Any,
    eval_dataset: Any,
    torch_module: Any,
    dist_module: Any,
    rank: int,
    local_rank: int,
    world_size: int,
) -> Dict[str, Any]:
    """Evaluate an R006 adapter when its artifact provides a checkpoint path."""
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    base = AutoModelForCausalLM.from_pretrained(
        str(BASE_CHECKPOINT),
        torch_dtype=torch_module.bfloat16,
        attn_implementation="sdpa",
        low_cpu_mem_usage=True,
    ).to(f"cuda:{local_rank}")
    model = PeftModel.from_pretrained(base, str(adapter_path)).to(f"cuda:{local_rank}")
    model.eval()
    local_loss_sum = 0.0
    local_token_count = 0
    local_indices = list(range(rank, len(eval_dataset), world_size))
    for start in range(0, len(local_indices), INITIAL_BATCH_SIZE):
        features = []
        indices = local_indices[start : start + INITIAL_BATCH_SIZE]
        for index in indices:
            row = eval_dataset[index]
            features.append(
                {
                    "input_ids": row["input_ids"],
                    "attention_mask": row["attention_mask"],
                    "labels": row["labels"],
                }
            )
        batch = collate_preserving_labels(features, tokenizer, torch_module)
        batch = {
            key: value.to(f"cuda:{local_rank}", non_blocking=True)
            for key, value in batch.items()
        }
        with torch_module.inference_mode(), torch_module.autocast(
            "cuda", dtype=torch_module.bfloat16
        ):
            loss = model(**batch).loss
        token_count = int((batch["labels"] != -100).sum().item())
        local_loss_sum += float(loss.detach()) * token_count
        local_token_count += token_count
    loss_totals = torch_module.tensor(
        [local_loss_sum, float(local_token_count)],
        device=f"cuda:{local_rank}",
        dtype=torch_module.float64,
    )
    dist_module.all_reduce(loss_totals, op=dist_module.ReduceOp.SUM)
    eval_loss = float(loss_totals[0].item()) / max(1.0, float(loss_totals[1].item()))
    rouge_l, per_rank_eval_examples = evaluate_generation(
        model,
        tokenizer,
        eval_dataset,
        torch_module,
        dist_module,
        rank,
        local_rank,
        world_size,
    )
    del model, base
    gc.collect()
    torch_module.cuda.empty_cache()
    dist_module.barrier()
    return {
        "eval_loss": eval_loss,
        "perplexity": math.exp(min(eval_loss, 20.0)),
        "rouge_l": rouge_l,
        "per_rank_eval_examples": per_rank_eval_examples,
    }


def load_rank16_results(
    tokenizer: Any,
    eval_dataset: Any,
    torch_module: Any,
    dist_module: Any,
    rank: int,
    local_rank: int,
    world_size: int,
) -> Dict[str, Any]:
    """Re-evaluate the exact R006 adapter on R007's held-out split."""
    require_path(RANK16_RESULTS_PATH, "R006 rank-16 results")
    require_path(RANK16_CHECKPOINT, "R006 rank-16 checkpoint")
    with RANK16_RESULTS_PATH.open("r", encoding="utf-8") as handle:
        prior = json.load(handle)
    if prior.get("efficiency_protocol") != EFFICIENCY_PROTOCOL:
        raise RuntimeError(
            "R006 efficiency metrics are not comparable: expected protocol "
            f"{EFFICIENCY_PROTOCOL!r}, got {prior.get('efficiency_protocol')!r}"
        )

    efficiency = {
        "throughput_tok_s": required_numeric_metric(prior, "throughput_tok_s"),
        "peak_vram_gb_per_gpu": required_numeric_metric(prior, "peak_vram_gb_per_gpu"),
        "train_minutes": required_numeric_metric(prior, "train_minutes"),
    }

    measured = evaluate_adapter_checkpoint(
        RANK16_CHECKPOINT,
        tokenizer,
        eval_dataset,
        torch_module,
        dist_module,
        rank,
        local_rank,
        world_size,
    )
    measured.update(efficiency)
    measured["evaluation_source"] = str(RANK16_CHECKPOINT)
    return measured


def create_plots(results: Dict[str, Any], history: List[Dict[str, Any]]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    with RANK16_HISTORY_PATH.open("r", encoding="utf-8") as handle:
        rank16_history = json.load(handle)
    if not isinstance(rank16_history, list):
        raise RuntimeError("R006 training history must be a list of measured step records")
    steps = [entry["step"] for entry in history if "step" in entry and "loss" in entry]
    losses = [entry["loss"] for entry in history if "step" in entry and "loss" in entry]
    rank16_steps = [
        entry["step"] for entry in rank16_history if "step" in entry and "loss" in entry
    ]
    rank16_losses = [
        entry["loss"] for entry in rank16_history if "step" in entry and "loss" in entry
    ]
    if not rank16_steps:
        raise RuntimeError("R006 training history contains no step/loss measurements")
    figure, axis = plt.subplots(figsize=(8, 5))
    axis.plot(rank16_steps, rank16_losses, color="#7f8c8d", label="LoRA rank 16")
    if steps:
        axis.plot(steps, losses, color="#3366cc", label="LoRA rank 64")
    axis.set(title="LoRA training curves", xlabel="Optimizer step", ylabel="Loss")
    axis.grid(alpha=0.25)
    axis.legend(loc="best")
    figure.tight_layout()
    figure.savefig(ARTIFACT_DIR / "training_curves.png", dpi=160)
    plt.close(figure)

    ranks = ["rank 16", "rank 64"]
    figure, axes = plt.subplots(1, 2, figsize=(10, 4.5))
    axes[0].bar(
        ranks,
        [results["rank16"]["eval_loss"], results["rank64"]["eval_loss"]],
        color=["#7f8c8d", "#3366cc"],
    )
    axes[0].axhline(1.75, color="#cc3333", linestyle="--", label="rank-64 target")
    axes[0].set_title("Held-out loss (lower is better)")
    axes[0].legend()
    axes[1].bar(
        ranks,
        [results["rank16"]["rouge_l"], results["rank64"]["rouge_l"]],
        color=["#7f8c8d", "#3366cc"],
    )
    axes[1].axhline(0.46, color="#cc3333", linestyle="--", label="rank-64 target")
    axes[1].set_title("ROUGE-L (higher is better)")
    axes[1].legend()
    figure.tight_layout()
    figure.savefig(ARTIFACT_DIR / "eval_metrics.png", dpi=160)
    plt.close(figure)

    figure, axes = plt.subplots(1, 2, figsize=(10, 4.5))
    axes[0].bar(
        ranks,
        [
            results["rank16"]["throughput_tok_s"],
            results["rank64"]["throughput_tok_s"],
        ],
        color=["#7f8c8d", "#3366cc"],
    )
    axes[0].axhline(1480.0, color="#cc3333", linestyle="--", label="80% baseline")
    axes[0].set_title("Training throughput (tokens/s)")
    axes[0].legend()
    axes[1].bar(
        ranks,
        [
            results["rank16"]["peak_vram_gb_per_gpu"],
            results["rank64"]["peak_vram_gb_per_gpu"],
        ],
        color=["#7f8c8d", "#3366cc"],
    )
    axes[1].set_title("Peak VRAM per GPU (GB)")
    figure.tight_layout()
    figure.savefig(ARTIFACT_DIR / "efficiency_comparison.png", dpi=160)
    plt.close(figure)


def write_report(results: Dict[str, Any], started: str, completed: str) -> None:
    rank16 = results["rank16"]
    rank64 = results["rank64"]
    loss_supports_rank64 = rank64["eval_loss"] < 1.75
    rouge_supports_rank64 = rank64["rouge_l"] > 0.46
    rank64_wins = loss_supports_rank64 or rouge_supports_rank64
    verdict = "contradicts" if rank64_wins else "supports"
    interpretation = (
        "Rank 64 crossed at least one pre-execution quality threshold, lowering "
        "confidence that rank 16 is sufficient."
        if rank64_wins
        else "Rank 64 crossed neither pre-execution quality threshold, raising "
        "confidence that rank 16 is sufficient."
    )
    throughput_change = 100.0 * (
        rank64["throughput_tok_s"] / rank16["throughput_tok_s"] - 1.0
    )
    per_rank_train_batches = results["per_rank_train_batches"]
    per_rank_eval_examples = rank64["per_rank_eval_examples"]
    report = f"""# REPORT — {RUN_ID}: Does LoRA rank 64 improve quality enough to justify its cost?

## Answer
The result {verdict} hypothesis #3: rank 64 reached {rank64['eval_loss']:.4f} held-out loss and {rank64['rouge_l']:.4f} ROUGE-L versus the 1.75/0.46 thresholds. {interpretation}

## Motivation
This run tests belief #3: “LoRA rank 16 is sufficient for instruction-following quality.” Before execution, the working plan called rank 64 worthwhile if held-out loss fell below 1.75 or ROUGE-L exceeded 0.46.

## Questions tested
1. **Primary:** Does rank 64 reach held-out loss <1.75 or ROUGE-L >0.46, enough to contradict rank-16 sufficiency?
2. **Secondary:** What throughput, memory, and training-time cost accompanies rank 64?

## Method
- **approach:** Train rank 64 while reusing the exact rank-16 checkpoint and fixed evaluation protocol.
- **data:** Validated R006 90/10 split, manifest, source SHA-256, tokenizer, seed, and max length.
- **comparisons:** LoRA rank 16 versus rank 64; all non-rank settings held fixed.
- **metrics:** Held-out loss, perplexity, ROUGE-L, throughput, peak VRAM, and training time.
- **repetitions:** One matched three-epoch training run per rank on the fixed split.
- **environment:** BF16, SDPA, DDP on four A100 GPUs; learning rate {LEARNING_RATE}; per-device batch {results['batch_size']}.
- **parallel execution:** Human-confirmed 4/4 A100 GPUs; four-rank DDP training and four-rank data-parallel evaluation, per-device batch {results['batch_size']}, global batch {results['batch_size'] * results['world_size']}.
- **scientific changes during execution:** None.

## Experiments
| Experiment | Why it is needed | Comparison / conditions |
|------------|------------------|-------------------------|
| Matched rank comparison | Answers the quality-efficiency question | Rank 16 vs 64 on one fixed split/evaluator |

## Results

### Data

| Rank | Eval loss | Perplexity | ROUGE-L | Throughput (tok/s) | Peak VRAM/GPU (GB) | Train time (min) |
|---:|---:|---:|---:|---:|---:|---:|
| 16 | {rank16['eval_loss']:.4f} | {rank16['perplexity']:.4f} | {rank16['rouge_l']:.4f} | {rank16['throughput_tok_s']:.1f} | {rank16['peak_vram_gb_per_gpu']:.2f} | {rank16['train_minutes']:.2f} |
| 64 | {rank64['eval_loss']:.4f} | {rank64['perplexity']:.4f} | {rank64['rouge_l']:.4f} | {rank64['throughput_tok_s']:.1f} | {rank64['peak_vram_gb_per_gpu']:.2f} | {rank64['train_minutes']:.2f} |

Rank-64 throughput changed by {throughput_change:+.2f}% relative to rank 16. Rank 64 used approximately 4× as many LoRA parameters.

- **wall-clock to answer:** {results['wall_clock_seconds']:.1f} seconds from launch to complete metrics and report.
- **GPU use, if applicable:** 4/4 confirmed GPUs did useful work. Per-rank training batches: {per_rank_train_batches}; per-rank rank-64 evaluation examples: {per_rank_eval_examples}; aggregate rank-64 throughput: {rank64['throughput_tok_s']:.1f} tokens/s; maximum peak memory: {rank64['peak_vram_gb_per_gpu']:.2f} GB/GPU.

## Analysis
{interpretation} The measured efficiency cost is reflected in throughput and peak VRAM above. Rank-16 evaluation source: `{rank16['evaluation_source']}`.

## Limitations and tested scope
A different generation protocol could reverse a marginal ROUGE-L result. The conclusion is limited to this checkpoint, split, evaluator, seed, `{EFFICIENCY_PROTOCOL}`, and four-A100 environment.

## Conclusion
- **answer:** {verdict} hypothesis/belief #3.
- **decisive evidence:** Rank 64 reached loss {rank64['eval_loss']:.4f} and ROUGE-L {rank64['rouge_l']:.4f} against thresholds 1.75 and 0.46.
- **confidence:** The supervisor assigns the scoped update from these predeclared thresholds.
- **next experiment:** None — the rank-16 versus rank-64 choice is decided in this scope.

## Reproducibility
- **command:** `sbatch /home/researcher/llm-finetune/RUNS/R007/job.sh`
- **parallelism:** `torchrun --standalone --nproc_per_node=4`; DDP training, four-rank example-sharded evaluation, per-device batch {results['batch_size']}, global batch {results['batch_size'] * results['world_size']}.
- **metrics:** `../RUNS/R007/metrics/lora_rank_comparison.json`
- **artifacts:** `../RUNS/R007/artifacts/lora_rank_comparison.json`

## Meta
- **run_id**: {RUN_ID}
- **started**: {started}
- **completed**: {completed}
- **execution**: slurm
- **slurm_job_id**: {os.environ.get('SLURM_JOB_ID', 'unknown')}
- **wandb_run**: offline run under `{os.environ['WANDB_DIR']}`
"""
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")


def train_worker(started: str, started_wall: float) -> None:
    """One DDP process; rank zero owns logging, evaluation artifacts, and report."""
    rank = int(os.environ["RANK"])
    local_rank = int(os.environ["LOCAL_RANK"])
    world_size = int(os.environ["WORLD_SIZE"])
    if world_size != WORLD_SIZE:
        raise RuntimeError(f"expected {WORLD_SIZE} torchrun processes, got {world_size}")

    import torch
    import torch.distributed as dist
    import wandb
    from datasets import load_from_disk
    from peft import LoraConfig, get_peft_model
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        Trainer,
        TrainerCallback,
        TrainingArguments,
        set_seed,
    )

    torch.cuda.set_device(local_rank)
    dist.init_process_group("nccl")
    set_seed(SEED)
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.benchmark = True

    logger: Optional[ExperimentLogger] = None
    wandb_started = False
    try:
        if rank == 0:
            for path in (LOG_DIR, METRICS_DIR, ARTIFACT_DIR, RANK64_CHECKPOINT):
                path.mkdir(parents=True, exist_ok=True)
            require_path(BASE_CHECKPOINT, "base checkpoint")
            logger = ExperimentLogger(RUN_DIR)

        tokenizer = AutoTokenizer.from_pretrained(str(BASE_CHECKPOINT), use_fast=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        tokenizer.padding_side = "right"

        dist.barrier()
        dataset = load_from_disk(str(PROCESSED_DATASET_PATH))

        config = {
            "run_id": RUN_ID,
            "model": str(BASE_CHECKPOINT),
            "dataset": str(DATASET_PATH),
            "train_examples": len(dataset["train"]),
            "eval_examples": len(dataset["eval"]),
            "lora_rank": 64,
            "lora_alpha": 128,
            "learning_rate": LEARNING_RATE,
            "epochs": EPOCHS,
            "initial_per_device_batch_size": INITIAL_BATCH_SIZE,
            "precision": "bf16",
            "parallelism": f"DDP ({world_size} GPUs)",
            "max_length": MAX_LENGTH,
            "seed": SEED,
        }
        if rank == 0:
            wandb.init(
                project=os.environ["WANDB_PROJECT"],
                entity=os.environ.get("WANDB_ENTITY"),
                name=os.environ["WANDB_RUN_NAME"],
                config=config,
                dir=os.environ["WANDB_DIR"],
            )
            wandb_started = True

        tokenizer = AutoTokenizer.from_pretrained(
            str(BASE_CHECKPOINT), use_fast=True, local_files_only=True
        )
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        model = AutoModelForCausalLM.from_pretrained(
            str(BASE_CHECKPOINT),
            torch_dtype=torch.bfloat16,
            attn_implementation="sdpa",
            low_cpu_mem_usage=True,
        )
        model.config.use_cache = False
        model.enable_input_require_grads()
        lora_config = LoraConfig(
            r=64,
            lora_alpha=128,
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM",
            target_modules=TARGET_MODULES,
        )
        model = get_peft_model(model, lora_config)
        collator = LabelPreservingCollator(tokenizer)

        class DenseLoggingCallback(TrainerCallback):
            def __init__(self, dense_logger: Optional[ExperimentLogger]) -> None:
                self.dense_logger = dense_logger
                self.emitted: set[int] = set()

            def on_log(self, args: Any, state: Any, control: Any, logs: Any = None, **kwargs: Any) -> None:
                if rank != 0 or not logs:
                    return
                record: Dict[str, Any] = {"step": int(state.global_step)}
                for key, value in logs.items():
                    if isinstance(value, (int, float)):
                        record[key] = float(value)
                if self.dense_logger is not None:
                    self.dense_logger.log_step(**record)
                wandb.log(record, step=int(state.global_step))
                if state.max_steps:
                    pct = int(100 * state.global_step / state.max_steps)
                    for milestone in (25, 50, 75, 90):
                        if pct >= milestone and milestone not in self.emitted:
                            loss_text = record.get("loss", "n/a")
                            delta_progress(
                                milestone,
                                f"rank-64 training step {state.global_step}/{state.max_steps}; loss={loss_text}",
                            )
                            self.emitted.add(milestone)
                    metric_interval = max(1, state.max_steps // 10)
                    if state.global_step % metric_interval == 0 and "loss" in record:
                        delta_metric(step=state.global_step, loss=f"{record['loss']:.4f}")

        def build_trainer(batch_size: int) -> Trainer:
            arguments = TrainingArguments(
                output_dir=str(RANK64_CHECKPOINT),
                overwrite_output_dir=True,
                num_train_epochs=EPOCHS,
                per_device_train_batch_size=batch_size,
                per_device_eval_batch_size=batch_size,
                learning_rate=LEARNING_RATE,
                optim=OPTIMIZER_NAME,
                adam_beta1=ADAM_BETA1,
                adam_beta2=ADAM_BETA2,
                adam_epsilon=ADAM_EPSILON,
                weight_decay=WEIGHT_DECAY,
                lr_scheduler_type=LR_SCHEDULER_TYPE,
                warmup_ratio=WARMUP_RATIO,
                gradient_accumulation_steps=GRADIENT_ACCUMULATION_STEPS,
                max_grad_norm=MAX_GRAD_NORM,
                bf16=True,
                tf32=True,
                logging_strategy="steps",
                logging_steps=1,
                eval_strategy="epoch",
                save_strategy="epoch",
                save_total_limit=2,
                dataloader_num_workers=4,
                dataloader_pin_memory=True,
                ddp_find_unused_parameters=False,
                report_to=[],
                remove_unused_columns=True,
                seed=SEED,
                data_seed=SEED,
                local_rank=local_rank,
            )
            return Trainer(
                model=model,
                args=arguments,
                train_dataset=dataset["train"],
                eval_dataset=dataset["eval"],
                data_collator=collator,
                callbacks=[DenseLoggingCallback(logger)],
            )

        selected_batch_size = INITIAL_BATCH_SIZE
        trainer = build_trainer(selected_batch_size)
        dist.barrier()
        torch.cuda.reset_peak_memory_stats(local_rank)
        train_started = time.perf_counter()
        # An OOM must terminate this DDP launch. Retrying inside only some ranks can
        # deadlock collectives or preserve partial trainer state. The supervisor may
        # edit the working plan and submit a fresh job at batch size 4.
        train_output = trainer.train()

        local_train_seconds = torch.tensor(
            [time.perf_counter() - train_started],
            device=f"cuda:{local_rank}",
            dtype=torch.float64,
        )
        dist.all_reduce(local_train_seconds, op=dist.ReduceOp.MAX)
        if rank == 0:
            trainer.save_model(str(RANK64_CHECKPOINT))
            tokenizer.save_pretrained(str(RANK64_CHECKPOINT))
        dist.barrier()

        local_peak_vram = torch.tensor(
            [torch.cuda.max_memory_allocated(local_rank)],
            device=f"cuda:{local_rank}",
            dtype=torch.float64,
        )
        dist.all_reduce(local_peak_vram, op=dist.ReduceOp.MAX)
        local_train_batches = torch.tensor(
            [int(trainer.state.global_step) * GRADIENT_ACCUMULATION_STEPS],
            device=f"cuda:{local_rank}",
            dtype=torch.int64,
        )
        gathered_train_batches = [torch.zeros_like(local_train_batches) for _ in range(world_size)]
        dist.all_gather(gathered_train_batches, local_train_batches)
        per_rank_train_batches = [int(value.item()) for value in gathered_train_batches]
        history = [
            {
                key: value
                for key, value in entry.items()
                if isinstance(value, (int, float))
            }
            for entry in trainer.state.log_history
        ] if rank == 0 else []
        del trainer, model
        gc.collect()
        torch.cuda.empty_cache()
        dist.barrier()

        if rank == 0:
            delta_progress(90, "rank-64 training complete; all four ranks evaluating both adapters")
        train_seconds = float(local_train_seconds.item())
        total_train_tokens = sum(len(row) for row in dataset["train"]["input_ids"]) * EPOCHS
        throughput = total_train_tokens / max(train_seconds, 1e-9)
        peak_vram = float(local_peak_vram.item()) / (1024**3)
        rank64 = evaluate_adapter_checkpoint(
            RANK64_CHECKPOINT,
            tokenizer,
            dataset["eval"],
            torch,
            dist,
            rank,
            local_rank,
            world_size,
        )
        rank64.update({
            "throughput_tok_s": throughput,
            "peak_vram_gb_per_gpu": peak_vram,
            "train_minutes": train_seconds / 60.0,
            "checkpoint": str(RANK64_CHECKPOINT),
            "efficiency_protocol": EFFICIENCY_PROTOCOL,
        })

        if rank == 0:
            delta_progress(95, "evaluating the exact R006 rank-16 adapter with the same evaluator")
        rank16 = load_rank16_results(
            tokenizer,
            dataset["eval"],
            torch,
            dist,
            rank,
            local_rank,
            world_size,
        )
        results = {
            "run_id": RUN_ID,
            "rank16": rank16,
            "rank64": rank64,
            "batch_size": selected_batch_size,
            "world_size": world_size,
            "per_rank_train_batches": per_rank_train_batches,
            "lora_parameter_ratio": 4.0,
            "loss_threshold": 1.75,
            "rouge_l_threshold": 0.46,
            "throughput_floor_tok_s": 1480.0,
            "wall_clock_seconds": time.perf_counter() - started_wall,
            "completed": utc_now(),
        }
        if rank == 0:
            if logger is not None:
                logger.log_results(results)
                logger.save_history()
            with (ARTIFACT_DIR / "lora_rank_comparison.json").open(
                "w", encoding="utf-8"
            ) as handle:
                json.dump(results, handle, indent=2)
            write_report(results, started=started, completed=results["completed"])
            wandb.log(
                {
                    "rank16/eval_loss": rank16["eval_loss"],
                    "rank16/rouge_l": rank16["rouge_l"],
                    "rank16/throughput_tok_s": rank16["throughput_tok_s"],
                    "rank64/eval_loss": rank64["eval_loss"],
                    "rank64/perplexity": rank64["perplexity"],
                    "rank64/rouge_l": rank64["rouge_l"],
                    "rank64/throughput_tok_s": rank64["throughput_tok_s"],
                    "rank64/peak_vram_gb_per_gpu": rank64["peak_vram_gb_per_gpu"],
                }
            )
            delta_metric(
                rank16_eval_loss=f"{rank16['eval_loss']:.4f}",
                rank64_eval_loss=f"{rank64['eval_loss']:.4f}",
                rank16_rouge_l=f"{rank16['rouge_l']:.4f}",
                rank64_rouge_l=f"{rank64['rouge_l']:.4f}",
                rank64_throughput_tok_s=f"{rank64['throughput_tok_s']:.1f}",
            )
    finally:
        if rank == 0:
            if logger is not None:
                logger.close()
            if wandb_started:
                wandb.finish()
        if dist.is_initialized():
            dist.destroy_process_group()


def smoke_worker() -> None:
    """Validate the exact four-GPU/data/checkpoint path without completing R007."""
    import torch
    import torch.distributed as dist
    from datasets import load_from_disk
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, AutoTokenizer

    rank = int(os.environ["RANK"])
    local_rank = int(os.environ["LOCAL_RANK"])
    world_size = int(os.environ["WORLD_SIZE"])
    if world_size != WORLD_SIZE:
        raise RuntimeError(f"smoke expected {WORLD_SIZE} torchrun processes, got {world_size}")
    torch.cuda.set_device(local_rank)
    dist.init_process_group("nccl")
    smoke_elapsed = 0.0
    try:
        validate_r006_data()
        dataset = load_from_disk(str(PROCESSED_DATASET_PATH))
        if "train" not in dataset or "eval" not in dataset:
            raise RuntimeError("R006 processed dataset lacks train/eval splits")
        if len(dataset["train"]) == 0 or len(dataset["eval"]) == 0:
            raise RuntimeError("R006 processed dataset lacks non-empty train/eval splits")
        required_columns = {"input_ids", "attention_mask", "labels", "prompt_text", "reference_text"}
        missing = required_columns.difference(dataset["eval"].column_names)
        if missing:
            raise RuntimeError(f"R006 eval split lacks required columns: {sorted(missing)}")
        tokenizer = AutoTokenizer.from_pretrained(
            str(BASE_CHECKPOINT), use_fast=True, local_files_only=True
        )
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        model = AutoModelForCausalLM.from_pretrained(
            str(BASE_CHECKPOINT),
            torch_dtype=torch.bfloat16,
            attn_implementation="sdpa",
            low_cpu_mem_usage=True,
            local_files_only=True,
        )
        model.config.use_cache = False
        model.enable_input_require_grads()
        model = get_peft_model(
            model,
            LoraConfig(
                r=64,
                lora_alpha=128,
                lora_dropout=0.05,
                bias="none",
                task_type="CAUSAL_LM",
                target_modules=TARGET_MODULES,
            ),
        ).to(local_rank)
        model = torch.nn.parallel.DistributedDataParallel(
            model, device_ids=[local_rank], find_unused_parameters=False
        )
        start = rank * INITIAL_BATCH_SIZE
        features = [
            {
                "input_ids": dataset["train"][index]["input_ids"],
                "attention_mask": dataset["train"][index]["attention_mask"],
                "labels": dataset["train"][index]["labels"],
            }
            for index in range(start, start + INITIAL_BATCH_SIZE)
        ]
        batch = collate_preserving_labels(features, tokenizer, torch)
        batch = {key: value.to(local_rank, non_blocking=True) for key, value in batch.items()}
        optimizer = torch.optim.AdamW(
            (parameter for parameter in model.parameters() if parameter.requires_grad),
            lr=LEARNING_RATE,
            betas=(ADAM_BETA1, ADAM_BETA2),
            eps=ADAM_EPSILON,
            weight_decay=WEIGHT_DECAY,
            fused=True,
        )
        torch.cuda.reset_peak_memory_stats(local_rank)
        dist.barrier()
        started = time.perf_counter()
        with torch.autocast("cuda", dtype=torch.bfloat16):
            loss = model(**batch).loss
        finite_loss = torch.isfinite(loss.detach()).to(dtype=torch.int32)
        dist.all_reduce(finite_loss, op=dist.ReduceOp.MIN)
        if int(finite_loss.item()) != 1:
            raise RuntimeError("smoke produced non-finite loss on at least one rank")
        loss.backward()
        optimizer.step()
        torch.cuda.synchronize(local_rank)
        elapsed = torch.tensor(
            [time.perf_counter() - started], device=f"cuda:{local_rank}", dtype=torch.float64
        )
        peak = torch.tensor(
            [torch.cuda.max_memory_allocated(local_rank)],
            device=f"cuda:{local_rank}",
            dtype=torch.float64,
        )
        tokens = batch["attention_mask"].sum().to(dtype=torch.float64).reshape(1)
        dist.reduce(elapsed, dst=0, op=dist.ReduceOp.MAX)
        dist.reduce(peak, dst=0, op=dist.ReduceOp.MAX)
        dist.reduce(tokens, dst=0, op=dist.ReduceOp.SUM)
        if rank == 0:
            peak_gb = float(peak.item()) / (1024**3)
            throughput = float(tokens.item()) / max(float(elapsed.item()), 1e-9)
            steps_per_epoch = math.ceil(
                len(dataset["train"]) / (WORLD_SIZE * INITIAL_BATCH_SIZE)
            )
            projected_minutes = float(elapsed.item()) * steps_per_epoch * EPOCHS / 60.0
            if peak_gb > 72.0:
                raise RuntimeError(f"smoke peak VRAM {peak_gb:.2f} GB exceeds 90% of A100 capacity")
            if projected_minutes > 180.0:
                raise RuntimeError(
                    f"smoke projects {projected_minutes:.1f} training minutes, above the 180-minute ceiling"
                )
            delta_metric(
                smoke_loss=f"{float(loss.detach()):.4f}",
                smoke_peak_vram_gb=f"{peak_gb:.2f}",
                smoke_throughput_tok_s=f"{throughput:.1f}",
                smoke_step_seconds=f"{float(elapsed.item()):.3f}",
                projected_hero_minutes=f"{projected_minutes:.1f}",
            )
            delta_progress(5, "smoke passed: one rank-64 batch per rank at hero batch size")
            smoke_elapsed = float(elapsed.item())
    finally:
        if dist.is_initialized():
            dist.destroy_process_group()
    if rank == 0:
        delta_smoke_done(f"{smoke_elapsed:.3f}s")


def main() -> None:
    started_wall = time.perf_counter()
    started = utc_now()
    rank = int(os.environ.get("RANK", "-1"))
    is_smoke = "--smoke" in sys.argv[1:]
    if rank == 0 and not is_smoke:
        delta_start()
    try:
        import torch

        if rank < 0 or "LOCAL_RANK" not in os.environ or "WORLD_SIZE" not in os.environ:
            raise RuntimeError("launch R007 with torchrun --nproc_per_node=4")
        visible_gpus = torch.cuda.device_count()
        if visible_gpus < WORLD_SIZE:
            raise RuntimeError(
                f"DDP requires {WORLD_SIZE} GPUs but only {visible_gpus} are visible"
            )
        if is_smoke:
            smoke_worker()
            return
        validate_r006_data()
        if rank == 0:
            delta_progress(10, "validated and loaded the immutable R006 split contract")
        train_worker(started, started_wall)
        elapsed = time.perf_counter() - started_wall
        if rank == 0:
            delta_done(f"{elapsed:.1f}s")
    except Exception as error:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        rank_label = rank if rank >= 0 else "launcher"
        with (LOG_DIR / f"stderr-rank-{rank_label}.log").open(
            "a", encoding="utf-8"
        ) as handle:
            handle.write(f"timestamp={utc_now()}\terror={error}\n")
            handle.write(traceback.format_exc())
            handle.write("\n")
        if rank == 0:
            with (LOG_DIR / "stderr.log").open("a", encoding="utf-8") as handle:
                handle.write(f"timestamp={utc_now()}\terror={error}\n")
                handle.write(traceback.format_exc())
                handle.write("\n")
            delta_blocker(f"{type(error).__name__}: {error}")
        raise


if __name__ == "__main__":
    main()
