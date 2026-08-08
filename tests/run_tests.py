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
  python tests/run_tests.py --run              # generate outputs with claude, then validate
  python tests/run_tests.py --run --agent codex  # use codex instead
  python tests/run_tests.py --review           # LLM reviews outputs against templates
  python tests/run_tests.py --debug            # show parsed data for debugging
"""

import re
import sys
import subprocess
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"
SUPERVISOR = ROOT / "templates" / "SUPERVISOR.md"

DEBUG = False

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
LEDGER_PATTERN = r"Run\s*\|.*Delta\s*\|.*Signal"
BELIEF_PATTERN = r"#\s*\|.*Belief\s*\|.*Confidence"
FRONTIER_PATTERN = r"Rank\s*\|.*Delta"
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
            "--gpus-per-node" in job or "--gres=gpu" in job,
            "Must allocate GPUs"
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
    for required in ["Delta", "Literature Grounding", "Resources", "Commands", "Success metrics", "Stop conditions", "Context", "Meta"]:
        found = any(required.lower() in s.lower() for s in section_names)
        r.check(f"Has section: {required}", found)

    # Multiple command steps
    step_headers = re.findall(r"###\s+Step\s+\d+", plan)
    r.check(
        "Multiple command steps",
        len(step_headers) >= 2,
        f"Found {len(step_headers)} steps (expected >=2)"
    )

    # Resources section has actual paths (not just placeholders)
    resources_text = ""
    for key, val in sections.items():
        if "resource" in key.lower():
            resources_text = val
    has_paths = bool(re.search(r"(/[\w/.-]+|data/|RUNS/|artifacts/)", resources_text))
    r.check("Resources section has actual paths", has_paths)

    grounding_text = ""
    for key, val in sections.items():
        if "literature grounding" in key.lower():
            grounding_text = val
    r.check(
        "Plan has a completed literature gate",
        "grounded" in grounding_text.lower() and "reports/r" in grounding_text.lower(),
        "Empirical plans must cite the completed REPORTS/R###.md grounding review"
    )

    # Targets the right belief — state has beliefs at 0.7, 0.5, 0.45
    # Agent should target #2 (0.5) or #3 (0.45) — most uncertain
    belief_refs = re.findall(r"#([23])", plan)
    r.check(
        "Targets uncertain belief (#2 or #3)",
        len(belief_refs) > 0,
        "Plan should target beliefs nearest 0.5 confidence"
    )

    # Context references specific numbers from prior runs
    has_numbers = bool(re.search(r"\d+\.\d+x|\d+ms|\d+\.\d+", plan))
    r.check(
        "Context includes specific numbers from prior runs",
        has_numbers,
        "Should reference concrete findings, not just 'see R001'"
    )

    # Success metrics table has rows
    metrics_table = find_table(plan, METRICS_PATTERN)
    r.check(
        "Success metrics table has rows",
        len(metrics_table) >= 1,
        f"Found {len(metrics_table)} metric rows"
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

    # Required sections
    for required in ["Summary", "Motivation", "Literature grounding", "Method", "Results", "Signal", "Verdict",
                      "Confounds", "New hypotheses", "Next tests", "Meta"]:
        found = any(required.lower() in s for s in section_names_lower)
        r.check(f"Has section: {required}", found)

    # Summary is present and not too long
    summary = sections.get("Summary", "").strip()
    r.check(
        "Summary is present and concise",
        20 < len(summary) < 1000,
        f"Summary is {len(summary)} chars"
    )

    # Inline data — tables in the Results section or Data subsection
    results_text = ""
    for key, val in sections.items():
        if "result" in key.lower() or "data" in key.lower():
            results_text += val
    has_inline_tables = "|" in results_text
    r.check("Results has inline data tables", has_inline_tables)

    # Embedded visualizations
    image_refs = re.findall(r"!\[.*?\]\(.*?\)", report)
    r.check(
        "Has embedded visualizations",
        len(image_refs) >= 1,
        f"Found {len(image_refs)} image embeds"
    )

    # Analysis section exists and has content
    analysis = ""
    for key, val in sections.items():
        if "analysis" in key.lower():
            analysis = val.strip()
    r.check(
        "Has analysis with interpretation",
        len(analysis) > 50,
        f"Analysis section has {len(analysis)} chars (expected >50)"
    )

    # Signal discrimination is valid
    signal_text = ""
    for key, val in sections.items():
        if "signal" in key.lower():
            signal_text = val
    valid_signals = ["discriminating", "partial", "null"]
    has_valid_signal = any(s in signal_text.lower() for s in valid_signals)
    r.check("Signal discrimination is valid", has_valid_signal)

    # Verdict is valid
    verdict_text = ""
    for key, val in sections.items():
        if "verdict" in key.lower():
            verdict_text = val
    valid_verdicts = ["supports", "contradicts", "unclear", "blocker"]
    has_valid_verdict = any(v in verdict_text.lower() for v in valid_verdicts)
    r.check("Verdict is valid", has_valid_verdict)

    # Verdict references a belief number
    has_belief_ref = bool(re.search(r"(belief\s*)?#\d+", verdict_text, re.IGNORECASE))
    r.check("Verdict references a belief", has_belief_ref)

    # New hypotheses section has content (not just placeholder)
    new_hyp = ""
    for key, val in sections.items():
        if "new hypothes" in key.lower():
            new_hyp = val.strip()
    # Filter out comment lines
    hyp_lines = [l for l in new_hyp.split("\n") if l.strip() and not l.strip().startswith("<!--")]
    r.check(
        "New hypotheses section has content",
        len(hyp_lines) >= 1,
        f"Found {len(hyp_lines)} non-empty lines"
    )

    return r


# ---------------------------------------------------------------------------
# Framework contract: literature gate + GitHub publication
# ---------------------------------------------------------------------------

def validate_framework_contracts() -> TestResult:
    r = TestResult("Framework Contracts (Literature + GitHub)")
    templates = ROOT / "templates"
    supervisor = (templates / "SUPERVISOR.md").read_text()
    state = (templates / "STATE.template.md").read_text()
    plan = (templates / "PLAN.template.md").read_text()
    report = (templates / "REPORT.template.md").read_text()
    init = (templates / "INIT.md").read_text()
    literature_path = templates / "LITERATURE.template.md"
    literature_index_path = templates / "LITERATURE_INDEX.template.md"

    r.check("Literature template exists", literature_path.exists())
    r.check("Literature index template exists", literature_index_path.exists())
    literature = literature_path.read_text() if literature_path.exists() else ""
    for heading in ["Target hypothesis", "Search protocol", "Evidence map", "Synthesis",
                    "Grounding verdict", "New hypotheses", "Next tests", "Sources", "Meta"]:
        r.check(
            f"Literature template has: {heading}",
            bool(re.search(rf"^## {re.escape(heading)}\s*$", literature, re.MULTILINE)),
        )

    r.check("Supervisor enforces one review per hypothesis",
            "Each literature-review run grounds exactly one hypothesis" in supervisor)
    r.check("Supervisor blocks ungrounded empirical work",
            "may target a belief only when" in supervisor and "Literature value is `grounded" in supervisor)
    r.check("Supervisor requires current search and primary sources",
            "current internet/database search" in supervisor and "Prioritize primary sources" in supervisor)
    r.check("Supervisor requires contrary evidence",
            "strongest contrary" in supervisor.lower())
    r.check("New hypotheses start literature pending",
            "Literature `pending`" in supervisor)
    r.check("State template has Literature column",
            "| Literature |" in state and "grounded (R###, YYYY-MM-DD)" in state)
    r.check("Plan template has Literature Grounding",
            "## Literature Grounding" in plan)
    r.check("Experimental report cites grounding",
            "## Literature grounding" in report and "review artifact" in report.lower())
    r.check("Supervisor requires versioned literature archive",
            "LITERATURE/B###/R###/" in supervisor and "byte-identical" in supervisor)
    r.check("Supervisor preserves query/evidence/bibliography artifacts",
            all(name in supervisor for name in ("queries.md", "evidence.csv", "sources.bib")))
    r.check("Supervisor updates literature index",
            "Update `LITERATURE/INDEX.md`" in supervisor)

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

    # New beliefs added (report has new hypotheses)
    r.check(
        "New beliefs added",
        len(beliefs_after) > len(beliefs_before),
        f"Before: {len(beliefs_before)} beliefs, After: {len(beliefs_after)} beliefs"
    )

    # New beliefs have Parent field populated
    new_beliefs = beliefs_after[len(beliefs_before):]
    if new_beliefs:
        all_have_parent = all(b.get("Parent", "").strip() for b in new_beliefs)
        r.check(
            "New beliefs have Parent field",
            all_have_parent,
            f"New beliefs: {[b.get('Parent', '') for b in new_beliefs]}"
        )
    else:
        r.check("New beliefs have Parent field", False, "No new beliefs to check")

    if new_beliefs:
        all_pending = all(b.get("Literature", "").strip().lower() == "pending" for b in new_beliefs)
        r.check(
            "New beliefs require literature grounding",
            all_pending,
            f"New belief Literature values: {[b.get('Literature', '') for b in new_beliefs]}"
        )
    else:
        r.check("New beliefs require literature grounding", False, "No new beliefs to check")

    # Frontier updated — R003's delta removed
    frontier_before = find_table(before, FRONTIER_PATTERN)
    frontier_after = find_table(after, FRONTIER_PATTERN)

    if frontier_before:
        old_top_delta = frontier_before[0].get("Delta", "")
        if old_top_delta:
            # Check if the exact old delta text is gone (use first 30 chars for fuzzy match)
            old_prefix = old_top_delta[:30].lower()
            still_there = any(old_prefix in str(f.get("Delta", "")).lower() for f in frontier_after)
            r.check(
                "Completed delta removed from Frontier",
                not still_there,
                f"Old top delta: '{old_top_delta[:50]}...'"
            )
        else:
            r.check("Completed delta removed from Frontier", False, "Old delta text was empty")
    else:
        r.check("Completed delta removed from Frontier", False,
                "No frontier entries parsed from before state")

    # New frontier entries for new beliefs
    r.check(
        "Frontier has entries for new beliefs",
        len(frontier_after) >= 1,
        f"Frontier has {len(frontier_after)} entries"
    )

    # Frontier entries have scoring dimension columns
    if frontier_after:
        sample = frontier_after[0]
        has_dimensions = all(
            dim in sample for dim in ("Uncertainty", "Info gain", "Feasibility")
        )
        r.check(
            "Frontier has scoring dimension columns",
            has_dimensions,
            f"Frontier columns: {list(sample.keys())}"
        )
    else:
        r.check("Frontier has scoring dimension columns", False, "No frontier entries to check")

    review_targets = {
        f.get("Target", "") for f in frontier_after
        if "literature review" in f.get("Delta", "").lower()
    }
    new_ids = {f"#{b.get('#')}" for b in new_beliefs}
    r.check(
        "Frontier grounds every new belief before experiments",
        bool(new_ids) and new_ids.issubset(review_targets),
        f"Expected review targets {sorted(new_ids)}, found {sorted(review_targets)}"
    )

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
        "- Parallelism recommends DDP with torchrun for 4 GPUs, mentions FSDP as fallback for large models\n"
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
        "2. The SUPERVISOR spec (especially Phase 2 bandit reasoning and Phase 3 plan requirements): {supervisor}\n"
        "3. The input STATE: {state}\n"
        "4. The generated output: {output}\n\n"
        "Evaluate the output against the template and supervisor rules. Report:\n\n"
        "## Compliance\n"
        "For each requirement below, say PASS or FAIL with a one-line reason:\n"
        "- All template sections present (Delta, Literature Grounding, Resources, Commands, Success metrics, Stop conditions, Context, Meta)\n"
        "- Empirical plan cites the exact completed literature-review report for each target belief\n"
        "- Delta targets the most uncertain belief(s) (confidence nearest 0.5)\n"
        "- Bandit reasoning: does it show awareness of uncertainty, info gain, and feasibility?\n"
        "- Commands have multiple substantive steps (not just 'run a script')\n"
        "- Resources specify exact paths from STATE.md Environment (not made-up paths)\n"
        "- Context references specific numbers from prior runs (not vague 'see R001')\n"
        "- Success metrics define clear support vs contradict thresholds\n"
        "- Hardware utilization: does the plan maximize available compute (GPUs, CPU cores) from Environment?\n"
        "- Stop conditions are specific and actionable\n\n"
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
        "3. The generated output: {output}\n\n"
        "Evaluate the output against the template and worker contract. Report:\n\n"
        "## Compliance\n"
        "For each requirement below, say PASS or FAIL with a one-line reason:\n"
        "- All template sections present (Summary, Motivation, Literature grounding, Method, Results/Data/Visualizations/Analysis, "
        "Signal, Verdict, Confounds, New hypotheses, Next tests, Artifacts, Meta)\n"
        "- Summary is concise and self-contained (a researcher could understand what happened)\n"
        "- Data is inline — actual numbers in tables, not just pointers to files\n"
        "- Visualizations are embedded with ![](path) syntax\n"
        "- Analysis interprets results (not just restating numbers)\n"
        "- Signal uses valid values (discriminating/partial/null) with reasoning\n"
        "- Verdict uses valid values (supports/contradicts/unclear/BLOCKER) and references a belief #\n"
        "- New hypotheses include parent belief hints [parent: #N or —]\n"
        "- Confounds section identifies real alternative explanations\n"
        "- Next tests suggest concrete follow-up deltas\n\n"
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
        "- Ledger: new row appended with correct run ID, delta, signal, verdict, belief, link\n"
        "- BeliefState: confidence updated in the right direction (report says supports → increase)\n"
        "- BeliefState: confidence magnitude is reasonable (not too aggressive, not too timid)\n"
        "- BeliefState: status updated correctly (≥0.8 → supported, ≤0.2 → rejected)\n"
        "- BeliefState: Parent column present with values for all beliefs\n"
        "- New beliefs: added from report's New hypotheses with confidence 0.5 and Literature=pending\n"
        "- New beliefs: Parent field populated (from [parent: #N] hints in report)\n"
        "- Frontier: completed delta removed\n"
        "- Frontier: new entries added for new beliefs\n"
        "- Frontier: scoring dimensions present (Uncertainty, Info gain, Feasibility)\n"
        "- Frontier: ranking makes sense (high-uncertainty + high-info-gain first)\n"
        "- Meta: total_runs incremented, last_updated changed\n"
        "- Meta: paradigm field present\n"
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
        "6. Generated job.sh: {job}\n\n"
        "Evaluate the generated scripts. Report:\n\n"
        "## Compliance\n"
        "For each requirement, say PASS or FAIL:\n"
        "- experiment.py has all DELTA markers (START, PROGRESS, DONE, BLOCKER)\n"
        "- experiment.py uses flush=True on all marker prints\n"
        "- experiment.py has wandb.init, wandb.log, wandb.finish\n"
        "- experiment.py implements the plan's commands as Python code\n"
        "- experiment.py has try/except with delta_blocker on fatal errors\n"
        "- job.sh has correct SBATCH directives (partition, GPUs, walltime from plan)\n"
        "- job.sh uses validated env activation from INFRA.md (absolute conda activation, "
        "uv/venv `source .../bin/activate`, or pixi shell-hook — never a bare `conda activate <name>`)\n"
        "- job.sh sets WANDB_PROJECT and WANDB_MODE env vars\n"
        "- job.sh output path includes run ID\n"
        "- job.sh launches the experiment.py\n\n"
        "## Quality issues\n"
        "Anything wrong — missing error handling, wrong env activation, mismatched resources.\n\n"
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
        "- 4 GPUs with NVLink → DDP with torchrun, FSDP for large models\n"
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
        "Read the plan template at {plan_template} — your output MUST use this exact structure "
        "with these exact section headings: Delta, Literature Grounding, Resources, Commands, Success metrics, "
        "Stop conditions, Context, Meta.\n\n"
        "Read the current state from {input}.\n\n"
        "Generate a plan for the next run following Phase 2 (Select delta) and Phase 3 (Create run) rules:\n"
        "- Use bandit reasoning: assess Uncertainty, Info gain, Feasibility for candidates\n"
        "- Target the most uncertain belief (confidence nearest 0.5)\n"
        "- Select only a belief with Literature=grounded for an empirical plan and cite its REPORTS/R###.md review\n"
        "- Resources must use exact paths from STATE.md Environment — do not invent paths\n"
        "- Commands must have multiple substantive analysis steps\n"
        "- Context must reference specific numbers from prior runs\n"
        "- If hardware is available (GPUs, multiple CPU cores), plan to maximize utilization\n\n"
        "Write the plan to {output}. Do NOT modify any other files."
    ),
    "worker_execution": (
        "You are a research worker.\n\n"
        "Read {supervisor} section 4 (Worker Prompt Template) for the contract and rules.\n\n"
        "Read the report template at {report_template} — your output MUST use this exact structure "
        "with these exact section headings in this order: "
        "Summary, Motivation, Literature grounding, Method, Results (with sub-sections Data, Visualizations, Analysis), "
        "Signal, Verdict, Confounds, New hypotheses, Next tests, Artifacts, Meta.\n\n"
        "CRITICAL: Use the EXACT section headings from the template. Do not rename, reorder, "
        "or use alternative headings. The supervisor parses these by name.\n\n"
        "Your plan is in {input}. Execute the plan.\n\n"
        "Additional rules:\n"
        "- All data must be inline in tables (not just file references)\n"
        "- Generate visualizations and embed with ![description](path)\n"
        "- Signal must be one of: discriminating | partial | null\n"
        "- Verdict must be one of: supports | contradicts | unclear | BLOCKER, referencing a belief #\n"
        "- New hypotheses must include [parent: #N or —] hints\n"
        "- Save artifacts to tests/worker_execution/artifacts/\n\n"
        "Write the report to {output}. Do NOT modify any other files."
    ),
    "state_compression": (
        "You are a research supervisor.\n\n"
        "Read {supervisor} section 5 (State Compression Rules) for the exact update procedure.\n\n"
        "Read the state template at {state_template} — your output MUST follow this structure "
        "including: Parent and Literature columns in BeliefState, paradigm in Meta, "
        "and Uncertainty/Info gain/Feasibility columns in Frontier.\n\n"
        "The current state is in {state_before}.\n"
        "The report to ingest is in {report}.\n\n"
        "Apply compression rules:\n"
        "- Append to Ledger (use exact delta description from the report, not paraphrased)\n"
        "- Update belief confidence in the correct direction and magnitude\n"
        "- Add new beliefs from report's New hypotheses at confidence 0.5 with Parent field and Literature=pending\n"
        "- Add a literature-review frontier entry ahead of empirical deltas for every new belief\n"
        "- Remove completed delta from Frontier, add new entries for new beliefs\n"
        "- Score frontier entries on Uncertainty, Info gain, Feasibility and re-rank\n"
        "- Check for paradigm shift if any belief was rejected or dropped ≥0.3\n"
        "- Update Meta (total_runs, last_updated, paradigm if shift occurred)\n\n"
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
        "Your task: Generate ONLY the experiment.py and job.sh files. Do NOT actually submit anything.\n\n"
        "1. Write {experiment} — a self-contained Python script that:\n"
        "   - Includes the DELTA marker helper functions (from OBSERVABILITY)\n"
        "   - Implements ALL plan commands as Python code\n"
        "   - Has wandb.init/log/finish integration\n"
        "   - Emits DELTA-START at beginning, DELTA-PROGRESS at milestones, DELTA-DONE at end\n"
        "   - Has try/except with delta_blocker for fatal errors\n"
        "   - Uses flush=True on ALL prints\n\n"
        "2. Write {job} — a SLURM job script that:\n"
        "   - Has #SBATCH directives from the plan's SLURM section\n"
        "   - Uses the validated env activation from INFRA.md Job Execution\n"
        "   - Sets WANDB_PROJECT, WANDB_MODE, WANDB_RUN_NAME env vars\n"
        "   - Has --output=RUNS/R007/slurm-%j.out\n"
        "   - Launches python RUNS/R007/experiment.py\n\n"
        "Do NOT modify any other files."
    ),
}


def run_agent(test_name: str, agent: str = "claude"):
    """Spawn the agent for a test case."""

    templates = ROOT / "templates"

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
            job=TESTS / "slurm_job_generation" / "output_job.sh",
        )
    else:
        print(f"Unknown test: {test_name}")
        return

    print(f"\n--- Running {test_name} with {agent} ---")
    print(f"Prompt: {prompt[:120]}...")

    if agent == "claude":
        cmd = ["claude", "-p", prompt, "--allowedTools", "Read,Write,Bash,Edit"]
    elif agent == "codex":
        cmd = ["codex", "exec", "--full-auto", prompt]
    else:
        print(f"Unknown agent: {agent}")
        return

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            print(f"Agent exited with code {result.returncode}")
            if result.stderr:
                print(f"stderr: {result.stderr[:500]}")
        else:
            print(f"Agent completed successfully")
    except FileNotFoundError:
        print(f"Agent CLI '{agent}' not found in PATH")
    except subprocess.TimeoutExpired:
        print(f"Agent timed out after 300s")


def review_agent(test_name: str, agent: str = "claude"):
    """Spawn the agent to review a test output against templates."""

    templates = ROOT / "templates"

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
            output=output,
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
        job = TESTS / "slurm_job_generation" / "output_job.sh"
        review_output = TESTS / "slurm_job_generation" / "review_slurm.md"
        if not experiment.exists() and not job.exists():
            print(f"\n--- Skipping review of {test_name}: output files not found ---")
            return
        prompt = REVIEW_PROMPTS[test_name].format(
            supervisor=SUPERVISOR,
            log_protocol=templates / "OBSERVABILITY.md",
            plan=TESTS / "slurm_job_generation" / "PLAN.md",
            infra=TESTS / "slurm_job_generation" / "INFRA.md",
            experiment=experiment,
            job=job,
            review_output=review_output,
        )
        output = experiment  # for the exists() check below
    else:
        print(f"Unknown test: {test_name}")
        return

    if not output.exists():
        print(f"\n--- Skipping review of {test_name}: {output.name} not found ---")
        return

    print(f"\n--- Reviewing {test_name} with {agent} ---")

    if agent == "claude":
        cmd = ["claude", "-p", prompt, "--allowedTools", "Read,Write,Bash,Edit"]
    elif agent == "codex":
        cmd = ["codex", "exec", "--full-auto", prompt]
    else:
        print(f"Unknown agent: {agent}")
        return

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            print(f"Review agent exited with code {result.returncode}")
            if result.stderr:
                print(f"stderr: {result.stderr[:500]}")
        else:
            print(f"Review completed → {review_output.name}")
            # Print the review inline
            if review_output.exists():
                print()
                print(review_output.read_text())
    except FileNotFoundError:
        print(f"Agent CLI '{agent}' not found in PATH")
    except subprocess.TimeoutExpired:
        print(f"Review agent timed out after 300s")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global DEBUG

    parser = argparse.ArgumentParser(description="Test the research loop agent")
    parser.add_argument("--run", action="store_true", help="Generate outputs by spawning the agent")
    parser.add_argument("--review", action="store_true",
                        help="LLM reviews outputs against templates (checks quality, not just structure)")
    parser.add_argument("--agent", default="claude", help="Agent CLI to use (claude, codex)")
    parser.add_argument("--test", choices=["init", "plan", "worker", "compression", "slurm", "contracts", "all"], default="all",
                        help="Which test to run")
    parser.add_argument("--debug", action="store_true", help="Show parsed table data")
    args = parser.parse_args()

    DEBUG = args.debug

    tests_to_run = {
        "init": args.test in ("init", "all"),
        "plan": args.test in ("plan", "all"),
        "worker": args.test in ("worker", "all"),
        "compression": args.test in ("compression", "all"),
        "slurm": args.test in ("slurm", "all"),
        "contracts": args.test in ("contracts", "all"),
    }

    # Generate outputs if requested
    if args.run:
        if tests_to_run["init"]:
            run_agent("initialization", args.agent)
        if tests_to_run["plan"]:
            run_agent("plan_generation", args.agent)
        if tests_to_run["worker"]:
            run_agent("worker_execution", args.agent)
        if tests_to_run["compression"]:
            run_agent("state_compression", args.agent)
        if tests_to_run["slurm"]:
            run_agent("slurm_job_generation", args.agent)

    # LLM review if requested
    if args.review:
        if tests_to_run["init"]:
            review_agent("initialization", args.agent)
        if tests_to_run["plan"]:
            review_agent("plan_generation", args.agent)
        if tests_to_run["worker"]:
            review_agent("worker_execution", args.agent)
        if tests_to_run["compression"]:
            review_agent("state_compression", args.agent)
        if tests_to_run["slurm"]:
            review_agent("slurm_job_generation", args.agent)

    # Validate
    results = []

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

    sys.exit(1 if total_failed > 0 else 0)


if __name__ == "__main__":
    main()
