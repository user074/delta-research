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

**Round 3 — Practical setup**:
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
| OpenAI Codex | `AGENTS.md` | `codex.toml` or project config |
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
  - Pointer: `See delta-research/templates/SUPERVISOR.md for the loop spec`
  - Pointer: `Current state (beliefs, what's been tried, frontier) lives in STATE.md`
  - Pointer: Human-readable summary lives in SYNTHESIS.md
  - How to run: `To continue research, say: "run the research loop"`
  - **Autonomous operation rule**: The loop does NOT stop after a few runs. It keeps cycling until an interrupt boundary triggers (budget exceeded, blocker, ambiguity).

For Codex, also enable multi-agent in config:
```toml
[features]
multi_agent = true

[agents.worker]
description = "Research worker: executes a single experiment plan, writes a structured report. Never modifies STATE.md or PLAN.md."
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

3. **For clusters — assisted profile:**
   - Ask the human: "I detected a SLURM/PBS cluster. Do you have documentation I can read? Provide a URL, or paste the relevant info (partitions, GPU types, module loads, quotas, storage paths)."
   - If URL provided: use WebFetch to read the documentation, extract partition names, GPU types, module loads, walltime limits, storage topology
   - If human pastes text: parse it directly
   - Also run what's available locally: `sinfo -N -l`, `module avail cuda 2>&1 | head -10`, `scontrol show partition`, `df -h`

4. **For remote clusters (can't access from here):**
   - Give the human a compact command block to run on the cluster and paste back:
     ```
     echo "=== GPU ===" && nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader,nounits 2>/dev/null || echo "No GPUs"
     echo "=== CPU ===" && lscpu | grep -E 'Model name|^CPU\(s\)|Thread'
     echo "=== RAM ===" && free -h | head -2
     echo "=== SLURM ===" && sinfo -N -l 2>/dev/null | head -20
     echo "=== MODULES ===" && module avail cuda 2>&1 | head -10
     echo "=== STORAGE ===" && df -h /home /scratch /tmp 2>/dev/null
     ```
   - Parse the pasted output to fill INFRA.md

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

**Logging and observability:**
- Ask whether to use wandb (or similar: tensorboard, mlflow) for experiment tracking
- If yes: project name, entity/team, whether to create a new project or use an existing one
- Configure run naming so logs map back to research loop runs (e.g. run name = `R001`, `R002` matching STATE.md ledger)
- Record the logging config in STATE.md Environment section and in CLAUDE.md/AGENTS.md so future sessions use it automatically

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
