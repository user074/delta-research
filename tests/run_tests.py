#!/usr/bin/env python3
"""
Automated tests for the research loop agent.

Validates that the agent produces correct outputs at each stage:
  1. Initialization: SYSTEM_PROFILE.md → INFRA.md
  2. Plan generation: STATE.md → PLAN.md
  3. Worker execution: PLAN.md → REPORT.md
  4. State compression: STATE.md + REPORT.md → updated STATE.md
  5. SLURM job generation: PLAN.md + INFRA.md → experiment.py + job.sh

Usage:
  python tests/run_tests.py                    # validate existing outputs
  python tests/run_tests.py --run              # generate isolated outputs with Astra/Sol, then validate
  python tests/run_tests.py --run --agent claude # use Claude/Sonnet instead
  python tests/run_tests.py --review           # LLM reviews outputs against templates
  python tests/run_tests.py --debug            # show parsed data for debugging
"""

import re
import sys
import subprocess
import argparse
import json
import math
from agent_harness import prepare_workspace, execute, review_verdict, OUTPUTS
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"
SUPERVISOR = ROOT / "templates" / "SUPERVISOR.md"

DEBUG = False
EVALUATION = None
OPTIONS = None

# ---------------------------------------------------------------------------
# Markdown parsing helpers
# ---------------------------------------------------------------------------

def extract_sections(text: str) -> dict[str, str]:
    """Split markdown into {heading: content} dict."""
    sections = {}
    current = None
    lines = []
    for line in text.split("\n"):
        m = re.match(r"^(#{1,3})\s+(.+)", line)
        if m:
            if current:
                sections[current] = "\n".join(lines)
            current = m.group(2).strip()
            lines = []
        else:
            lines.append(line)
    if current:
        sections[current] = "\n".join(lines)
    return sections


def find_table(text: str, header_pattern: str) -> list[dict]:
    """Find and parse a markdown table by matching its header row.

    This is more robust than heading-based lookup — it finds the table
    regardless of what section heading the agent used.
    """
    lines = text.split("\n")
    rows = []
    in_table = False
    headers = []

    for line in lines:
        stripped = line.strip()
        if not in_table and re.search(header_pattern, stripped):
            in_table = True
            headers = [h.strip() for h in stripped.strip("|").split("|")]
            continue
        if in_table:
            if re.match(r"\s*\|[\s\-:|]+\|\s*$", stripped):
                continue
            if stripped.startswith("|") and stripped.endswith("|"):
                cells = [c.strip() for c in stripped.strip("|").split("|")]
                if len(cells) == len(headers):
                    rows.append(dict(zip(headers, cells)))
                elif cells:
                    # Tolerate minor column count mismatches
                    padded = cells + [""] * (len(headers) - len(cells))
                    rows.append(dict(zip(headers, padded[:len(headers)])))
            else:
                if rows or (not stripped.startswith("<!--") and stripped):
                    in_table = False
    if DEBUG and rows:
        print(f"  [debug] find_table({header_pattern!r}): {len(rows)} rows, headers={headers}")
    if DEBUG and not rows:
        print(f"  [debug] find_table({header_pattern!r}): NO ROWS FOUND")
    return rows


def extract_meta_field(text: str, field: str) -> str:
    m = re.search(rf"\*\*{re.escape(field)}\*\*:\s*(.+)", text)
    return m.group(1).strip() if m else ""


# ---------------------------------------------------------------------------
# Test result tracking
# ---------------------------------------------------------------------------

class TestResult:
    def __init__(self, name: str):
        self.name = name
        self.checks: list[tuple[str, bool, str]] = []

    def check(self, name: str, condition: bool, detail: str = ""):
        self.checks.append((name, condition, detail))

    def passed(self) -> int:
        return sum(1 for _, ok, _ in self.checks if ok)

    def failed(self) -> int:
        return sum(1 for _, ok, _ in self.checks if not ok)

    def print_report(self):
        print(f"\n{'='*60}")
        print(f"  {self.name}")
        print(f"{'='*60}")
        for name, ok, detail in self.checks:
            status = "\033[32mPASS\033[0m" if ok else "\033[31mFAIL\033[0m"
            line = f"  [{status}] {name}"
            if detail and not ok:
                line += f"\n         {detail}"
            print(line)
        total = len(self.checks)
        print(f"\n  {self.passed()}/{total} passed")


# ---------------------------------------------------------------------------
# Table header patterns (match the header row of each table type)
# ---------------------------------------------------------------------------

# These patterns match the header row of each table, not section headings.
# This makes parsing robust to different heading styles.
LEDGER_PATTERN = r"Run\s*\|.*Question\s*\|.*Conclusion"
BELIEF_PATTERN = r"#\s*\|.*Belief\s*\|.*Confidence"
FRONTIER_PATTERN = r"Rank\s*\|.*Experiment question"
METRICS_PATTERN = r"Metric\s*\|.*Baseline"
GPU_TABLE_PATTERN = r"Index\s*\|.*Model\s*\|.*VRAM"
ACCELERATOR_PATTERN = r"Package\s*\|.*Version"


# ---------------------------------------------------------------------------
# Test 0: Initialization (INFRA.md generation)
# ---------------------------------------------------------------------------

def validate_infra(infra_path: Path, profile_path: Path) -> TestResult:
    r = TestResult("Initialization (INFRA)")

    if not infra_path.exists():
        r.check("Output file exists", False, f"Not found: {infra_path}")
        return r
    r.check("Output file exists", True)

    infra = infra_path.read_text()
    sections = extract_sections(infra)
    section_names_lower = {s.lower() for s in sections.keys()}

    # --- Required sections ---
    for required in ["GPUs", "CPU", "Memory", "Precision", "Attention", "Compilation",
                      "Parallelism", "Data Loading", "GPU-CPU Transfer Pitfalls",
                      "Training Efficiency", "Installed Accelerators", "Paths",
                      "Profiling Source"]:
        found = any(required.lower() in s for s in section_names_lower)
        r.check(f"Has section: {required}", found)

    # --- GPU table has rows matching the profile (4x A100) ---
    gpu_table = find_table(infra, GPU_TABLE_PATTERN)
    r.check(
        "GPU table has rows",
        len(gpu_table) >= 1,
        f"Found {len(gpu_table)} GPU rows"
    )

    # GPU table mentions A100
    gpu_text = " ".join(str(row) for row in gpu_table)
    r.check(
        "GPU table identifies A100",
        "A100" in gpu_text or "a100" in gpu_text.lower(),
        "Profile has 4x A100 — table should reflect this"
    )

    # --- Precision: should recommend BF16 for A100 (cc 8.0) ---
    precision_text = ""
    for key, val in sections.items():
        if "precision" in key.lower():
            precision_text = val.lower()
    r.check(
        "Precision recommends BF16",
        "bf16" in precision_text or "bfloat16" in precision_text,
        "A100 (cc 8.0) should use BF16"
    )

    # Should NOT recommend FP16 as primary (FP16 is for V100/T4)
    # Allow mentioning FP16 in passing, but "recommended" should be BF16
    rec_match = re.search(r"\*\*recommended\*\*:\s*(.+)", infra, re.IGNORECASE)
    if rec_match:
        rec_val = rec_match.group(1).lower()
        r.check(
            "Precision primary recommendation is not FP16",
            "fp16" not in rec_val,
            f"Got: {rec_val} — should be BF16 for A100"
        )
    else:
        r.check("Precision primary recommendation is not FP16", True, "No explicit recommendation field found — checked in section text")

    # --- Attention: flash-attn NOT installed, should recommend SDPA and note flash-attn opportunity ---
    attention_text = ""
    for key, val in sections.items():
        if "attention" in key.lower() and "flash" not in key.lower().replace("attention", ""):
            attention_text = val.lower()
    r.check(
        "Attention recommends SDPA (flash-attn not installed)",
        "sdpa" in attention_text or "scaled_dot_product" in attention_text,
        "flash-attn not installed — should recommend SDPA as current mechanism"
    )

    # Should mention flash-attn as upgrade opportunity
    r.check(
        "Attention notes flash-attn upgrade opportunity",
        "flash" in attention_text and ("install" in attention_text or "not installed" in attention_text or "upgrade" in attention_text),
        "cc 8.0 supports FA2 but flash-attn not installed — should note this"
    )

    # --- Compilation: mentions torch.compile ---
    compilation_text = ""
    for key, val in sections.items():
        if "compil" in key.lower():
            compilation_text = val.lower()
    r.check(
        "Compilation mentions torch.compile",
        "torch.compile" in compilation_text or "compile" in compilation_text,
        "PyTorch 2.4 available — should mention torch.compile"
    )

    # --- Parallelism: should recommend DDP for 4 GPUs ---
    parallelism_text = ""
    for key, val in sections.items():
        if "parallelism" in key.lower():
            parallelism_text = val.lower()
    r.check(
        "Parallelism recommends DDP",
        "ddp" in parallelism_text or "distributeddataparallel" in parallelism_text,
        "4 GPUs with NVLink — should recommend DDP"
    )

    # Should include torchrun launch command
    r.check(
        "Parallelism includes torchrun command",
        "torchrun" in parallelism_text,
        "DDP should specify torchrun launch command"
    )
    r.check(
        "INFRA records the human-confirmed GPU count",
        "human-confirmed gpu count" in infra.lower() and re.search(r"human-confirmed gpu count\*\*:\s*4", infra.lower()) is not None,
        "Detected GPUs and approved experiment allocation are different facts"
    )
    r.check(
        "DDP outranks tensor parallelism when a replica fits",
        "ddp is the fastest default when the model fits" in parallelism_text
        and "tensor parallel fallback" in parallelism_text
        and "forbidden while one" in parallelism_text,
        "Four A100s should use DDP unless a concrete single-GPU fit constraint prevents it"
    )
    r.check(
        "All confirmed GPUs receive useful work",
        "all-gpu work rule" in parallelism_text
        and "every confirmed gpu" in parallelism_text
        and "per-rank" in parallelism_text,
        "Useful work and lightweight in-run evidence should cover every approved GPU"
    )

    # --- Data Loading section has key fields ---
    data_loading_text = ""
    for key, val in sections.items():
        if "data loading" in key.lower():
            data_loading_text = val.lower()
    dl_keywords = ["pin_memory", "num_workers", "prefetch"]
    found_dl = [kw for kw in dl_keywords if kw in data_loading_text]
    r.check(
        "Data Loading has key fields",
        len(found_dl) >= 2,
        f"Found: {found_dl}, expected at least 2 of {dl_keywords}"
    )

    # --- GPU-CPU Transfer Pitfalls mentions .item() ---
    transfer_text = ""
    for key, val in sections.items():
        if "transfer" in key.lower() or "pitfall" in key.lower():
            transfer_text = val
    r.check(
        "GPU-CPU pitfalls mentions .item()",
        ".item()" in transfer_text,
        "Should warn against .item() in training loops"
    )

    # --- Training Efficiency section has content ---
    efficiency_text = ""
    for key, val in sections.items():
        if "training efficiency" in key.lower() or "efficiency" in key.lower():
            efficiency_text = val.lower()
    r.check(
        "Training Efficiency has fused optimizer guidance",
        "fused" in efficiency_text,
        "PyTorch 2.4 supports fused AdamW — should mention it"
    )

    # --- Installed Accelerators table ---
    accel_table = find_table(infra, ACCELERATOR_PATTERN)
    r.check(
        "Installed Accelerators table has rows",
        len(accel_table) >= 4,
        f"Found {len(accel_table)} rows (profile has 8+ packages)"
    )

    # flash-attn should show "not installed" (matching the profile)
    flash_row = [row for row in accel_table if "flash" in str(row).lower()]
    if flash_row:
        flash_ver = str(flash_row[0]).lower()
        r.check(
            "Accelerators: flash-attn correctly shows not installed",
            "not installed" in flash_ver,
            f"Profile has flash-attn not installed — should reflect this"
        )
    else:
        r.check("Accelerators: flash-attn correctly shows not installed", False, "flash-attn row not found")

    # deepspeed should show its version (it IS installed)
    ds_row = [row for row in accel_table if "deepspeed" in str(row).lower()]
    if ds_row:
        ds_ver = str(ds_row[0]).lower()
        r.check(
            "Accelerators: deepspeed shows installed version",
            "not installed" not in ds_ver and "0.14" in ds_ver,
            f"Profile has deepspeed 0.14.0 — should show version"
        )
    else:
        r.check("Accelerators: deepspeed shows installed version", False, "deepspeed row not found")

    # --- Storage paths table ---
    storage_table = find_table(infra, r"Purpose\s*\|.*Path")
    r.check(
        "Storage paths table has rows",
        len(storage_table) >= 2,
        f"Found {len(storage_table)} storage path rows"
    )

    # Should identify NFS for /data
    storage_text = " ".join(str(row) for row in storage_table)
    r.check(
        "Storage identifies NFS mount",
        "nfs" in storage_text.lower() or "network" in storage_text.lower(),
        "/data is NFS-mounted — should be identified"
    )

    # --- Profiling source ---
    profiling_text = ""
    for key, val in sections.items():
        if "profiling" in key.lower() and "source" in key.lower():
            profiling_text = val.lower()
    r.check(
        "Profiling Source section is filled",
        len(profiling_text.strip()) > 20,
        "Should record method, date, and host"
    )

    # --- Recommended Optimizations ---
    has_rec_section = any("recommend" in s and "optim" in s for s in section_names_lower)
    r.check("Has section: Recommended Optimizations", has_rec_section)

    # Should have an optimization table with rows
    opt_table = find_table(infra, r"#\s*\|.*Optimization\s*\|.*Command")
    r.check(
        "Recommended Optimizations table has rows",
        len(opt_table) >= 1,
        f"Found {len(opt_table)} optimization rows (profile has flash-attn and triton missing)"
    )

    # Should recommend installing flash-attn (cc 8.0 but not installed)
    opt_text = " ".join(str(row) for row in opt_table).lower()
    r.check(
        "Recommends installing flash-attn",
        "flash" in opt_text,
        "A100 (cc 8.0) supports FA2 but flash-attn not installed — should recommend it"
    )

    # Should recommend installing triton (torch.compile available but triton missing)
    r.check(
        "Recommends installing triton",
        "triton" in opt_text,
        "torch.compile available but triton not installed — should recommend it"
    )

    # Each recommendation should have a command
    if opt_table:
        has_commands = all(
            row.get("Command", "").strip()
            for row in opt_table
        )
        r.check(
            "Each recommendation has a concrete command",
            has_commands,
            "Recommendations should include runnable commands (pip install, etc.)"
        )

    return r


# ---------------------------------------------------------------------------
# Test 0b: SLURM job generation (experiment.py + job.sh)
# ---------------------------------------------------------------------------

def validate_slurm_job(exp_path: Path, job_path: Path, plan_path: Path, infra_path: Path) -> TestResult:
    r = TestResult("SLURM Job Generation")
    smoke_job_path = job_path.with_name("output_smoke_job.sh")

    # --- experiment.py ---
    if not exp_path.exists():
        r.check("experiment.py exists", False, f"Not found: {exp_path}")
    else:
        r.check("experiment.py exists", True)
        exp = exp_path.read_text()

        # DELTA markers
        for marker in ["DELTA-START", "DELTA-PROGRESS", "DELTA-DONE"]:
            r.check(
                f"experiment.py has [{marker}]",
                f"[{marker}]" in exp,
                f"Missing {marker} marker — required by OBSERVABILITY"
            )
        r.check(
            "experiment.py has distinct smoke-success marker",
            "[DELTA-SMOKE-DONE]" in exp,
            "Smoke must authorize hero execution without completing the research run"
        )

        # Error handling with DELTA-BLOCKER
        r.check(
            "experiment.py has DELTA-BLOCKER error handling",
            "[DELTA-BLOCKER]" in exp,
            "Must have DELTA-BLOCKER for fatal errors"
        )

        # flush=True
        r.check(
            "experiment.py uses flush=True",
            "flush=True" in exp,
            "All DELTA marker prints must use flush=True for SLURM buffering"
        )

        # Full logging
        r.check(
            "experiment.py has full logging setup",
            "logs" in exp and ("train.log" in exp or "log_step" in exp or "ExperimentLogger" in exp),
            "Must write full logs to RUNS/R###/logs/ (see OBSERVABILITY.md)"
        )
        r.check(
            "experiment.py writes metrics JSON",
            "json" in exp.lower() and ("training_history" in exp or "eval_results" in exp or "metrics" in exp),
            "Must write structured metrics to RUNS/R###/metrics/"
        )
        r.check(
            "experiment.py evaluates the exact rank-16 checkpoint",
            'RANK16_CHECKPOINT = Path("/scratch/researcher/checkpoints/R006/lora_r16")' in exp
            and "evaluate_adapter_checkpoint(\n        RANK16_CHECKPOINT" in exp,
            "The comparison arm must be measured from the exact R006 checkpoint on the current split"
        )
        r.check(
            "experiment.py rejects missing baseline metrics",
            "required_numeric_metric" in exp and "missing required measured metric" in exp,
            "Do not replace absent R006 measurements with plausible-looking constants"
        )
        r.check(
            "experiment.py does not retry a partial DDP job after OOM",
            "retrying once" not in exp and "FALLBACK_BATCH_SIZE" not in exp,
            "A failed DDP launch must terminate; retry only via a fresh amended job"
        )
        r.check(
            "experiment.py uses all ranks for evaluation",
            "local_indices = list(range(rank, len(eval_dataset), world_size))" in exp
            and "dist_module.all_reduce" in exp
            and "all four ranks evaluating both adapters" in exp
            and "rank-zero-only full evaluation" not in exp,
            "Do not idle three confirmed GPUs after DDP training"
        )
        r.check(
            "experiment.py records useful work on every rank",
            "per_rank_train_batches" in exp
            and "per_rank_eval_examples" in exp
            and "wall_clock_seconds" in exp
            and "4/4 confirmed GPUs did useful work" in exp,
            "The real job should prove work distribution and time-to-answer without a separate audit"
        )

        # wandb integration
        r.check(
            "experiment.py has wandb.init",
            "wandb.init(" in exp,
            "Must initialize wandb for experiment tracking"
        )
        r.check(
            "experiment.py has wandb.log",
            "wandb.log(" in exp,
            "Must log metrics to wandb"
        )
        r.check(
            "experiment.py has wandb.finish",
            "wandb.finish()" in exp,
            "Must call wandb.finish() for clean shutdown"
        )

    # --- job.sh ---
    if not job_path.exists():
        r.check("job.sh exists", False, f"Not found: {job_path}")
    else:
        r.check("job.sh exists", True)
        job = job_path.read_text()

        # Read plan and infra for cross-reference
        plan = plan_path.read_text() if plan_path.exists() else ""
        infra = infra_path.read_text() if infra_path.exists() else ""

        # SBATCH directives
        r.check(
            "job.sh has #SBATCH directives",
            "#SBATCH" in job,
            "Must have SLURM directives"
        )

        # Partition matches plan
        plan_partition = "gpu"  # from fixture
        r.check(
            "job.sh partition matches plan",
            f"--partition={plan_partition}" in job or f"--partition {plan_partition}" in job,
            f"Plan specifies partition={plan_partition}"
        )

        # GPUs match plan
        r.check(
            "job.sh has GPU allocation",
            "--gpus-per-node=4" in job or "--gres=gpu:4" in job,
            "Must allocate all four human-confirmed GPUs"
        )

        # Walltime
        r.check(
            "job.sh has walltime",
            "--time" in job,
            "Must specify walltime"
        )

        # Output path includes run ID
        r.check(
            "job.sh output path includes R007",
            "R007" in job and "--output" in job,
            "Output should go to RUNS/R007/slurm-%j.out"
        )
        r.check(
            "job.sh output path is absolute",
            "#SBATCH --output=/home/researcher/llm-finetune/RUNS/R007/slurm-%j.out" in job,
            "SBATCH resolves paths before shell cd; use the exact project-root path"
        )

        # Module loads from INFRA
        r.check(
            "job.sh has module loads",
            "module load" in job,
            "Must load modules from INFRA.md"
        )

        # Validated env activation — accept any of the supported env managers
        # (conda/mamba: absolute conda.sh or absolute conda binary;
        #  uv/venv: source .../bin/activate or PATH=.../bin;
        #  pixi: shell-hook)
        has_conda_abs = (
            "/opt/conda" in job
            or "conda activate /" in job
            or "source /" in job and "conda.sh" in job
            or "/conda/bin/conda activate" in job
        )
        has_venv_activate = (
            "/bin/activate" in job  # uv or plain venv
            or ".venv/bin/activate" in job
        )
        has_pixi = "pixi shell-hook" in job
        has_validated_env = has_conda_abs or has_venv_activate or has_pixi
        r.check(
            "job.sh uses validated env activation",
            has_validated_env,
            "Must use validated env path from INFRA.md — absolute conda activation, "
            "source <abs>/.venv/bin/activate (uv/venv), or pixi shell-hook. "
            "Not bare 'conda activate <name>'."
        )

        # wandb env vars
        r.check(
            "job.sh sets WANDB_PROJECT",
            "WANDB_PROJECT" in job,
            "Must set WANDB_PROJECT env var"
        )
        r.check(
            "job.sh sets WANDB_MODE",
            "WANDB_MODE" in job,
            "Must set WANDB_MODE env var"
        )

        # Launches experiment.py
        r.check(
            "job.sh launches experiment.py",
            "experiment.py" in job,
            "Must run python RUNS/R007/experiment.py"
        )
        r.check(
            "job.sh launches experiment.py by absolute path",
            "torchrun --standalone --nproc_per_node=4 /home/researcher/llm-finetune/RUNS/R007/experiment.py" in job,
            "The launch must not depend on sbatch's submission directory"
        )
        smoke_job = smoke_job_path.read_text() if smoke_job_path.exists() else ""
        r.check("job_smoke.sh exists", smoke_job_path.exists(), f"Not found: {smoke_job_path}")
        r.check(
            "job_smoke.sh uses a bounded four-GPU R007 smoke launch",
            "#SBATCH --time=00:15:00" in smoke_job
            and "#SBATCH --gpus-per-node=4" in smoke_job
            and "R007/slurm-smoke-%j.out" in smoke_job
            and "torchrun --standalone --nproc_per_node=4" in smoke_job
            and "experiment.py --smoke" in smoke_job,
            "Smoke must be a cheap job under the same run ID and hero process shape"
        )
        r.check(
            "launcher translates any-rank failure to BLOCKER",
            "hero torchrun failed on at least one rank" in job
            and "smoke torchrun failed on at least one rank" in smoke_job,
            "The shell launcher must emit a terminal marker even when a nonzero rank fails first"
        )

    return r


# ---------------------------------------------------------------------------
# Test 1: Plan generation
# ---------------------------------------------------------------------------

def validate_plan(plan_path: Path, state_path: Path) -> TestResult:
    r = TestResult("Plan Generation")

    if not plan_path.exists():
        r.check("Output file exists", False, f"Not found: {plan_path}")
        return r
    r.check("Output file exists", True)

    plan = plan_path.read_text()
    sections = extract_sections(plan)
    section_names = set(sections.keys())

    # Required sections
    for required in ["Question and finish line", "Evidence package", "Method and resources", "Prediction",
                     "Bounds", "Working notes", "Meta"]:
        found = any(required.lower() in s.lower() for s in section_names)
        r.check(f"Has section: {required}", found)

    # Start from one concrete command; a minimum step count invites padded planning.
    first_command = re.search(r"\*\*first command(?::)?\*\*(?::)?\s*`([^`]+)`", plan, re.IGNORECASE)
    r.check(
        "Has an executable first command",
        first_command is not None and "shortest command" not in first_command.group(1).lower(),
        "The working guide should start useful work immediately"
    )

    # Resources section has actual paths (not just placeholders)
    resources_text = ""
    for key, val in sections.items():
        if "resource" in key.lower():
            resources_text = val
    has_paths = bool(re.search(r"(/[\w/.-]+|data/|RUNS/|artifacts/)", resources_text))
    r.check("Resources section has actual paths", has_paths)

    progress_text = ""
    for key, val in sections.items():
        if "question and finish line" in key.lower():
            progress_text = val
    r.check(
        "Plan names one hypothesis question",
        "hypothesis" in progress_text.lower() and "primary question" in progress_text.lower(),
        "The run should answer one named hypothesis question"
    )
    r.check(
        "Plan states support and contradiction",
        "support / contradict" in progress_text.lower(),
        "The plan must say how either result changes the answer"
    )
    r.check(
        "Plan states complete evidence and ETA",
        "minimum complete evidence" in progress_text.lower() and "eta to answer" in progress_text.lower(),
        "The test must be adequate before speed is optimized"
    )
    package = sections.get("Evidence package", "")
    r.check(
        "Plan keeps the coherent experiment together",
        all(term in package.lower() for term in
            ("main comparison", "repetitions / coverage", "required controls or ablations")),
        "Baseline, treatment, repetitions, and necessary controls must share one run"
    )
    r.check(
        "Skips the legacy no-progress frontier item",
        "audit all benchmark scripts" not in plan.lower()
        and "survey alternative profiling methods" not in plan.lower(),
        "Direct work must outrank a superficially thorough audit"
    )

    r.check(
        "Chooses fastest adequate direct test",
        bool(re.search(r"\*\*hypothesis(?::)?\*\*(?::)?\s*#3", plan, re.IGNORECASE)) and "8 minutes" in plan.lower()
        and "allocation-plus-copy" not in plan.lower(),
        "The 8-minute #3 test should outrank the 25-minute #2 test after both can answer their questions"
    )

    r.check(
        "Plan is concise",
        len(re.findall(r"\b\w+\b", plan)) <= 600,
        "A working guide should remain under 600 words including commands"
    )
    r.check(
        "Plan has no amendment bureaucracy",
        "PLAN.initial.md" not in plan and "AMENDMENT_NEEDED" not in plan
        and "Class A" not in plan and "Amendment Log" not in plan,
        "The plan must stay editable without copies, classes, or approvals"
    )
    r.check(
        "Plan explicitly permits adaptation",
        "adapt freely" in plan.lower() and "without approval" in plan.lower()
    )
    r.check(
        "Plan stops at sufficient evidence",
        "complete the evidence package" in plan.lower()
        and "supports, contradicts, or cannot decide" in plan.lower()
    )
    r.check(
        "Plan states accelerator layout and wall-clock target",
        all(term in resources_text.lower() for term in
            ("parallel strategy", "utilization plan", "expected wall-clock")),
        "The working plan should make useful device placement and time-to-result explicit"
    )

    return r


# ---------------------------------------------------------------------------
# Test 2: Worker execution (report validation)
# ---------------------------------------------------------------------------

def validate_report(report_path: Path) -> TestResult:
    r = TestResult("Worker Execution (Report)")

    if not report_path.exists():
        r.check("Output file exists", False, f"Not found: {report_path}")
        return r
    r.check("Output file exists", True)

    report = report_path.read_text()
    sections = extract_sections(report)
    section_names_lower = {s.lower() for s in sections.keys()}

    # Required compact-paper sections. Ablations are optional.
    for required in ["Answer", "Motivation", "Questions tested", "Method", "Experiments", "Results",
                     "Analysis", "Limitations and tested scope", "Conclusion", "Reproducibility", "Meta"]:
        found = any(required.lower() in s for s in section_names_lower)
        r.check(f"Has section: {required}", found)

    # Answer is present, concrete, and short.
    summary = sections.get("Answer", "").strip()
    summary_words = re.findall(r"\b\w+\b", summary)
    r.check(
        "Answer is direct and concise",
        20 < len(summary) and len(summary_words) <= 80
        and any(term in summary.lower() for term in ("supports", "contradicts", "cannot decide", "cannot yet decide")),
        f"Answer has {len(summary_words)} words"
    )

    internal_jargon = ["delta", "frontier", "evidence floor", "paradigm", "unblocker",
                       "belief movement", "discriminating signal"]
    r.check(
        "Answer avoids internal jargon",
        not any(term in summary.lower() for term in internal_jargon) and bool(re.search(r"\d", summary)),
        "The opening should use a concrete number and no loop-internal vocabulary"
    )

    questions = sections.get("Questions tested", "")
    r.check(
        "Report has one primary question",
        "primary" in questions.lower() and any(term in questions.lower() for term in ("support", "contradict")),
        "The report must state one question and its decision threshold"
    )

    method = sections.get("Method", "")
    r.check(
        "Method states the scientific design",
        all(term in method.lower() for term in ("approach", "data", "comparisons", "metrics", "repetitions", "environment")),
        "Approach, data, comparisons, metrics, repetitions, and environment are required"
    )
    r.check(
        "Method states the parallel execution layout",
        "parallel execution" in method.lower(),
        "Reports must make the confirmed device count and execution strategy visible"
    )

    experiments = sections.get("Experiments", "")
    r.check(
        "Experiments form a coherent evidence package",
        "main" in experiments.lower() and "comparison" in experiments.lower() and "|" in experiments,
        "The report should show the main comparison and any necessary control/ablation together"
    )

    # Inline data — tables in the Results section or Data subsection
    results_text = ""
    for key, val in sections.items():
        if "result" in key.lower() or "data" in key.lower():
            results_text += val
    has_inline_tables = "|" in results_text
    r.check("Results has inline data tables", has_inline_tables)
    r.check(
        "Results states wall-clock and GPU use",
        "wall-clock to answer" in results_text.lower()
        and "gpu use, if applicable" in results_text.lower(),
        "Time-to-answer and useful-device evidence belong inside the real result"
    )

    # Visualizations are optional and bounded; plots must not become default post-processing.
    image_refs = re.findall(r"!\[.*?\]\(.*?\)", report)
    r.check(
        "Uses at most one visualization",
        len(image_refs) <= 1,
        f"Found {len(image_refs)} image embeds (expected 0 or 1)"
    )

    # Analysis section exists and has content
    analysis = ""
    for key, val in sections.items():
        if "analysis" in key.lower():
            analysis = val.strip()
    r.check(
        "Analysis justifies the conclusion",
        len(analysis) > 20,
        f"Analysis section has {len(analysis)} chars (expected >20)"
    )

    conclusion = sections.get("Conclusion", "")
    r.check(
        "Conclusion answers the hypothesis",
        any(v in conclusion.lower() for v in ("supports", "contradicts", "cannot decide"))
        and bool(re.search(r"(?:belief|hypothesis)?\s*#\d+", conclusion, re.IGNORECASE))
        and "decisive evidence" in conclusion.lower(),
        "Conclusion needs an answer, belief reference, and decisive evidence"
    )
    r.check(
        "Report does not manufacture new directions",
        "## New hypotheses" not in report and "## Next tests" not in report,
        "Only one same-question next experiment belongs inside Conclusion"
    )
    reproducibility = sections.get("Reproducibility", "")
    r.check(
        "Reproducibility records parallelism",
        "parallelism" in reproducibility.lower(),
        "The launcher, world size, and batch/condition assignment should be reproducible"
    )

    return r


# ---------------------------------------------------------------------------
# Framework contract: experimental progress + GitHub publication
# ---------------------------------------------------------------------------

def validate_framework_contracts() -> TestResult:
    r = TestResult("Framework Contracts (Real Work + Plans + GitHub)")
    templates = ROOT / "templates"
    supervisor = (templates / "SUPERVISOR.md").read_text()
    state = (templates / "STATE.template.md").read_text()
    plan = (templates / "PLAN.template.md").read_text()
    report = (templates / "REPORT.template.md").read_text()
    blocker = (templates / "BLOCKER.template.md").read_text()
    synthesis = (templates / "SYNTHESIS.template.md").read_text()
    init = (templates / "INIT.md").read_text()
    observability = (templates / "OBSERVABILITY.md").read_text()
    waiter = (ROOT / "scripts/wait_for_job.sh").read_text()
    runner_source = Path(__file__).read_text()
    literature_path = templates / "LITERATURE.template.md"
    literature = literature_path.read_text() if literature_path.exists() else ""

    r.check("Supervisor defines one run as one answer",
            "One run, one answer" in supervisor
            and "coherent evidence package for one scientific question" in supervisor)
    r.check("Supervisor rejects fake-work run types",
            "Generic literature review, experiment surveys, audits, gates" in supervisor
            and "are not research runs" in supervisor)
    r.check("Partial conditions cannot become runs",
            "A baseline, single seed, one configuration, smoke check, plot, or ablation" in supervisor
            and "not a completed run" in supervisor)
    r.check("Related experiment stages share one ID",
            "Do not split these into new run IDs" in supervisor
            and "multiple commands or SLURM jobs inside one R###" in supervisor)
    r.check("Blocked attempts do not spam runs",
            "`RUNS/R###/BLOCKER.md`" in supervisor
            and "Do not write `REPORTS/R###.md`, append" in supervisor
            and "consume another run ID" in supervisor)
    r.check("Blocked run IDs are resumed, not replaced",
            "That is a pending experiment" in supervisor
            and "resume the same plan, worker, and ID" in supervisor
            and "never allocate a new ID to step around it" in supervisor)
    r.check("Blocked attempts use a non-report scaffold",
            "This is an execution note, not a research report or completed run" in blocker
            and "repairs attempted" in blocker
            and "resume command" in blocker
            and "No `REPORTS/R###.md`" in blocker)
    r.check("Supporting work is bounded inside a run",
            "smaller of 20% of its budget or 30 minutes" in supervisor)
    r.check("Smoke cannot complete a run",
            "smoke test and evidence package are one run" in supervisor.lower()
            and "Never write the final report" in supervisor)
    r.check("Smoke success is monitorable without run completion",
            "[DELTA-SMOKE-DONE]" in observability
            and "SMOKE_DONE" in waiter
            and "DELTA-SMOKE-DONE" in waiter)
    r.check("Successful jobs cannot close partial experiments",
            "`[DELTA-DONE]` does not by itself complete R###" in observability
            and "Only the complete evidence package permits" in observability)
    r.check("State ledger only records coherent experiments",
            "One row per completed, decision-capable experiment" in state
            and "| Run | Question | Key result | Conclusion | Belief | Link |" in state)
    r.check("State frontier stores complete evidence packages",
            "| Experiment question | Target | Decision result | Minimum complete evidence | ETA |" in state)
    r.check("Literature is recovery-only after direction failure",
            "One-shot literature direction recovery" in supervisor
            and "forbidden while any executable experiment" in supervisor
            and "At least one direct experiment has already failed scientifically" in supervisor)
    r.check("Literature recovery is strictly bounded",
            "Cap the\nsearch at 30 minutes and 8 relevant primary/official sources" in supervisor
            and "stop earlier after finding 3 executable direct" in supervisor)
    r.check("Literature recovery cannot repeat or become a gate",
            "Never run a second literature recovery until new experimental evidence" in supervisor
            and "never an experiment-eligibility gate" in supervisor)
    r.check("Literature cannot move beliefs",
            "Literature cannot update belief confidence" in literature
            and "belief confidence update**: none" in literature)
    r.check("Plan template defines a complete experiment",
            "## Question and finish line" in plan and "## Evidence package" in plan
            and "minimum complete evidence" in plan.lower() and "ETA to answer" in plan)
    r.check("Plan forbids splitting related conditions",
            "Do not split the baseline, treatment, seeds" in plan
            and "controls, ablations, smoke test, retry, plot, or analysis" in plan)
    r.check("Plan template keeps lookup inside execution",
            "technical lookup" in plan.lower() and "never scientific literature" in plan.lower())
    r.check("Report uses a compact paper scaffold",
            all(heading in report for heading in ("## Answer", "## Motivation", "## Questions tested",
                "## Method", "## Experiments", "## Results", "## Analysis",
                "## Limitations and tested scope", "## Conclusion", "## Reproducibility")))
    r.check("Ablations stay optional and in the same run",
            "## Ablations (optional)" in report and "Keep all related ablations in this run" in report)
    r.check("Supervisor requires Feynman-style communication",
            "Plain-English communication contract" in supervisor
            and "Answer first" in supervisor
            and "Never invent an acronym" in supervisor)
    r.check("Human summaries translate internal loop terms",
            "Translate loop internals" in supervisor
            and 'Say "experiment," "next' in supervisor
            and "confidence changed" in supervisor)
    r.check("Reports lead with a short answer and a number",
            "At most 80 words" in report
            and "First sentence says the result supports, contradicts, or cannot yet decide" in report
            and "decisive number" in report)
    r.check("Synthesis is answer-first and decision-focused",
            "## Answer so far" in synthesis and "## Best evidence" in synthesis
            and "## What could change this answer" in synthesis
            and "## Next step, only if needed" in synthesis
            and "## Technical details" in synthesis)
    r.check("Interrupts are short and plain",
            "at most 150 words" in supervisor
            and "answer/blocker first" in supervisor
            and "Translate the boundary" in supervisor)
    r.check("Report states exact tested scope",
            "Exact model/data/runtime/hardware scope" in report
            and "limitation or alternative explanation that could reverse" in report)
    r.check("Mandatory literature gate removed",
            "## Literature Grounding" not in plan and "| Literature |" not in state
            and "Each literature-review run grounds exactly one hypothesis" not in supervisor)
    r.check("Optional literature brief cannot gate experiments",
            "not an R### research run" in literature
            and re.search(r"does\s*>?\s*not block experiments", literature) is not None)

    r.check("Supervisor has mandatory Phase 6b",
            "Phase 6b: Curate, commit, and push" in supervisor)
    r.check("Git staging forbids blanket add",
            "Never use `git add .`, `git add -A`, or `git add --all`" in supervisor)
    r.check("Git publication uses non-default branch",
            "Use a non-default research branch" in supervisor)
    r.check("Git publication verifies remote",
            "Verify local HEAD equals the remote-tracking branch" in supervisor)
    r.check("Git failures forbid force push",
            "do not force-push" in supervisor)
    r.check("Initialization records publication authorization",
            "GitHub publication authorization" in init)

    r.check("Supervisor uses one editable working plan",
            "Write one `RUNS/R###/PLAN.md`" in supervisor
            and "Do not create `PLAN.initial.md`" in supervisor)
    r.check("Planning is strictly time and size bounded",
            "at most 5 minutes" in supervisor and "hard cap of 10 minutes" in supervisor
            and "under 400 words" in supervisor)
    r.check("Planning starts execution at minimal readiness",
            "Start execution as soon as the plan names" in supervisor
            and "the first executable command" in supervisor)
    r.check("Worker adapts plan without approval",
            "may edit `PLAN.md` directly at any time" in supervisor
            and "need no classification, approval, version bump, or log entry" in supervisor)
    r.check("Plan changes do not become blockers",
            "The plan guides work; it does not block work" in supervisor
            and "not because the plan changed" in supervisor)
    r.check("Scientific changes remain honest but lightweight",
            "one sentence stating when, what changed, why" in supervisor
            and "label the affected result exploratory" in supervisor)
    r.check("Plan template contains no amendment workflow",
            "## Working notes" in plan and "PLAN.initial.md" not in plan
            and "AMENDMENT_NEEDED" not in plan and "plan_version" not in plan)
    r.check("Report records scientific changes inside Method",
            "scientific changes during execution" in report and "affect interpretation" in report)
    r.check("Initialization teaches editable lightweight plans",
            "working guide, not an immutable contract" in init and "always ≤10 minutes" in init)
    r.check("Complete evidence precedes speed optimization",
            "Minimum decisive experiment" in supervisor
            and "Scientific adequacy is the floor" in supervisor
            and "choose the shortest total time to an answer" in supervisor)
    r.check("Time to result includes all latency",
            "setup + queue + all required conditions + analysis" in supervisor)
    r.check("Hardware optimization targets wall-clock time",
            "Shortest wall-clock hardware use" in supervisor
            and "GPU-hours are a\n  secondary accounting metric" in supervisor
            and "shortest total wall-clock time" in supervisor)
    r.check("Confirmed GPUs all do useful work",
            "if the human approved `N` GPUs, allocate exactly `N`" in supervisor
            and "Do not leave confirmed GPUs idle" in supervisor
            and "synthetic work" in supervisor)
    r.check("DDP is mandatory when a replica fits",
            "DDP first" in supervisor
            and "torchrun --nproc_per_node=N" in supervisor
            and "do not choose tensor parallelism when DDP can execute" in supervisor)
    r.check("Tensor parallelism requires a concrete constraint",
            "one replica cannot fit on one GPU" in supervisor
            and "required operation cannot be divided" in supervisor
            and "state that exact reason in the plan and report" in supervisor)
    r.check("Utilization evidence stays inside the experiment",
            "Useful utilization evidence, not a gate" in supervisor
            and "per-rank sample/batch count" in supervisor
            and "Do not create a separate utilization audit" in supervisor)
    r.check("Plan and report expose the GPU execution contract",
            "exact human-confirmed GPU count" in plan
            and "parallel strategy" in plan and "utilization plan" in plan
            and "wall-clock to answer" in report and "GPU use, if applicable" in report)
    r.check("Complete package is required before closing",
            "do not close the run until the\nminimum complete evidence is present" in supervisor
            and "Do not accept several trivial\nreports" in supervisor)
    r.check("Substantial does not mean padded",
            '"Substantial" means\ndecision-complete, not expensive or exhaustive' in supervisor
            and "do not pad the report" in supervisor)
    r.check("Controls and ablations require a verdict-changing reason",
            "controls and ablations needed to rule out an explanation that could reverse" in supervisor)
    r.check("Plots are optional and bounded",
            "Do not generate a plot by default" in supervisor
            and "Use at most one" in supervisor)
    r.check("Resolved target triggers GOAL",
            "| `GOAL` |" in supervisor and "Do not manufacture follow-up work" in supervisor)
    r.check("Loop does not grow beliefs to stay alive",
            "Do not grow the belief space merely to keep the loop alive" in supervisor
            and "does not automatically authorize a mechanism study" in supervisor)
    from agent_harness import command_for
    command = command_for("codex", "gpt-5.6-sol", "medium", ROOT)
    r.check("Codex runner explicitly routes model and effort",
            "--approve-for-me" in command and command[command.index("--model") + 1] == "gpt-5.6-sol"
            and 'model_reasoning_effort="medium"' in command)

    return r


# ---------------------------------------------------------------------------
# Test 3: State compression
# ---------------------------------------------------------------------------

def validate_state_compression(
    before_path: Path, after_path: Path, report_path: Path
) -> TestResult:
    r = TestResult("State Compression")

    if not after_path.exists():
        r.check("Output file exists", False, f"Not found: {after_path}")
        return r
    r.check("Output file exists", True)

    before = before_path.read_text()
    after = after_path.read_text()

    # Parse tables using header-row patterns (robust to heading variations)
    ledger_before = find_table(before, LEDGER_PATTERN)
    ledger_after = find_table(after, LEDGER_PATTERN)
    r.check(
        "Ledger has new row",
        len(ledger_after) > len(ledger_before),
        f"Before: {len(ledger_before)} rows, After: {len(ledger_after)} rows"
    )

    # New row contains R003
    new_rows = ledger_after[len(ledger_before):]
    has_r003 = any("R003" in str(row) for row in new_rows)
    r.check("New ledger row contains R003", has_r003)
    r.check(
        "New ledger row records a question and conclusion",
        any(row.get("Question", "").strip() and row.get("Key result", "").strip()
            and row.get("Conclusion", "").lower() in ("supports", "contradicts", "cannot decide")
            for row in new_rows),
        f"New rows: {new_rows}"
    )

    # Belief #3 confidence increased (was 0.45, report supports it)
    beliefs_before = find_table(before, BELIEF_PATTERN)
    beliefs_after = find_table(after, BELIEF_PATTERN)

    b3_before = next((b for b in beliefs_before if b.get("#") == "3"), None)
    b3_after = next((b for b in beliefs_after if b.get("#") == "3"), None)

    if b3_before and b3_after:
        try:
            conf_before = float(b3_before.get("Confidence", "0"))
            conf_after = float(b3_after.get("Confidence", "0"))
            r.check(
                "Belief #3 confidence increased",
                conf_after > conf_before,
                f"Before: {conf_before}, After: {conf_after}"
            )
        except ValueError:
            r.check("Belief #3 confidence increased", False, "Could not parse confidence values")
    else:
        r.check("Belief #3 confidence increased", False,
                f"Belief #3 not found (before: {len(beliefs_before)} beliefs, after: {len(beliefs_after)} beliefs)")

    # A decided question must not manufacture follow-up beliefs merely to keep cycling.
    r.check(
        "No unnecessary beliefs added",
        len(beliefs_after) == len(beliefs_before),
        f"Before: {len(beliefs_before)} beliefs, After: {len(beliefs_after)} beliefs"
    )

    new_beliefs = beliefs_after[len(beliefs_before):]

    # Frontier updated — R003's question removed
    frontier_before = find_table(before, FRONTIER_PATTERN)
    frontier_after = find_table(after, FRONTIER_PATTERN)

    if frontier_before:
        old_top_delta = frontier_before[0].get("Experiment question", "")
        if old_top_delta:
            # Check if the exact old delta text is gone (use first 30 chars for fuzzy match)
            old_prefix = old_top_delta[:30].lower()
            still_there = any(old_prefix in str(f.get("Experiment question", "")).lower() for f in frontier_after)
            r.check(
                "Completed question removed from Frontier",
                not still_there,
                f"Old top delta: '{old_top_delta[:50]}...'"
            )
        else:
            r.check("Completed question removed from Frontier", False, "Old question text was empty")
    else:
        r.check("Completed question removed from Frontier", False,
                "No frontier entries parsed from before state")

    # Keep only the fastest goal-relevant next test; do not manufacture a large frontier.
    r.check(
        "Frontier keeps at most one next test",
        0 <= len(frontier_after) <= 1,
        f"Frontier has {len(frontier_after)} entries"
    )

    # Frontier stores only fields needed to choose the fastest adequate test.
    if frontier_after:
        sample = frontier_after[0]
        has_dimensions = all(
            dim in sample for dim in
            ("Experiment question", "Decision result", "Minimum complete evidence", "ETA", "Blocked by")
        )
        r.check(
            "Frontier has decision and time columns",
            has_dimensions,
            f"Frontier columns: {list(sample.keys())}"
        )
    else:
        r.check("Frontier has decision and time columns", True, "Frontier empty because goal may be resolved")

    r.check("Decided question does not create a run backlog", not frontier_after,
            f"Frontier has {len(frontier_after)} entries")

    # total_runs incremented
    runs_before = extract_meta_field(before, "total_runs")
    runs_after = extract_meta_field(after, "total_runs")
    try:
        r.check(
            "total_runs incremented",
            int(runs_after) > int(runs_before),
            f"Before: {runs_before}, After: {runs_after}"
        )
    except ValueError:
        r.check("total_runs incremented", False, f"Could not parse: '{runs_before}' -> '{runs_after}'")

    # last_updated changed
    date_before = extract_meta_field(before, "last_updated")
    date_after = extract_meta_field(after, "last_updated")
    r.check(
        "last_updated changed",
        date_after != date_before,
        f"Before: {date_before}, After: {date_after}"
    )
    r.check(
        "Experimental evidence resets direction recovery",
        extract_meta_field(after, "direction_recovery_used_since_experiment").lower() == "false",
        "A completed experiment must re-arm at most one future recovery lookup"
    )

    return r


# ---------------------------------------------------------------------------
# Agent runner
# ---------------------------------------------------------------------------

REVIEW_PROMPTS = {
    "initialization": (
        "You are a quality reviewer for an LLM-driven research loop. "
        "Your job is to evaluate whether the generated INFRA.md follows the template and correctly "
        "derives the optimization playbook from the hardware profile.\n\n"
        "Read these files:\n"
        "1. The INFRA template: {infra_template}\n"
        "2. The system profile (simulated hardware info): {profile}\n"
        "3. The generated output: {output}\n\n"
        "The system profile describes a 4x A100-80GB server with NVLink, AMD EPYC 64-core CPU, "
        "504GB RAM, PyTorch 2.4, deepspeed, and other packages. flash-attn and triton are NOT "
        "installed — these are optimization gaps the agent should identify.\n\n"
        "Evaluate the output against the template and hardware. Report:\n\n"
        "## Compliance\n"
        "For each requirement below, say PASS or FAIL with a one-line reason:\n"
        "- All template sections present (Compute/GPUs/CPU/Memory, full Optimization Playbook, Storage, Profiling Source)\n"
        "- GPU table correctly reflects 4x A100-SXM4-80GB with cc 8.0\n"
        "- Precision correctly recommends BF16 (not FP16) for cc 8.0\n"
        "- Attention correctly recommends SDPA (flash-attn not installed) and notes FA2 as upgrade opportunity\n"
        "- Compilation mentions torch.compile with appropriate mode recommendations\n"
        "- Parallelism uses all 4 human-confirmed GPUs, recommends DDP with torchrun when one replica fits, and forbids tensor parallelism unless a concrete memory/operation constraint requires it\n"
        "- The playbook records wall-clock, throughput, and per-rank work inside the experiment without creating a separate utilization gate\n"
        "- Data Loading has concrete num_workers, pin_memory, prefetch_factor guidance\n"
        "- GPU-CPU Transfer Pitfalls includes .item() warning and accumulate-on-GPU pattern\n"
        "- Training Efficiency mentions fused AdamW, TF32, cudnn.benchmark\n"
        "- Installed Accelerators table has correct versions from the profile (flash-attn and triton show 'not installed')\n"
        "- Storage correctly identifies /scratch as fast-local and /data as NFS\n"
        "- Recommended Optimizations table identifies flash-attn and triton as gaps with pip install commands\n"
        "- Playbook recommendations are internally consistent (no contradictions)\n\n"
        "## Quality issues\n"
        "List any problems — wrong recommendations for the hardware, hallucinated package versions, "
        "missing optimizations that should be obvious for A100s, generic advice that isn't tailored "
        "to the specific hardware.\n\n"
        "## What's good\n"
        "Note anything the output does particularly well.\n\n"
        "## Verdict\n"
        "Overall: SATISFACTORY or NEEDS IMPROVEMENT, with a 1-2 sentence summary.\n\n"
        "Write your review to {review_output}. Do NOT modify any other files."
    ),
    "plan_generation": (
        "You are a quality reviewer for an LLM-driven research loop. "
        "Your job is to evaluate whether the generated plan follows the templates and rules.\n\n"
        "Read these files:\n"
        "1. The PLAN template: {plan_template}\n"
        "2. The SUPERVISOR spec (especially Phase 2 minimum-decisive selection and Phase 3 plan requirements): {supervisor}\n"
        "3. The input STATE: {state}\n"
        "4. The generated output: {output}\n\n"
        "Evaluate the output against the template and supervisor rules. Report:\n\n"
        "## Compliance\n"
        "For each requirement below, say PASS or FAIL with a one-line reason:\n"
        "- All required sections present (Question and finish line, Evidence package, Method and resources, Prediction, Bounds, Working notes, Meta; optional Smoke test only for a concrete costly-run risk)\n"
        "- The plan names one primary hypothesis question and its support/contradict fork\n"
        "- Baseline, treatment, repetitions, and necessary controls/ablations form one coherent evidence package\n"
        "- The plan reaches a hypothesis-relevant measurement instead of substituting review/audit/setup work\n"
        "- The plan is a concise editable guide with one immediately executable first command and no amendment workflow\n"
        "- It filters for an adequate two-sided test, then selects the shortest total ETA (#3 at 8 minutes)\n"
        "- Minimum complete evidence and total ETA are explicit; the run cannot close after a trivial subset\n"
        "- Commands use the shortest reproducible path to a measurement, without padded audits/checks\n"
        "- Resources specify exact paths from STATE.md Environment (not made-up paths)\n"
        "- The decision fork clearly defines support versus contradiction\n"
        "- Hardware execution minimizes wall-clock time; any human-confirmed GPUs all receive useful work, DDP is used when one replica fits, and contention does not change the estimand\n"
        "- Bounds name only genuine budget, safety, irreversibility, unavailable-resource, or invalid-measurement stops\n\n"
        "## Quality issues\n"
        "List any problems with the LLM output — vagueness, hallucinated data, "
        "missing context, wrong belief targeting, logical gaps, or anything a supervisor "
        "should have caught.\n\n"
        "## What's good\n"
        "Note anything the output does particularly well.\n\n"
        "## Verdict\n"
        "Overall: SATISFACTORY or NEEDS IMPROVEMENT, with a 1-2 sentence summary.\n\n"
        "Write your review to {review_output}. Do NOT modify any other files."
    ),
    "worker_execution": (
        "You are a quality reviewer for an LLM-driven research loop. "
        "Your job is to evaluate whether the generated report follows the templates and rules.\n\n"
        "Read these files:\n"
        "1. The REPORT template: {report_template}\n"
        "2. The SUPERVISOR spec (especially Section 4 Worker Prompt Template): {supervisor}\n"
        "3. The worker plan: {plan}\n"
        "4. The generated output: {output}\n"
        "5. The generated artifacts: {artifact_dir}\n\n"
        "Fixture mapping: `tests/worker_execution/output_REPORT.md` stands in for `REPORTS/R003.md`, and "
        "`tests/worker_execution/artifacts/` stands in for the run's artifact and metrics directories. "
        "Accept fixture-relative `artifacts/...` links when they resolve to fresh files in that directory; "
        "do not downgrade the scientific review for this intentional layout remapping.\n\n"
        "Evaluate the output against the template and worker contract. Report:\n\n"
        "## Compliance\n"
        "For each requirement below, say PASS or FAIL with a one-line reason:\n"
        "- Required compact-paper sections present (Answer, Motivation, Questions tested, Method, Experiments, Results, Analysis, Limitations and tested scope, Conclusion, Reproducibility, Meta; Ablations optional)\n"
        "- Answer is at most 80 words; its first sentence says supports/contradicts/cannot decide, gives a decisive number, and avoids loop-internal jargon\n"
        "- Data is inline — actual numbers in tables, not just pointers to files\n"
        "- Experiments contains the main comparison and every necessary control/ablation under the same R###\n"
        "- Method states approach, data, comparisons, metrics, repetitions, environment, and material scientific changes\n"
        "- Visualizations are optional and limited to at most one\n"
        "- Analysis contains only what is needed to justify the conclusion\n"
        "- Conclusion uses supports/contradicts/cannot decide, references a belief #, and gives decisive evidence\n"
        "- Limitations gives exact tested scope and only alternatives that could reverse the conclusion\n"
        "- No New hypotheses or Next tests sections; Conclusion may name one experiment only for the same unresolved question\n\n"
        "## Quality issues\n"
        "List any problems — fabricated results, missing interpretation, "
        "inconsistencies between data and verdict, vague confounds, "
        "or anything that would mislead the supervisor.\n\n"
        "## What's good\n"
        "Note anything the output does particularly well.\n\n"
        "## Verdict\n"
        "Overall: SATISFACTORY or NEEDS IMPROVEMENT, with a 1-2 sentence summary.\n\n"
        "Write your review to {review_output}. Do NOT modify any other files."
    ),
    "state_compression": (
        "You are a quality reviewer for an LLM-driven research loop. "
        "Your job is to evaluate whether state compression was done correctly.\n\n"
        "Read these files:\n"
        "1. The STATE template: {state_template}\n"
        "2. The SUPERVISOR spec (especially Section 5 State Compression Rules): {supervisor}\n"
        "3. The input STATE (before): {state_before}\n"
        "4. The REPORT being ingested: {report}\n"
        "5. The generated output STATE (after): {output}\n\n"
        "Evaluate the compression against the rules. Report:\n\n"
        "## Compliance\n"
        "For each requirement below, say PASS or FAIL with a one-line reason:\n"
        "- Ledger: new row appended with run ID, question, decisive result, conclusion, belief, and link\n"
        "- BeliefState: confidence updated in the right direction (report says supports → increase)\n"
        "- BeliefState: confidence magnitude is reasonable (not too aggressive, not too timid)\n"
        "- BeliefState: status updated correctly (≥0.8 → supported, ≤0.2 → rejected)\n"
        "- BeliefState: Parent column present with values for all beliefs\n"
        "- No new beliefs or experiment backlog manufactured after the target question is decided\n"
        "- Frontier: completed question removed\n"
        "- Frontier: at most one goal-relevant next test; no manufactured backlog\n"
        "- Frontier: Experiment question, Decision result, Minimum complete evidence, ETA, and Blocked by columns present\n"
        "- Meta: total_runs incremented, last_updated changed\n"
        "- Meta: paradigm field present\n"
        "- Meta: a completed experiment resets direction_recovery_used_since_experiment=false\n"
        "- Paradigm shift: if a belief was rejected or dropped ≥0.3, were children flagged?\n\n"
        "## Quality issues\n"
        "List any problems — wrong confidence direction, missing beliefs, "
        "frontier not re-ranked properly, paradigm shift missed, "
        "or information lost during compression.\n\n"
        "## What's good\n"
        "Note anything the output does particularly well.\n\n"
        "## Verdict\n"
        "Overall: SATISFACTORY or NEEDS IMPROVEMENT, with a 1-2 sentence summary.\n\n"
        "Write your review to {review_output}. Do NOT modify any other files."
    ),
    "slurm_job_generation": (
        "You are a quality reviewer for SLURM job scripts generated by a research loop worker.\n\n"
        "Read these files:\n"
        "1. The SUPERVISOR spec (especially Section 4 Worker Prompt Template, Execution Mode → slurm): {supervisor}\n"
        "2. The OBSERVABILITY (DELTA marker spec): {log_protocol}\n"
        "3. The plan: {plan}\n"
        "4. The INFRA: {infra}\n"
        "5. Generated experiment.py: {experiment}\n"
        "6. Generated smoke job: {smoke_job}\n"
        "7. Generated hero job.sh: {job}\n\n"
        "Evaluate the generated scripts. Report:\n\n"
        "## Compliance\n"
        "For each requirement, say PASS or FAIL:\n"
        "- experiment.py has all DELTA markers (START, PROGRESS, DONE, BLOCKER)\n"
        "- experiment.py uses flush=True on all marker prints\n"
        "- experiment.py has wandb.init, wandb.log, wandb.finish\n"
        "- experiment.py implements the plan's commands as Python code\n"
        "- experiment.py has try/except with delta_blocker on fatal errors\n"
        "- all four human-confirmed GPUs do useful DDP/data-parallel work during training and evaluation; metrics include per-rank work, aggregate throughput, and launch-to-result wall-clock\n"
        "- job.sh has correct SBATCH directives (partition, GPUs, walltime from plan)\n"
        "- smoke job has a short walltime, same run ID and process shape, executes one hero-sized training step, and reports throughput/peak VRAM without completing the run\n"
        "- job.sh uses validated env activation from INFRA.md (absolute conda activation, "
        "uv/venv `source .../bin/activate`, or pixi shell-hook — never a bare `conda activate <name>`)\n"
        "- job.sh sets WANDB_PROJECT and WANDB_MODE env vars\n"
        "- job.sh output path includes run ID\n"
        "- job.sh launches the experiment.py\n\n"
        "## Quality issues\n"
        "Anything wrong — missing error handling, wrong env activation, mismatched resources, "
        "stale or hard-coded comparison metrics, relative paths resolved before `cd`, unsafe distributed retries, "
        "or metrics that only observe one DDP rank when the plan requires all GPUs.\n\n"
        "## Verdict\n"
        "Overall: SATISFACTORY or NEEDS IMPROVEMENT.\n\n"
        "Write your review to {review_output}. Do NOT modify any other files."
    ),
}


PROMPTS = {
    "initialization": (
        "You are an environment setup agent for a research loop.\n\n"
        "Read the INFRA template at {infra_template} — your output MUST use this exact structure "
        "with all the sections defined in the template.\n\n"
        "Read the INIT procedure at {init} — focus on the 'Hardware profiling and INFRA.md' "
        "subsection in Step 2 for the playbook derivation rules.\n\n"
        "Read the system profile at {profile}. This contains the output of hardware profiling "
        "commands (nvidia-smi, lscpu, free, df, python package versions) for a real server.\n\n"
        "Your task: Generate INFRA.md by:\n"
        "1. Filling the Compute section from the profiling output (GPU table, CPU, Memory)\n"
        "2. Deriving the Optimization Playbook using the rules in INIT.md — precision, attention, "
        "compilation, parallelism, data loading, GPU-CPU pitfalls, training efficiency, inference\n"
        "3. Filling Storage paths from the df/mount output, identifying speed classes correctly\n"
        "4. Filling the Installed Accelerators table from the package versions\n"
        "5. Filling Profiling Source (method: auto-profiled, today's date, hostname from profile)\n\n"
        "IMPORTANT: The playbook must be specific to this hardware. For example:\n"
        "- A100 (cc 8.0) → BF16, not FP16\n"
        "- flash-attn NOT installed but cc 8.0 supports it → recommend SDPA now, note flash-attn as upgrade\n"
        "- 4 human-confirmed GPUs with NVLink → use all 4 with DDP and torchrun when one replica fits; tensor/model sharding only for a concrete single-GPU fit or operation constraint\n"
        "- PyTorch 2.4 → torch.compile available, but triton NOT installed → note it\n"
        "- /data is NFS, /scratch is local NVMe\n\n"
        "IMPORTANT: After filling the playbook, fill the Recommended Optimizations table.\n"
        "Compare what's installed vs what the hardware supports. The profile shows flash-attn and "
        "triton are NOT installed — these are clear optimization gaps that should be listed with "
        "concrete pip install commands, impact level, and status=pending.\n\n"
        "The GPU-CPU Transfer Pitfalls section should be filled from the template — these are "
        "static rules, not hardware-dependent, but they must be present.\n\n"
        "Write the INFRA.md to {output}. Do NOT modify any other files."
    ),
    "plan_generation": (
        "You are a research supervisor. "
        "Read {supervisor} — focus on section 2 (Supervisor Loop) for the planning process "
        "and section 3 (Contracts) for rules.\n\n"
        "Read the plan template at {plan_template} — your output MUST use these exact section headings: "
        "Question and finish line, Evidence package, Method and resources, Prediction, Bounds, Working notes, Meta. Include the optional Smoke test "
        "only for a named costly-run failure risk.\n\n"
        "Read the current state from {input}.\n\n"
        "Generate a plan for the next run following Phase 2 (Select delta) and Phase 3 (Create run) rules:\n"
        "- Exclude no-progress work; choose the shortest complete experiment capable of answering one hypothesis\n"
        "- State the primary question, support/contradict fork, minimum complete evidence, and ETA\n"
        "- Keep baseline, treatment, repetitions, and necessary controls/ablations under this one R###\n"
        "- Resources must use exact paths from STATE.md Environment — do not invent paths\n"
        "- Give one first executable command and only the minimal measurement details needed for the decision\n"
        "- Keep the whole plan under 400 prose words; do not summarize context or enumerate broad fallbacks\n"
        "- Include one expected and one surprising outcome before execution\n"
        "- This fixture is CPU-only. For GPU plans, use every human-confirmed GPU for useful work, prefer DDP when one replica fits, and minimize wall-clock time without biasing the measurement\n\n"
        "Write the plan to {output}. Do NOT modify any other files."
    ),
    "worker_execution": (
        "You are a research worker.\n\n"
        "Read {supervisor} section 4 (Worker Prompt Template) for the contract and rules.\n\n"
        "Read the report template at {report_template} — your output MUST use this exact structure "
        "with these exact section headings in this order: "
        "Answer, Motivation, Questions tested, Method, Experiments, Results, Analysis, optional Ablations, "
        "Limitations and tested scope, Conclusion, Reproducibility, Meta.\n\n"
        "CRITICAL: Use the EXACT section headings from the template. Do not rename, reorder, "
        "or use alternative headings. The supervisor parses these by name.\n\n"
        "Your plan is in {input}. Execute the plan.\n\n"
        "Additional rules:\n"
        "- Execute the complete evidence package under this one run ID; do not split its conditions, control, analysis, or plot into new runs\n"
        "- Do not add audits, literature review, gates, or unrelated experiments\n"
        "- Make the Answer at most 80 words; say supports/contradicts/cannot decide in the first sentence, include the decisive number, and use no loop-internal jargon\n"
        "- Use exact technical names and numbers, but define unfamiliar terms in plain English and never invent an acronym\n"
        "- All data must be inline in tables (not just file references)\n"
        "- Do not generate a plot by default; use at most one only if it clarifies the verdict\n"
        "- Regenerate metrics and report from this execution only; never reuse stale artifact values\n"
        "- Conclusion must use supports, contradicts, or cannot decide and reference belief #3\n"
        "- Do not add New hypotheses or Next tests sections; one same-question next experiment may appear in Conclusion only if unresolved\n"
        "- Save artifacts to tests/worker_execution/artifacts/\n\n"
        "- Fill every Meta field from the template, including execution, slurm_job_id, and wandb_run\n\n"
        "Write the report to {output}. Do NOT modify any other files."
    ),
    "state_compression": (
        "You are a research supervisor.\n\n"
        "Read {supervisor} section 5 (State Compression Rules) for the exact update procedure.\n\n"
        "Read the state template at {state_template} — your output MUST follow this structure "
        "including: Parent in BeliefState, paradigm/direction-recovery fields in Meta, "
        "and Experiment question/Decision result/Minimum complete evidence/ETA/Blocked by columns in Frontier.\n\n"
        "The current state is in {state_before}.\n"
        "The report to ingest is in {report}.\n\n"
        "Apply compression rules:\n"
        "- Append to Ledger with the question, decisive result, conclusion, belief, and link\n"
        "- Update belief confidence in the correct direction and magnitude\n"
        "- Do not add a new belief or next experiment because the target question is decided\n"
        "- Remove the completed question and leave Frontier empty\n"
        "- When Frontier is nonempty, record Experiment question, Decision result, Minimum complete evidence, ETA, and Blocked by\n"
        "- Check for paradigm shift if any belief was rejected or dropped ≥0.3\n"
        "- Update Meta (total_runs, last_updated, paradigm if shift occurred); because this is a direct observation, "
        "reset direction_recovery_used_since_experiment=false\n\n"
        "Produce the updated state and write it to {output}. Do NOT modify any other files."
    ),
    "slurm_job_generation": (
        "You are a research worker executing an experiment on a SLURM cluster.\n\n"
        "Read {supervisor} — focus on Section 4 Worker Prompt Template, specifically the "
        "'Execution Mode → mode = slurm' section for the exact steps.\n\n"
        "Read the OBSERVABILITY at {log_protocol} for the DELTA marker spec and Python helper.\n\n"
        "Read the plan at {plan}. Note: execution mode is slurm.\n"
        "Read the INFRA at {infra}. Note: Job Execution section has validated env activation, "
        "wandb mode=offline, partition=gpu.\n\n"
        "Your task: Generate ONLY experiment.py, job_smoke.sh, and job.sh. Do NOT actually submit anything.\n\n"
        "1. Write {experiment} — a self-contained Python script that:\n"
        "   - Includes the DELTA marker helper functions (from OBSERVABILITY)\n"
        "   - Implements ALL plan commands as Python code\n"
        "   - Gives useful batches to all four confirmed DDP ranks and records per-rank batch/sample counts, aggregate throughput, and wall-clock time in the real run\n"
        "   - Has wandb.init/log/finish integration\n"
        "   - Emits DELTA-START at beginning, DELTA-PROGRESS at milestones, DELTA-DONE at end\n"
        "   - Has try/except with delta_blocker for fatal errors\n"
        "   - Uses flush=True on ALL prints\n\n"
        "2. Write {smoke_job} — a 15-minute four-GPU smoke SLURM script under R007 that launches "
        "the experiment with `--smoke`, records loss/throughput/peak VRAM for one hero-sized step, "
        "and never emits DONE or writes a report.\n\n"
        "3. Write {job} — the hero SLURM job script that:\n"
        "   - Has #SBATCH directives from the plan's SLURM section\n"
        "   - Uses the validated env activation from INFRA.md Job Execution\n"
        "   - Sets WANDB_PROJECT, WANDB_MODE, WANDB_RUN_NAME env vars\n"
        "   - Has --output=RUNS/R007/slurm-%j.out\n"
        "   - Launches `torchrun --standalone --nproc_per_node=4` on the absolute R007 experiment path\n"
        "   - Translates any-rank torchrun failure into a DELTA-BLOCKER marker\n\n"
        "Do NOT modify any other files."
    ),
}


def run_agent(test_name: str, agent: str = "codex"):
    """Spawn the agent for a test case."""

    templates = SUPERVISOR.parent

    if test_name == "initialization":
        prompt = PROMPTS[test_name].format(
            infra_template=templates / "INFRA.template.md",
            init=templates / "INIT.md",
            profile=TESTS / "initialization" / "SYSTEM_PROFILE.md",
            output=TESTS / "initialization" / "output_INFRA.md",
        )
    elif test_name == "plan_generation":
        prompt = PROMPTS[test_name].format(
            supervisor=SUPERVISOR,
            plan_template=templates / "PLAN.template.md",
            input=TESTS / "plan_generation" / "STATE.md",
            output=TESTS / "plan_generation" / "output_PLAN.md",
        )
    elif test_name == "worker_execution":
        prompt = PROMPTS[test_name].format(
            supervisor=SUPERVISOR,
            report_template=templates / "REPORT.template.md",
            input=TESTS / "worker_execution" / "PLAN.md",
            output=TESTS / "worker_execution" / "output_REPORT.md",
        )
    elif test_name == "state_compression":
        prompt = PROMPTS[test_name].format(
            supervisor=SUPERVISOR,
            state_template=templates / "STATE.template.md",
            state_before=TESTS / "state_compression" / "STATE_before.md",
            report=TESTS / "state_compression" / "REPORT.md",
            output=TESTS / "state_compression" / "output_STATE_after.md",
        )
    elif test_name == "slurm_job_generation":
        prompt = PROMPTS[test_name].format(
            supervisor=SUPERVISOR,
            log_protocol=templates / "OBSERVABILITY.md",
            plan=TESTS / "slurm_job_generation" / "PLAN.md",
            infra=TESTS / "slurm_job_generation" / "INFRA.md",
            experiment=TESTS / "slurm_job_generation" / "output_experiment.py",
            smoke_job=TESTS / "slurm_job_generation" / "output_smoke_job.sh",
            job=TESTS / "slurm_job_generation" / "output_job.sh",
        )
    else:
        print(f"Unknown test: {test_name}")
        return

    model = OPTIONS.model or (OPTIONS.supervisor_model if test_name in
        ("plan_generation", "state_compression") else OPTIONS.worker_model)
    effort = OPTIONS.supervisor_effort if test_name in (
        "plan_generation", "state_compression") else OPTIONS.worker_effort
    if agent == "claude":
        model = OPTIONS.model or "sonnet"
    result = execute(agent, model, effort, EVALUATION, prompt,
        [TESTS / test_name / name for name in OUTPUTS[test_name]],
        test_name, OPTIONS.timeout or (600 if test_name == "worker_execution" else 300))
    return execution_check(test_name, result)


def execution_check(label, result):
    check = TestResult(label)
    check.check("Agent execution produced fresh outputs", result["ok"], result.get("error", ""))
    return check


def review_agent(test_name: str, agent: str = "codex"):
    """Spawn the agent to review a test output against templates."""

    templates = SUPERVISOR.parent
    missing = [name for name in OUTPUTS[test_name]
               if not (TESTS / test_name / name).is_file()]
    if missing:
        return execution_check("Review " + test_name,
            {"ok": False, "error": "missing review inputs: " + ", ".join(missing)})

    if test_name == "initialization":
        output = TESTS / "initialization" / "output_INFRA.md"
        review_output = TESTS / "initialization" / "review_INFRA.md"
        prompt = REVIEW_PROMPTS[test_name].format(
            infra_template=templates / "INFRA.template.md",
            profile=TESTS / "initialization" / "SYSTEM_PROFILE.md",
            output=output,
            review_output=review_output,
        )
    elif test_name == "plan_generation":
        output = TESTS / "plan_generation" / "output_PLAN.md"
        review_output = TESTS / "plan_generation" / "review_PLAN.md"
        prompt = REVIEW_PROMPTS[test_name].format(
            plan_template=templates / "PLAN.template.md",
            supervisor=SUPERVISOR,
            state=TESTS / "plan_generation" / "STATE.md",
            output=output,
            review_output=review_output,
        )
    elif test_name == "worker_execution":
        output = TESTS / "worker_execution" / "output_REPORT.md"
        review_output = TESTS / "worker_execution" / "review_REPORT.md"
        prompt = REVIEW_PROMPTS[test_name].format(
            report_template=templates / "REPORT.template.md",
            supervisor=SUPERVISOR,
            plan=TESTS / "worker_execution" / "PLAN.md",
            output=output,
            artifact_dir=TESTS / "worker_execution" / "artifacts",
            review_output=review_output,
        )
    elif test_name == "state_compression":
        output = TESTS / "state_compression" / "output_STATE_after.md"
        review_output = TESTS / "state_compression" / "review_STATE.md"
        prompt = REVIEW_PROMPTS[test_name].format(
            state_template=templates / "STATE.template.md",
            supervisor=SUPERVISOR,
            state_before=TESTS / "state_compression" / "STATE_before.md",
            report=TESTS / "state_compression" / "REPORT.md",
            output=output,
            review_output=review_output,
        )
    elif test_name == "slurm_job_generation":
        experiment = TESTS / "slurm_job_generation" / "output_experiment.py"
        smoke_job = TESTS / "slurm_job_generation" / "output_smoke_job.sh"
        job = TESTS / "slurm_job_generation" / "output_job.sh"
        review_output = TESTS / "slurm_job_generation" / "review_slurm.md"
        if not experiment.exists() and not job.exists():
            print(f"\n--- Skipping review of {test_name}: output files not found ---")
            return execution_check(test_name, {"ok": False, "error": "missing review inputs"})
        prompt = REVIEW_PROMPTS[test_name].format(
            supervisor=SUPERVISOR,
            log_protocol=templates / "OBSERVABILITY.md",
            plan=TESTS / "slurm_job_generation" / "PLAN.md",
            infra=TESTS / "slurm_job_generation" / "INFRA.md",
            experiment=experiment,
            smoke_job=smoke_job,
            job=job,
            review_output=review_output,
        )
        output = experiment  # for the exists() check below
    else:
        print(f"Unknown test: {test_name}")
        return

    if not output.exists():
        print(f"\n--- Skipping review of {test_name}: {output.name} not found ---")
        return execution_check(test_name, {"ok": False, "error": "missing review output"})

    verdict_path = review_output.with_suffix(".json")
    prompt += (f"\nAlso write the machine-readable verdict to {verdict_path}: "
               '{"passed": true, "issues": []}. Set passed to false and list material '
               'failures when improvement is needed. Return a concise final message.')
    model = OPTIONS.model or OPTIONS.review_model
    if agent == "claude":
        model = OPTIONS.model or "sonnet"
    result = execute(agent, model, OPTIONS.worker_effort, EVALUATION, prompt,
                     [review_output, verdict_path], "review_" + test_name,
                     OPTIONS.timeout or 300)
    check = execution_check("Review " + test_name, result)
    if result["ok"]:
        passed, detail = review_verdict(verdict_path)
        check.check("Scientific review accepted output", passed, detail)
    return check


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global DEBUG, TESTS, SUPERVISOR, EVALUATION, OPTIONS

    parser = argparse.ArgumentParser(description="Test the research loop agent")
    parser.add_argument("--run", action="store_true", help="Generate outputs by spawning the agent")
    parser.add_argument("--review", action="store_true",
                        help="LLM reviews outputs against templates (checks quality, not just structure)")
    parser.add_argument("--agent", choices=["claude", "codex"], default="codex")
    parser.add_argument("--model", help="Explicit override for every role in this evaluation")
    parser.add_argument("--supervisor-model", default="gpt-6-astra")
    parser.add_argument("--worker-model", default="gpt-5.6-sol")
    parser.add_argument("--review-model", default="gpt-5.6-sol")
    parser.add_argument("--supervisor-effort", choices=["low", "medium", "high", "xhigh"], default="high")
    parser.add_argument("--worker-effort", choices=["low", "medium", "high", "xhigh"], default="medium")
    parser.add_argument("--output-dir", type=Path, help="New isolated evaluation directory")
    parser.add_argument("--artifacts-dir", type=Path, help="Validate an earlier evaluation's tests directory")
    parser.add_argument("--timeout", type=float, help="Per invocation timeout in seconds")
    parser.add_argument("--test", choices=["init", "plan", "worker", "compression", "slurm", "contracts", "all"], default="all",
                        help="Which test to run")
    parser.add_argument("--debug", action="store_true", help="Show parsed table data")
    args = parser.parse_args()

    DEBUG = args.debug
    OPTIONS = args
    if args.timeout is not None and (not math.isfinite(args.timeout) or args.timeout <= 0):
        parser.error("--timeout must be positive")
    if args.artifacts_dir and (args.run or args.review):
        parser.error("--artifacts-dir is for validation only")
    if args.output_dir and not (args.run or args.review):
        parser.error("--output-dir requires --run or --review")
    if args.artifacts_dir:
        TESTS = args.artifacts_dir.resolve()
    if args.run or args.review:
        EVALUATION = prepare_workspace(ROOT, args.output_dir, review_only=not args.run)
        TESTS = EVALUATION / "tests"
        SUPERVISOR = EVALUATION / "delta-research/templates/SUPERVISOR.md"
        print(f"Evaluation outputs: {EVALUATION}")
        import hashlib
        manifest = {"mode": "generated" if args.run else "review_snapshot",
                    "models": {"supervisor": args.supervisor_model, "worker": args.worker_model,
                               "review": args.review_model, "override": args.model},
                    "framework_sha256": hashlib.sha256(SUPERVISOR.read_bytes()).hexdigest()}
        (EVALUATION / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    tests_to_run = {
        "init": args.test in ("init", "all"),
        "plan": args.test in ("plan", "all"),
        "worker": args.test in ("worker", "all"),
        "compression": args.test in ("compression", "all"),
        "slurm": args.test in ("slurm", "all"),
        "contracts": args.test in ("contracts", "all"),
    }

    results = []
    names = {"init": "initialization", "plan": "plan_generation", "worker": "worker_execution",
             "compression": "state_compression", "slurm": "slurm_job_generation"}
    for short, name in names.items():
        if not tests_to_run[short]:
            continue
        if args.run:
            generated = run_agent(name, args.agent)
            results.append(generated)
            if generated.failed():
                tests_to_run[short] = False
                continue
        if args.review:
            results.append(review_agent(name, args.agent))

    if tests_to_run["init"]:
        results.append(validate_infra(
            TESTS / "initialization" / "output_INFRA.md",
            TESTS / "initialization" / "SYSTEM_PROFILE.md",
        ))

    if tests_to_run["plan"]:
        results.append(validate_plan(
            TESTS / "plan_generation" / "output_PLAN.md",
            TESTS / "plan_generation" / "STATE.md",
        ))

    if tests_to_run["worker"]:
        results.append(validate_report(
            TESTS / "worker_execution" / "output_REPORT.md",
        ))

    if tests_to_run["compression"]:
        results.append(validate_state_compression(
            TESTS / "state_compression" / "STATE_before.md",
            TESTS / "state_compression" / "output_STATE_after.md",
            TESTS / "state_compression" / "REPORT.md",
        ))

    if tests_to_run["slurm"]:
        results.append(validate_slurm_job(
            TESTS / "slurm_job_generation" / "output_experiment.py",
            TESTS / "slurm_job_generation" / "output_job.sh",
            TESTS / "slurm_job_generation" / "PLAN.md",
            TESTS / "slurm_job_generation" / "INFRA.md",
        ))

    if tests_to_run["contracts"]:
        results.append(validate_framework_contracts())

    # Summary
    total_passed = sum(r.passed() for r in results)
    total_failed = sum(r.failed() for r in results)
    total = total_passed + total_failed

    for r in results:
        r.print_report()

    print(f"\n{'='*60}")
    print(f"  TOTAL: {total_passed}/{total} passed", end="")
    if total_failed > 0:
        print(f"  (\033[31m{total_failed} failed\033[0m)")
    else:
        print(f"  (\033[32mall passed\033[0m)")
    print(f"{'='*60}")

    if EVALUATION:
        summary = {"passed": total_passed, "failed": total_failed,
                   "checks": {r.name: r.checks for r in results}}
        (EVALUATION / "results.json").write_text(json.dumps(summary, indent=2) + "\n")
    sys.exit(1 if total_failed > 0 else 0)


if __name__ == "__main__":
    main()
