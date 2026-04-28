# Initialization

> Run this when STATE.md does not exist.
> The human is present. Use them — they know the project better than any README.

---

## Step 1: Understand the project and write agent instructions

### 1a: Read the codebase

Before talking to the human, scan the repo like a standard /init:
- Key files, project structure, languages, frameworks, what it does
- Entry points, configs, existing documentation
- Note anything relevant to research (data directories, model code, experiment scripts)

### 1b: Interview the human

The code reading gives you a head start. Use it. Don't ask the human things you can already see in the code — instead, lead with your understanding and let them correct or extend it.

**Do NOT dump all questions at once.** This is a conversation, not a form. One round at a time. Wait for the human's response before moving to the next round.

**Round 1 — Project context**:
Lead with what you learned from the code and present it to the human. For example: *"From reading the repo, this looks like [X] that does [Y]. The main entry point is [Z]. Is that right? What's the research question you're trying to answer?"*

Let the human confirm, correct, or add what's missing. Ask about what they've tried and what worked/didn't. Talk to human until you have a good understanding of the project and their research goals.

**Round 2 — Hypotheses** (dig deeper based on round 1):
Ask the human to list their hypotheses one by one. Do not dump all questions at once.
- What do you think is true but haven't proven? (these become seed beliefs)
- What are the competing explanations? (these shape the frontier)
- What would change your mind? (this defines what "discriminating" means)

**Round 3 — Reference repos**:
Before assuming the agent should build from scratch, ask:
- Are there existing repos, scaffolds, or codebases that this work should build on or reuse?
- Any reference implementations of the methods you want to test? (papers' official code, model weights, evaluation harnesses)
- Any internal/lab code that solves an adjacent problem you'd want to copy from?

Record these as paths or URLs in STATE.md Environment → "Reference repos". When the loop runs experiments, the agent should check this list first and reuse rather than re-implementing. **Building from scratch when a known good implementation exists is wasted work.**

**Round 4 — Practical setup**:
Ask the human to list their constraints one by one. Do not dump all questions at once.
- What does success look like? When would you stop?
- Any constraints — time budget, compute limits, things not to touch?
- Any irreversible actions to watch for?

Adapt the interview based on what the human says. If they mention something interesting, follow up. The goal is to extract their mental model of the problem — not just fill in template fields.

### 1c: Write CLAUDE.md / AGENTS.md

Detect which agent is running. Write or update the appropriate instruction file(s).

| Agent | Instruction file | Multi-agent config |
|-------|-----------------|-------------------|
| Claude Code | `CLAUDE.md` | N/A (Task tool built-in) |
| OpenAI Codex | `AGENTS.md` | `codex features enable multi_agent` |
| Cursor | `.cursorrules` | N/A |

If unsure, write both `CLAUDE.md` and `AGENTS.md`.

If CLAUDE.md or AGENTS.md already exists, read it first. Incorporate any useful existing content into the updated file — don't discard what's already there.

If there is a README.md, read it and include the important parts (project purpose, setup, key commands) — don't make the agent re-discover what's already documented.

The file should contain:

- **Project overview** — the goal is to give future agent sessions enough context to be productive immediately, without re-reading the whole codebase:
  - What the project does (one paragraph)
  - High-level architecture: how the major components fit together, data flow, key abstractions. Focus on the "big picture" that requires reading multiple files to understand — things an agent can't figure out from a single file
  - Key files and entry points (only the important ones, not an exhaustive listing — agents can discover the rest with tools)
  - Common commands: how to run the project, run tests, build, etc. For research projects this might be how to run experiments, launch training, evaluate models
  - Important gotchas, non-obvious conventions, or anything that would trip up a new contributor
  - Avoid: listing every file/directory (easily discovered), generic development practices, information that duplicates README.md verbatim
- **Research loop** section:
  - Research question and goals (from interview)
  - Key constraints (from interview)
  - How to run: `To continue research, say: "run the research loop"`

- **Reference: where to find what** (lookup table — agents should consult this when they need a spec, not guess):

  *delta-research framework specs (read-only — copied into the project as a git submodule, subtree, or directory):*

  | File | What's in it | When to read |
  |------|--------------|--------------|
  | `delta-research/templates/SUPERVISOR.md` | Full 7-phase loop spec, worker prompt template, state compression rules, bandit-based delta ranking, paradigm shift handling | When running the loop, designing a delta, or compressing state |
  | `delta-research/templates/OBSERVABILITY.md` | DELTA marker protocol, run directory structure (`logs/`, `metrics/`, `checkpoints/`, `artifacts/`, `scripts/`), full logging spec, SLURM execution workflow, failure recovery | When generating `experiment.py` or `job.sh`, debugging a failed run, or interpreting DELTA markers |
  | `delta-research/templates/WANDB_REPORTS.md` | wandb Report sub-agent spec — triggers, what to read, what to produce, plot quality rules | When a Report trigger fires (paradigm shift, belief resolved, every 5 runs) |
  | `delta-research/templates/INIT.md` | First-time initialization (interview, env setup, INFRA.md, SLURM test job) | Only when re-initializing — env change, new cluster, etc. |
  | `delta-research/templates/STATE.template.md` | Structure of STATE.md | When seeding STATE.md from scratch |
  | `delta-research/templates/PLAN.template.md` | Structure of PLAN.md (Delta, Resources, SLURM, Commands, Predictions, Success metrics, Stop conditions, Context, Meta) | When writing a plan in Phase 3 |
  | `delta-research/templates/REPORT.template.md` | Structure of REPORT.md (Summary, Method, Results with predicted-vs-actual, Signal, Verdict, Confounds, New hypotheses, Next tests, Meta) | When the worker is writing a report |
  | `delta-research/templates/INFRA.template.md` | Structure of INFRA.md (compute, optimization playbook, storage, cluster, job execution) | When (re)building INFRA.md |
  | `delta-research/scripts/wait_for_job.sh` | Blocking SLURM monitor — tails output for DELTA markers, exits on DONE/BLOCKER, has FIFO read + 30s safety net | Use it directly via `bash scripts/wait_for_job.sh <JOB_ID> <OUTPUT_FILE>`. Never reimplement. |

  *Runtime files (this project's working memory — written and updated by the loop):*

  | File / dir | What's in it | Owned by |
  |------------|--------------|----------|
  | `STATE.md` | Current beliefs, ledger, frontier, environment. **Read first in any research conversation.** | Supervisor (read+write). Workers never touch. |
  | `INFRA.md` | Hardware profile, optimization playbook, storage paths, cluster config, validated env activation | Init agent (write); supervisor + workers (read) |
  | `SYNTHESIS.md` | Human-facing narrative — what we've learned and where we are | Supervisor (write at paradigm shift / belief resolution) |
  | `REPORTS/R###.md` | Per-run reports — full data, plots, analysis, verdict | Worker (write); supervisor (read in Phase 5) |
  | `RUNS/R###/` | Per-run dir: `PLAN.md` (immutable), `experiment.py`, `job.sh`, `slurm-*.out`, `logs/`, `metrics/`, `checkpoints/`, `artifacts/`, `scripts/` | Supervisor writes PLAN.md; worker writes the rest |

  *When in doubt:*
  - Lost context after compaction? → re-read `STATE.md` (current state) + this CLAUDE.md/AGENTS.md (rules). For phase details, re-read `SUPERVISOR.md`.
  - Worker crashed? → read `RUNS/R###/logs/stderr.log` + `RUNS/R###/slurm-*.out`, then `OBSERVABILITY.md` Step 5 for recovery patterns.
  - Don't know which file format? → check `delta-research/templates/<name>.template.md`.

- **Loop discipline** (these are the patterns that get lost after context compaction. CLAUDE.md/AGENTS.md is reloaded every conversation, so put the rules here, not just in SUPERVISOR.md):

  **The 7 phases** (one cycle):
  1. Read STATE.md (beliefs, ledger, frontier)
  2. Select the highest-ranked delta from Frontier
  3. Write PLAN.md to `RUNS/R###/PLAN.md`
  4. Spawn a worker with the plan
  5. Ingest the worker's REPORT.md
  6. Compress STATE.md (update beliefs, append ledger, refresh frontier, update SYNTHESIS.md if a paradigm shifted)
  7. Loop back to phase 1

  **Hard contracts** (do not break these):
  - Workers NEVER modify STATE.md or PLAN.md
  - Plans are IMMUTABLE once created — no edits between create and execute
  - Workers suggest new directions ONLY via the report's "New hypotheses" and "Next tests" sections
  - Workers use ONLY resources specified in the plan's Resources section. If a resource is missing → BLOCKER.

  **A run is atomic**: phases 3–6 are one unit. Once a plan is approved (Phase 2), do NOT pause to ask "should I launch the script?" — launch it. Don't ask for permission between submit/wait/sync/report.

  **Smoke test before hero run**: For any non-trivial run (training, long benchmarks, anything >30 min), run the plan's `## Smoke Test` first — short walltime, fast-queue partition, 1 GPU, small data slice. Use it to validate paths, VRAM headroom, throughput, and refine the hero walltime estimate. A failed 4-hour run wastes 4 hours of compute *and* queue time. Skip only for runs <10 min, deterministic non-GPU analyses, or a near-identical config that succeeded in the last 24 hours. See OBSERVABILITY.md Step 0 for the procedure.

  **SLURM is one unit**: `sbatch` → `bash scripts/wait_for_job.sh ${JOB_ID} {OUTPUT_FILE}` → `wandb sync` (if offline) → write REPORT.md. No breaks. Do NOT manually poll `squeue` — `wait_for_job.sh` handles monitoring with FIFO-based reading and a 30s safety net.

  **Failure recovery is part of the run**: If a run hits DELTA-BLOCKER, non-zero exit, or missing output: read logs, diagnose (env issue, OOM, code bug, missing path), fix, re-run. Iterate up to 2-3 times. Only escalate to BLOCKER when the failure is truly unfixable without human input.

  **Interrupt boundaries** (the ONLY valid reasons to stop the loop):
  - BUDGET — time/compute budget exceeded
  - NULL_STREAK — N consecutive runs with null discrimination (N from STATE.md Policy)
  - BLOCKER — unrecoverable failure
  - AMBIGUITY — beliefs/frontier can't be updated without human input
  - IRREVERSIBLE — about to take an action that can't be undone

  **Autonomous operation**: The loop does NOT stop after a few runs. It cycles until an interrupt boundary triggers. Don't emit user-facing summaries between cycles.

  **State compression after each run** (Phase 6):
  - Append one row to STATE.md Ledger: `| R### | <delta> | <signal> | <verdict> | #N | [link](REPORTS/R###.md) |`
  - Update affected beliefs' confidence based on verdict + signal
  - Add new beliefs from "New hypotheses" (confidence 0.5)
  - Refresh Frontier — remove completed delta, add candidates from "Next tests"
  - Update SYNTHESIS.md narrative if a paradigm shifted or a belief resolved

  **Wandb Report triggers** (spawn the Report sub-agent — see WANDB_REPORTS.md):
  - Paradigm shift (core belief rejected, confidence dropped ≥ 0.3)
  - Belief resolved (reached `supported` or `rejected`)
  - Every 5 runs (periodic snapshot)

  **Worker spawning**:
  - Claude Code: `Task(subagent_type="general-purpose", prompt=<filled Worker Prompt Template from SUPERVISOR.md Section 4>)`
  - Codex: Spawn a sub-agent with the same filled template.

- **File management** rules (large files):
  - Checkpoints save to `RUNS/{RUN_ID}/checkpoints/` (per-run) or to the cluster checkpoint path from INFRA.md Storage. Add `RUNS/*/checkpoints/` and `checkpoints/` to `.gitignore`.
  - HuggingFace cache lives at the path from INFRA.md Storage (set `HF_HOME`). Never let it default to `~/.cache/huggingface`.
  - Datasets are read from the path in INFRA.md Storage — do not download into the project tree.

For Codex, enable multi-agent once before running the loop:
```bash
codex features enable multi_agent
```

If the user prefers manual configuration instead of the CLI helper, tell them to set:
```toml
[features]
multi_agent = true
```

For Codex, also add this section to `AGENTS.md` to prevent premature turn-ending:

```markdown
## Autonomous loop behavior (Codex-specific)

Codex has a default behavior of surfacing progress to the user and closing the turn cleanly after completing work. In the research loop, this is wrong — emitting a user-facing summary between cycles causes Codex to treat it as a turn completion point and stop.

Rules for the research loop:
- Do NOT emit user-facing progress messages between cycles. No "here's what I found so far." No "completed R003, ready for next pass."
- Do NOT treat "substantial progress" as a reason to yield control. The interrupt boundaries in STATE.md Policy are the ONLY valid reasons to stop.
- "Keep experiments short" means each experiment is fast to execute. It does NOT mean "run one cycle and stop." Short experiments = more cycles per session, not fewer.
- After updating STATE.md (Phase 7), go directly back to reading STATE.md (Phase 1). Do not produce any output between these steps.
- The only time you talk to the human is when an interrupt boundary fires.
```

---

## Step 2: Environment setup

Spawn an environment agent to handle setup. This is separate from the research loop — the supervisor does not manage conda, GPUs, or dependencies directly.

The environment agent should:
- Detect active conda/venv, confirm with human
- Check GPU availability if relevant (`nvidia-smi`). Record all available GPUs and set `CUDA_VISIBLE_DEVICES` to use all of them by default. Note the parallelism strategy (DataParallel, DistributedDataParallel, or independent runs per GPU).
- Check CPU cores (`nproc` / `sysctl -n hw.ncpu`) and record in Environment. Workers use this to set parallelism (e.g. num_workers, joblib n_jobs).
- Verify key dependencies are importable
- Install missing packages within the env

**Storage and downloads:**
- Check whether there are existing data, model checkpoints, or trained weights directories. If so, confirm with the human whether to use them
- If none exist, ask the human where to create them. Don't let models/datasets download to system defaults (e.g. `~/.cache/huggingface`) — confirm an explicit project-local or shared directory
- Record all paths in STATE.md so workers use the right locations

**Hardware profiling and INFRA.md:**

After basic environment setup, create INFRA.md from `templates/INFRA.template.md`. This gives workers a concrete optimization playbook instead of generic "use all GPUs" advice.

1. **Detect environment type:**
   - `which squeue sbatch 2>/dev/null` — if found, this is a SLURM cluster
   - `which qsub 2>/dev/null` — if found, this is PBS
   - If neither, treat as local machine

2. **For local machines — auto-profile:**
   Run these commands and fill INFRA.md from the results:
   - GPUs: `nvidia-smi --query-gpu=index,name,memory.total,driver_version --format=csv,noheader,nounits`
   - Compute capability: `python -c "import torch; print([(i, torch.cuda.get_device_capability(i)) for i in range(torch.cuda.device_count())])"`
   - GPU topology: `nvidia-smi topo -m` (may not be available on all systems)
   - CUDA version: `python -c "import torch; print(torch.version.cuda)"` (or `nvcc --version`)
   - CPU: `lscpu` (Linux) or `sysctl -n machdep.cpu.brand_string && sysctl -n hw.ncpu` (macOS)
   - RAM: `free -h` (Linux) or `python -c "import os; print(f'{os.sysconf(\"SC_PAGE_SIZE\") * os.sysconf(\"SC_PHYS_PAGES\") / (1024**3):.0f} GB')"` (macOS)
   - Storage: `df -h` on working dir, dataset, and checkpoint paths. Detect NFS: `df -T` (Linux) or `mount`. Detect SSD vs HDD: `lsblk -d -o NAME,ROTA` (Linux, ROTA=0 means SSD)
   - PyTorch version and features: `python -c "import torch; print(torch.__version__); print('compile:', hasattr(torch, 'compile')); print('SDPA:', hasattr(torch.nn.functional, 'scaled_dot_product_attention'))"`
   - Accelerator packages: try importing each in Python and record version or "not installed":
     `torch`, `flash_attn`, `deepspeed`, `accelerate`, `apex`, `bitsandbytes`, `xformers`, `triton`, `vllm`
   - Fused optimizer support: `python -c "import torch; print('fused_adam:', 'fused' in torch.optim.AdamW.__init__.__code__.co_varnames)" 2>/dev/null`; also check for apex FusedAdam

3. **For clusters — probe, then interview:**

   Cluster setup is two-step: probe what the scheduler exposes (objective facts), then interview the human about policies and conventions (subjective rules — not discoverable from commands).

   **Step A: Probe the scheduler.** Run on the login node (or hand to the human if remote):

   ```bash
   echo "=== PARTITIONS ===" && sinfo -o "%P %a %l %D %G %N" 2>/dev/null | head -30
   echo "=== USER ACCOUNTS ===" && sacctmgr show user $USER format=user,account,defaultaccount -P 2>/dev/null
   echo "=== QOS ===" && sacctmgr show qos format=name,maxwall,maxtres,priority -P 2>/dev/null | head -20
   echo "=== FAIRSHARE ===" && sshare -U 2>/dev/null
   echo "=== AVAILABLE MODULES ===" && module avail cuda anaconda3 2>&1 | head -30
   echo "=== LOADED MODULES ===" && module list 2>&1
   echo "=== HOME QUOTA ===" && quota -s 2>/dev/null
   echo "=== MOUNTED FILESYSTEMS ===" && df -hT 2>/dev/null | grep -iE "lustre|gpfs|nfs|panfs|beegfs|home|scratch|work"
   echo "=== HOME SIZE ===" && du -sh $HOME 2>/dev/null
   echo "=== GPU ===" && nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader,nounits 2>/dev/null || echo "no GPUs on login node"
   ```

   This populates: partition list, accounts, QOS, module versions, mount points, quotas. **Don't assume defaults from the probe alone** — the human knows which paths/partitions are *appropriate*, not just *available*.

   **Step B: Interview the human about cluster policy.** One round at a time, not all at once. Lead with what the probe found and ask for confirmation/extension.

   *Round 1 — Storage policy* (the most common source of failure — defaults are wrong on most clusters):
   > "I see these mounts: [list from `df -hT`]. Where should I store:
   > - Datasets / large input data?
   > - Model checkpoints and intermediate outputs?
   > - Scratch / temporary files (per-run, can be purged)?
   > - HuggingFace cache (model downloads — can be tens of GB)?
   >
   > I'll avoid your home directory for large files unless you say otherwise. Is there a shared group storage path I should know about?"

   *Round 2 — Partition policy*:
   > "I see these partitions: [list from `sinfo`]. Which should I use for typical runs? Is there a fast-queue partition for short tests (e.g. `gpu-debug`)? Any partition-specific rules?"

   *Round 3 — Account, QOS, fairshare*:
   > "Your accounts: [from `sacctmgr`]. Default: [X]. Any QOS conventions for your group? Any fairshare considerations (e.g. lab quota shared with N people, long jobs reduce others' priority)?"

   *Round 4 — Conventions and forbidden actions*:
   > "Anything else I should know — walltime conventions (e.g. 'always request the minimum'), forbidden actions (e.g. 'never run on login node'), local quirks of this cluster, lab rules?"

   *Round 5 — Documentation*:
   > "Is there a cluster documentation URL or wiki I should read?" If yes, WebFetch it and extract anything else relevant.

   **Step C: Fill INFRA.md Cluster section** combining probe output + interview answers. Quotas, mount paths, and partition list come from the probe; storage policy, fairshare considerations, and conventions come from the human. Then fill Storage → Paths from the storage policy answers.

4. **For remote clusters (can't run commands locally):**
   - Hand the probe block from step 3A to the human, ask them to run it on the cluster and paste back the output
   - Then conduct the same interview (steps 3B and 3C) — same questions, just no live probe
   - Also confirm the project root path and conda env path explicitly, since you can't verify them locally

5. **Derive the Optimization Playbook:**
   Use these rules to fill each playbook section. The template (INFRA.template.md) has detailed comments for each — follow those for the full decision tree.

   *Precision:*
   - cc >= 9.0 (H100, H200, B200) → BF16 native, note FP8 available for supported ops
   - cc >= 8.0 (A100, L40S) → BF16 (native, no loss scaling needed)
   - cc 7.0–7.5 (V100, T4) → FP16 with AMP (GradScaler required)
   - Below 7.0 or no GPU → FP32
   - For Ampere+: enable TF32 (`torch.backends.cuda.matmul.allow_tf32 = True`)

   *Attention:*
   - flash-attn >= 4.0 + cc >= 10.0 (B200) → Flash Attention 4
   - flash-attn >= 3.0 + cc >= 9.0 (H100/H200) → Flash Attention 3
   - flash-attn >= 2.0 + cc >= 8.0 → Flash Attention 2
   - PyTorch >= 2.2 → SDPA with Flash backend auto-selection
   - PyTorch >= 2.0 → SDPA basic
   - Neither → standard (flag as slow for long sequences)

   *Compilation:*
   - PyTorch >= 2.0 + triton installed → `torch.compile` available
   - Recommend `"reduce-overhead"` mode for training, `"max-autotune"` for inference
   - Note first-iteration compilation cost and dynamic shape caveats

   *Parallelism:*
   - 0 GPUs → CPU multiprocessing (`n_jobs` = core count)
   - 1 GPU → single GPU
   - 2+ GPUs, model fits 1 GPU → DDP with `torchrun --nproc_per_node=N`
   - 2+ GPUs, model doesn't fit → FSDP SHARD_GRAD_OP (ZeRO-2) or FULL_SHARD (ZeRO-3)
   - Prefer FSDP over gradient checkpointing when multiple GPUs are available
   - Note `accelerate` if installed (simplified multi-GPU launch for HF workflows)

   *Data loading:*
   - num_workers: ~4 per GPU (adjust based on CPU core count)
   - Always: `pin_memory=True`, `persistent_workers=True`
   - prefetch_factor: 2-4 (increase if data is on network storage)

   *Training efficiency:*
   - Fused optimizers: `AdamW(fused=True)` on PyTorch 2.0+, or apex FusedAdam
   - cudnn benchmark: `True` for fixed-size inputs
   - channels_last for CNN workloads on Ampere+

   *GPU-CPU transfer pitfalls:*
   - Fill from the template — these are static rules, not hardware-dependent

6. **Fill INFRA.md** from `templates/INFRA.template.md` with all detected and derived information.

7. **Identify optimization gaps and act on them:**

   After filling INFRA.md, compare what's installed against what the hardware supports. For each gap, add a row to the "Recommended Optimizations" table in INFRA.md with a concrete command.

   *Common gaps to check:*

   | Condition | Recommendation | Impact |
   |-----------|---------------|--------|
   | cc >= 8.0 but `flash-attn` not installed | `pip install flash-attn --no-build-isolation` | high |
   | `torch.compile` available but `triton` not installed | `pip install triton` | medium |
   | Multi-GPU but `accelerate` not installed (HF workflows) | `pip install accelerate` | medium |
   | HF_HOME on slow storage (NFS, HDD) | Move to fast scratch + set `HF_HOME` in shell rc | medium |
   | PyTorch < 2.0 (missing compile, SDPA, fused AdamW) | Upgrade: `pip install torch>=2.4 --index-url ...` | high |
   | Multi-GPU but no `deepspeed` (needed for large models) | `pip install deepspeed` | medium |
   | No quantization support but may need it for inference | `pip install bitsandbytes` | low |
   | `vllm` not installed but project does batched LLM inference | `pip install vllm` | medium |

   **Present the recommendations to the human as a numbered list.** For example:
   > I found these optimization opportunities for your hardware:
   > 1. **[high]** Install Flash Attention 2 — your A100s support it but flash-attn isn't installed. `pip install flash-attn --no-build-isolation`
   > 2. **[medium]** Install Triton — needed for torch.compile inductor backend. `pip install triton`
   > 3. **[medium]** Move HF cache to /scratch — currently on NFS which is slow for model downloads.
   >
   > Which ones should I install? (all / 1,2 / none)

   **After the human responds:**
   - Execute approved optimizations (run the pip install commands, update shell config, etc.)
   - For each applied optimization, update the row in the Recommended Optimizations table: status → `applied`
   - For each declined optimization, update status → `skipped`
   - **Re-derive affected Playbook sections** — e.g., if flash-attn was just installed, update the Attention section from "SDPA" to "Flash Attention 2" with the correct usage example
   - Verify the installation worked (try importing the package, check version)

   If all recommendations are low-impact or the human declines everything, that's fine — the table still serves as documentation of what could be improved later.

**Logging and observability (wandb setup):**

1. Ask the human: "Do you want to use wandb for experiment tracking and Reports? (recommended for observability)"
2. If yes:
   - **Check/install**: `python -c "import wandb; print(wandb.__version__)"` — if missing, `pip install wandb`
   - **Project**: ask for project name (default: repo name) and entity/team (or use default)
   - **Authentication**: check `wandb login --verify` — if not logged in, tell the human to run `wandb login` (this requires interactive input)
   - **Run naming**: configure so wandb runs match STATE.md ledger: run name = `R001`, `R002`, etc.
   - **Connectivity check**: determine if wandb can reach the API from this machine. If on a cluster, compute nodes may not have internet access — test with a short `wandb.init()` / `wandb.finish()` call
   - **Mode decision**:
     - Online (default): metrics stream live to wandb dashboard
     - Offline: metrics saved locally, synced later with `wandb sync`. Use when compute nodes lack internet.
     - Disabled: no wandb. The loop still works — DELTA markers provide basic observability.
3. Record in INFRA.md `Job Execution` section: `wandb mode`, `wandb project`, `wandb entity`
4. Record in STATE.md Environment section: `wandb project`, `wandb entity`
5. Add to CLAUDE.md/AGENTS.md: wandb project name, mode, and instructions for future sessions

**SLURM test job (when scheduler != N/A):**

Before committing to the SLURM setup, validate that experiments can actually run on compute nodes. This catches common issues (wrong conda path, missing modules, no GPU access) before they waste real experiment time.

The test script emits DELTA markers so `scripts/wait_for_job.sh` is validated simultaneously.

Generate and submit a test job with two phases:

*Phase 1 — Essentials (fail fast):*

```python
# test_slurm.py — generated by init agent
import sys
from datetime import datetime, timezone

def delta_start():
    print(f"[DELTA-START] TEST | {datetime.now(timezone.utc).isoformat()}", flush=True)
def delta_progress(pct, msg=""):
    print(f"[DELTA-PROGRESS] {pct}% | {msg}", flush=True)
def delta_done(elapsed):
    print(f"[DELTA-DONE] TEST | elapsed={elapsed} | status=completed", flush=True)
def delta_blocker(msg):
    print(f"[DELTA-BLOCKER] TEST | {msg}", flush=True)
    sys.exit(1)

delta_start()

# 1. Python works
delta_progress(10, "Python interpreter OK")

# 2. Key imports
try:
    import torch
    import numpy
    delta_progress(20, f"torch={torch.__version__}, numpy={numpy.__version__}")
except ImportError as e:
    delta_blocker(f"Import failed: {e}")

# 3. GPU accessible
if not torch.cuda.is_available():
    delta_blocker("torch.cuda.is_available() returned False")
gpu_count = torch.cuda.device_count()
gpu_names = [torch.cuda.get_device_name(i) for i in range(gpu_count)]
delta_progress(30, f"GPUs: {gpu_count}x {gpu_names[0]}")

# 4. Write permissions — use absolute paths from INFRA.md project root
import os, tempfile
PROJECT_ROOT = os.environ.get("PROJECT_ROOT", os.getcwd())
write_paths = [
    os.environ.get("SCRATCH_PATH", "/tmp"),
    os.path.join(PROJECT_ROOT, "RUNS"),
]
for path in write_paths:
    try:
        os.makedirs(path, exist_ok=True)
        test_file = os.path.join(path, ".delta_write_test")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
    except Exception as e:
        delta_blocker(f"Cannot write to {path}: {e}")
delta_progress(40, f"Write permissions OK (project root: {PROJECT_ROOT})")

# 5. Project root accessible
if not os.path.isdir(PROJECT_ROOT):
    delta_blocker(f"Project root not accessible: {PROJECT_ROOT}")
delta_progress(45, "Project root accessible")
```

*Phase 2 — Extended (only if Phase 1 passes):*

```python
# 6. CUDA operations
try:
    a = torch.randn(1024, 1024, device="cuda")
    b = torch.randn(1024, 1024, device="cuda")
    c = a @ b
    torch.cuda.synchronize()
    delta_progress(50, "CUDA matmul OK")
except Exception as e:
    delta_blocker(f"CUDA operation failed: {e}")

# 7. Multi-GPU NCCL (if > 1 GPU)
if gpu_count > 1:
    try:
        import torch.distributed as dist
        os.environ.setdefault("MASTER_ADDR", "localhost")
        os.environ.setdefault("MASTER_PORT", "29500")
        # Note: full NCCL test requires torchrun; basic check here
        delta_progress(55, f"Multi-GPU: {gpu_count} GPUs detected, NCCL test requires torchrun")
    except Exception as e:
        delta_progress(55, f"Multi-GPU check skipped: {e}")

# 8. wandb connectivity
try:
    import wandb
    wandb_mode = os.environ.get("WANDB_MODE", "online")
    if wandb_mode == "online":
        wandb.init(project="delta-test", name="slurm-test", mode="online")
        wandb.log({"test": 1.0})
        wandb.finish()
        delta_progress(65, "wandb online OK")
    else:
        delta_progress(65, f"wandb mode={wandb_mode}, skipping connectivity test")
except Exception as e:
    delta_progress(65, f"wandb failed (will use offline mode): {e}")

# 9. Network access
try:
    import urllib.request
    urllib.request.urlopen("https://huggingface.co", timeout=5)
    delta_progress(70, "Network access: OK (HuggingFace reachable)")
except Exception:
    delta_progress(70, "Network access: BLOCKED (compute nodes have no internet)")

# 10. Disk I/O speed
import time
scratch = os.environ.get("SCRATCH_PATH", "/tmp")
test_file = os.path.join(scratch, ".delta_io_test")
data = b"x" * (100 * 1024 * 1024)  # 100MB
start = time.time()
with open(test_file, "wb") as f:
    f.write(data)
write_speed = 100 / (time.time() - start)
start = time.time()
with open(test_file, "rb") as f:
    _ = f.read()
read_speed = 100 / (time.time() - start)
os.remove(test_file)
delta_progress(80, f"Disk I/O on {scratch}: write={write_speed:.0f} MB/s, read={read_speed:.0f} MB/s")

# 11. All accelerator packages
for pkg in ["flash_attn", "deepspeed", "accelerate", "apex", "bitsandbytes", "xformers", "triton", "vllm"]:
    try:
        mod = __import__(pkg)
        ver = getattr(mod, "__version__", "unknown")
        delta_progress(85, f"{pkg}={ver}")
    except ImportError:
        delta_progress(85, f"{pkg}: not installed")

# 12. Storage paths from INFRA.md — validate all configured paths are accessible
storage_paths = os.environ.get("DELTA_STORAGE_PATHS", "").split(":")
for sp in storage_paths:
    sp = sp.strip()
    if not sp:
        continue
    if os.path.exists(sp):
        is_readable = os.access(sp, os.R_OK)
        is_writable = os.access(sp, os.W_OK)
        delta_progress(90, f"Path OK: {sp} (read={is_readable}, write={is_writable})")
    else:
        delta_progress(90, f"Path MISSING: {sp} — not accessible from compute node")

import time as _time
delta_done("test complete")
```

The init agent should set `DELTA_STORAGE_PATHS` in the test job script as a colon-separated list of all paths from INFRA.md Storage (datasets, checkpoints, scratch, HuggingFace cache) plus any model/dataset paths discovered during setup. This catches the common failure mode where a path is visible from the login node but not mounted on compute nodes.

**Submit the test job:**
1. Generate `test_slurm.py` with both phases above
2. Generate `test_job.sh` using INFRA.md submission template with minimal resources (1 GPU, 10 min walltime, 16GB memory)
3. Set `#SBATCH --output={PROJECT_ROOT}/RUNS/test_slurm-%j.out` (absolute path — resolved before any commands run)
4. Add `export PROJECT_ROOT={project_root}` and `export DELTA_STORAGE_PATHS={colon-separated paths from INFRA.md Storage}` to the job script
5. Submit: `JOB_ID=$(sbatch --parsable {PROJECT_ROOT}/RUNS/test_job.sh)`
6. Monitor: `bash scripts/wait_for_job.sh ${JOB_ID} {PROJECT_ROOT}/RUNS/test_slurm-${JOB_ID}.out 600`

**On failure:**
- Read the full output — diagnose what failed
- Common fixes: use absolute conda path (`/opt/conda/bin/conda activate ...`), different module version, set `WANDB_MODE=offline`
- Fix, regenerate, resubmit. Iterate until Phase 1 passes.
- Phase 2 failures are informational — record issues but don't block init

**On success:**
- Save the validated env activation sequence to INFRA.md `Job Execution → validated env activation`
- Set `test job status: passed` in INFRA.md
- Record any notes (e.g. "compute nodes have no internet — using WANDB_MODE=offline")
- Set INFRA.md `Job Execution → mode: slurm`

**Wrap up:**
- Record everything in STATE.md Environment section
- Update CLAUDE.md/AGENTS.md with environment-specific commands and paths (so future sessions don't need to re-discover them)

**Agent-specific spawning:**
- **Claude Code**: `Task(subagent_type="general-purpose", prompt="Set up and verify the research environment. <details from interview>. Record in STATE.md Environment section.")`
- **Codex**: Spawn a sub-agent for environment setup.

The environment can be re-invoked later (new model, GPU change) without touching research state.

---

## Step 3: Set up permissions for autonomous operation

The research loop runs shell commands (python scripts, data processing, etc.). Configure permissions so the loop can run without approval prompts interrupting it.

**Claude Code** — create or update `.claude/settings.local.json`:
```json
{
  "permissions": {
    "allow": [
      "Bash(python:*)",
      "Bash(python3:*)",
      "Bash(pip install:*)",
      "Bash(conda:*)",
      "Bash(mkdir:*)"
    ]
  }
}
```
For full autonomy (if the human agrees), use `"allow": ["Bash(*)"]`. The conda/venv env is the safety boundary.

**Codex** — runs in a sandboxed container by default, so permissions are less of a concern. Use `--full-auto` flag when launching. Ensure the container image has the right conda env and dependencies pre-installed, or let the agent install them.

**Other agents** — configure equivalent auto-approval for shell commands per the agent's docs.

Ask the human which permission level they want before writing the config. Show them the options:
1. **Scoped** (recommended): python, pip, conda, mkdir only
2. **Full autonomy**: all shell commands (`Bash(*)`)
3. **Manual**: no auto-permissions, approve each command

---

## Step 4: Create project structure

```
mkdir -p REPORTS RUNS
```

---

## Step 5: Create STATE.md

Use `templates/STATE.template.md` as structure. Fill in from the interview:
- Project name, goal, date
- Seed beliefs from the human's hypotheses (confidence 0.5)
- Initial frontier: deltas that would discriminate between competing hypotheses
- Policy: budget, interrupt thresholds
- Environment section populated by environment agent
- INFRA.md populated by environment agent (detailed hardware profile and optimization playbook — STATE.md Environment stays minimal)

Also create initial SYNTHESIS.md from templates/SYNTHESIS.template.md with project name, goal, and seed beliefs.

---

## Step 6: Confirm with human

Show STATE.md and the written CLAUDE.md/AGENTS.md. Are the seed beliefs right? Is the frontier targeting the right questions? Anything missing from the environment setup? Are permissions configured correctly?

Once confirmed, tell the human: *"To start the research loop, say: run the research loop"*. The agent will then read `templates/SUPERVISOR.md` and begin cycling.
