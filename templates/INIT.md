# Initialization

> Run this when STATE.md does not exist.
> The human is present. Use them — they know the project better than any README.

Reuse answers and authorization already provided in this session or project. Ask
only for missing decisions; do not repeat interviews, GPU counts or permission requests.

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
- What is the smallest experiment that could produce that evidence? (this becomes the first direct frontier entry)

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
- If GPUs are available, how many GPUs may each experiment use? Record the exact confirmed count; do not infer it
  from the number detected.
- Any irreversible actions to watch for?

Adapt the interview based on what the human says. If they mention something interesting, follow up. The goal is to extract their mental model of the problem — not just fill in template fields.

### 1c: Write CLAUDE.md / AGENTS.md

Detect which agent is running. Write or update the appropriate instruction file(s).

| Agent | Instruction file | Multi-agent config |
|-------|-----------------|-------------------|
| Claude Code | `CLAUDE.md` | N/A (Task tool built-in) |
| OpenAI Codex | `AGENTS.md` | Project defaults from `templates/codex.config.toml` |
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
### Install the compact loop instructions

Append the managed block from `templates/AGENTS.fragment.md` to the project instruction
file. On updates replace only the block between `delta-research:begin` and
`delta-research:end`; preserve project-specific instructions, resource paths and recorded
authorization outside it. The fragment is the canonical compact contract; do not copy
whole supervisor phases, worker prompts, report scaffolds, or hardware playbooks into
AGENTS.md/CLAUDE.md. PLAN.md is a working guide, not an immutable contract, normally
≤5 minutes and always ≤10 minutes to write.

For an older unmarked installation, identify the old framework-only rules and reconcile
them with this fragment while preserving user-specific content. In particular, remove
obsolete automatic W&B triggers, automatic `at` scheduling and instructions to skip
publication after compression. Record fragment version v2 in STATE.md Environment.
Do not rewrite generated `.delta-loop/LOOP.md` or `.delta-loop/POLICY.md`.

For Codex, merge `templates/codex.config.toml` into the project's `.codex/config.toml`
and install `templates/research-worker.toml` as `.codex/agents/research-worker.toml`.
Preserve existing explicit user model, effort, permission and other configuration
choices; keep the two worker-model settings consistent when applying a user override.
The default is an Astra supervisor and Sol workers at medium effort. Do not silently
inherit the supervisor's model. Use the current host's supported configuration; if a
host uses explicit spawn arguments, pass the same model/effort there. Do not downgrade
or upgrade silently when a configured model is unavailable. Record the effective
supervisor/worker model and effort in STATE.md Environment.

Current Codex supports `agents.enabled`, `agents.default_subagent_model` and
`agents.default_subagent_reasoning_effort`; older installations may require the legacy
`codex features enable multi_agent` switch. Verify the installed CLI before applying
settings. See the [official subagent configuration](https://learn.chatgpt.com/docs/agent-configuration/subagents).

Use `templates/RUNTIME.md` for journal setup and host-specific continuation. Record the
human's cumulative deadline once and preserve it through retries and resumed sessions.

---

## Step 2: Environment setup

Spawn an environment agent to handle setup. This is separate from the research loop — the supervisor does not manage the Python env, GPUs, or dependencies directly.

The environment agent should:
- Detect the active Python environment and which manager owns it, confirm with human. Supported managers:
  - **conda / mamba**: `conda env list`, `echo $CONDA_PREFIX`, `mamba env list`
  - **uv**: `which uv`, look for `pyproject.toml` + `uv.lock`, `.venv/` in project root, `echo $VIRTUAL_ENV`
  - **plain venv**: `echo $VIRTUAL_ENV`, look for `.venv/bin/activate` or `venv/bin/activate`
  - **pixi**: `which pixi`, look for `pixi.toml` / `pixi.lock`
  - **poetry**: `which poetry`, look for `pyproject.toml` with `[tool.poetry]`
  Record the manager (`conda` / `mamba` / `uv` / `venv` / `pixi` / `poetry`) and the exact activation command in STATE.md Environment and INFRA.md.
- Check GPU availability if relevant (`nvidia-smi`). Record all available GPUs. Detection is not allocation
  permission: ask the human for the exact GPU count approved for experiment jobs and record it
  in STATE.md and INFRA.md. Once `N` is confirmed, every GPU experiment allocates all `N`, assigns useful work to each,
  and uses the layout with the shortest wall-clock time to the complete answer.
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
   echo "=== AVAILABLE MODULES ===" && module avail cuda anaconda3 python uv 2>&1 | head -40
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
   - Also confirm the project root path and env path (conda env / uv-or-venv `.venv` / pixi prefix) explicitly, since you can't verify them locally

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
   - 2+ confirmed GPUs, model fits 1 GPU → DDP across all confirmed GPUs with `torchrun --nproc_per_node=N`
   - 2+ GPUs, model doesn't fit → FSDP SHARD_GRAD_OP (ZeRO-2) or FULL_SHARD (ZeRO-3)
   - Do not use tensor parallelism when DDP can run the same work. Tensor/model sharding is a fallback only when a
     replica cannot fit on one GPU or the required operation cannot be divided into independent per-GPU work.
   - For independent experiment arms or seeds, run them concurrently across confirmed GPUs when that is faster and
     does not bias the comparison. If runtime is the measured outcome, give each condition the same all-GPU layout.
   - Collect wall-clock, throughput, and per-rank sample/batch counts inside the real experiment; this is not a
     separate utilization test or gate.
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

Before committing to the SLURM setup, validate that experiments can actually run on compute nodes. This catches common issues (wrong env activation path, missing modules, no GPU access, env not visible from compute filesystem) before they waste real experiment time.

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
6. Monitor: `bash {FRAMEWORK_ROOT}/scripts/wait_for_job.sh ${JOB_ID} {PROJECT_ROOT}/RUNS/test_slurm-${JOB_ID}.out 600`

**On failure:**
- If monitoring times out or accounting is unknown, reconcile the existing job first;
  do not resubmit while it may still be running. Preserve a unique log for each attempt.
- Read the full output — diagnose what failed
- Common fixes by env manager:
  - **conda/mamba**: use absolute path (`source /opt/conda/etc/profile.d/conda.sh && conda activate <env>`) — `conda activate` alone often fails under sbatch because `.bashrc` isn't sourced
  - **uv / venv**: use absolute path to activate (`source /abs/path/.venv/bin/activate`) and confirm the venv lives on a filesystem mounted on compute nodes (NOT `/home` on some clusters). Alternatively prepend the venv's `bin/` to `PATH` and skip activation entirely
  - **pixi**: `eval "$(pixi shell-hook --manifest-path /abs/path/pixi.toml)"`
  - module mismatches: try a different cuda/python module version
  - wandb network blocked: set `WANDB_MODE=offline`
- Fix, regenerate, resubmit. Iterate until Phase 1 passes.
- Phase 2 failures are informational — record issues but don't block init

**On success:**
- Save the validated env activation sequence to INFRA.md `Job Execution → validated env activation`
- Set `test job status: passed` in INFRA.md
- Record any notes (e.g. "compute nodes have no internet — using WANDB_MODE=offline")
- Set INFRA.md `Job Execution → mode: slurm`

**Wrap up:**
- The environment worker writes INFRA.md and returns a compact summary with exact commands and paths.
- The supervisor records the Environment section in STATE.md and updates project-specific
  commands in CLAUDE.md/AGENTS.md; the environment worker does not edit these shared files.

**Agent-specific spawning:**
- **Claude Code**: `Task(subagent_type="general-purpose", model="sonnet", prompt="Set up and verify the research environment. <details from interview>. Write INFRA.md and return the environment summary to the supervisor.")`
- **Codex**: Spawn environment setup with explicit `gpt-5.6-sol` / `medium`, or the
  configured cheaper worker. Pass only the interview answers, exact paths and setup scope.

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
      "Bash(mamba:*)",
      "Bash(uv:*)",
      "Bash(source:*)",
      "Bash(mkdir:*)"
    ]
  }
}
```
For full autonomy (if the human agrees), use `"allow": ["Bash(*)"]`. The active Python env (conda/uv/venv) is the safety boundary — package installs land there, not system-wide.

**Codex** — use the host's configured sandbox and `--approve-for-me` for automatic
approval review when available. Verify access to the project and shared storage. Prepare
the required Python environment and dependencies during init; do not assume a container
or change permissions to bypass a failed approval review.

**Other agents** — configure equivalent auto-approval for shell commands per the agent's docs.

Ask the human which permission level they want before writing the config. Show them the options:
1. **Scoped** (recommended): python, pip, uv, conda/mamba, source (for venv activation), mkdir only
2. **Full autonomy**: all shell commands (`Bash(*)`)
3. **Manual**: no auto-permissions, approve each command

### GitHub publication authorization

Separately ask whether the loop is authorized to stage, commit, and push after every completed run. These are
distinct external-write actions; record the answer in STATE.md Environment and CLAUDE.md/AGENTS.md. If authorized:

- Inspect `git remote -v`, current/default branches, working-tree status, and GitHub authentication.
- Configure a non-default research branch (for example `codex/research-loop`) for run commits. Do not commit run work
  directly to the default branch.
- Record the exact remote and research branch in STATE.md.
- Reference the Phase 6b contract from the managed instruction fragment. Add
  `.delta-runtime/` to the project gitignore; operational state remains local. Keep
  explicit staging, relevant checks, atomic run commit, verified push and no force-push.
- If authorization is declined or manual, Phase 6b stops at `IRREVERSIBLE` and asks before each commit/push.

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
- Set `last_experimental_evidence: none` and `direction_recovery_used_since_experiment: false`
- Initial frontier: add only a few decision-capable experiment questions with exact decision results, minimum
  complete evidence packages, total ETAs, and entry points; shortest adequate package ranks first
- Policy: budget, interrupt thresholds
- Environment section populated by environment agent
- INFRA.md populated by environment agent (detailed hardware profile and optimization playbook — STATE.md Environment stays minimal)

Also create initial SYNTHESIS.md from templates/SYNTHESIS.template.md with project name, goal, and seed beliefs.

---

## Step 6: Confirm with human

Show STATE.md and the written CLAUDE.md/AGENTS.md. Are the seed beliefs right? Does each top frontier item create a
new observation that could change one of them? Is the first experiment the shortest useful test of the goal?
Anything missing from the environment setup? Are permissions configured correctly? Is the Git remote/research
branch correct, and is the recorded commit/push authorization accurate?

Validate `squeue` and `sacct` access in SLURM mode; the monitor requires accounting
completion and exit status. Confirm the installed Python can run the standard-library
helpers. Then, once confirmed, tell the human: *"To start the research loop, say: run the research loop"*. The agent will then read `templates/SUPERVISOR.md` and begin cycling.
