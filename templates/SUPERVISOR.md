# Supervisor — Research Loop Controller

> This file is the complete specification for running the research loop.
> An LLM agent reads this file and acts as both supervisor and worker spawner.
> There are no scripts. The agent IS the orchestrator.
>
> For initialization (first-time setup), see `templates/INIT.md`.

---

## 1. Principles

1. **Delta-first** — The unit of progress is *what changed → what happened → what it means*.
2. **Ground before testing** — Every hypothesis receives its own literature-review run before an empirical run may target it. Prior work should sharpen, redirect, or retire weak ideas before compute is spent.
3. **Bisect the hypothesis space** — A good delta splits uncertain beliefs in two. Even negative results are progress if they eliminate a direction.
4. **Compression over narration** — STATE.md holds structured tables, not prose. Compress after every run.
5. **Autonomy with crisp interrupts** — Default is *keep going*. Stop only on defined boundaries.
6. **Single source of truth** — STATE.md is memory. Reports are the detailed record. SYNTHESIS.md is the human-facing interpretation. Everything else is derived.
7. **One run, one published commit** — A cycle is not durable until its run-scoped files, state compression, and
   `.gitignore` updates are committed atomically and pushed to the configured research branch.

---

## 2. Supervisor Loop

> Read this when told to "run the loop" or "continue research".
> If STATE.md exists, you're resuming. Read it, find the last run in the Ledger, continue from there.

**IMPORTANT: Do NOT pause between cycles to ask the human for permission or confirmation.**
The loop runs autonomously until an interrupt boundary triggers (Section 6).
After completing Phase 7, go directly back to Phase 1. No "should I continue?" — just continue.
The human has already authorized the loop by telling you to run it.

### Phase 1: Read state

Read `STATE.md`. Parse:
- **BeliefState**: current beliefs, confidence, status, and literature-grounding status
- **Ledger**: history of completed runs
- **Frontier**: ranked candidate deltas
- **Policy**: interrupt boundaries
- **Environment**: env manager + activation (conda / mamba / uv / venv / pixi), paths, resources (pass to worker)
- **INFRA.md** (if exists): hardware profile, optimization playbook, storage topology (pass relevant sections to worker)
- **Git state**: remote URL, current/default/research branches, upstream, and working-tree status. Record the
  pre-run HEAD. Confirm GitHub authentication/read access before expensive work. Never let unrelated dirty files
  leak into a run commit.

Next run ID = highest Ledger run + 1 (or R001 if empty).

### Phase 2: Select delta

Pick the top-ranked non-blocked Frontier entry.

#### Mandatory Literature Grounding Gate

Every belief must have a `Literature` value in BeliefState:

- `pending` — no dedicated review has grounded the exact hypothesis wording
- `grounded (R###, YYYY-MM-DD)` — a completed literature-review run covers this exact hypothesis
- `refresh-needed` — the hypothesis changed materially or the review is no longer current enough for the decision

If the column is absent in an older STATE.md, add it at the next compression and treat every belief without a
linked review artifact as `pending`. Project experiments, intuition, or a few citations in Scratch do not satisfy
the gate.

**Eligibility rule:** an empirical, analysis, exploration, or engineering delta may target a belief only when its
Literature value is `grounded (...)`. If it is `pending` or `refresh-needed`, the only eligible next delta for that
belief is a `literature-review` run. The supervisor must create or promote that review entry ahead of empirical
entries targeting the same belief.

Each literature-review run grounds exactly one hypothesis. Closely related beliefs may share sources, but each
still gets its own review round and report so its evidence, novelty, and direction are independently auditable.
When the wording or causal mechanism of a belief changes materially, mark it `refresh-needed`; cosmetic wording
changes do not reopen the gate.

A literature-review run must answer:

1. What primary evidence directly supports or contradicts this hypothesis?
2. What adjacent evidence changes its plausibility without testing it directly?
3. What is the closest prior work, and is the proposed contribution still novel?
4. Which methods, datasets, metrics, checkpoints, prompts, or official code should be reused?
5. What known failure modes, negative results, or alternative explanations should change the experiment?
6. Should the hypothesis be kept, narrowed, reframed, deprioritized, or dropped?

Literature runs require current internet/database search unless an explicit offline constraint creates a BLOCKER.
Prioritize primary sources (papers and official project/code pages); use reviews or surveys to discover primary
work, not as the sole support for technical claims. Include the strongest contrary evidence and distinguish
direct evidence from adjacent analogy and speculation. Record search date, query families, inclusion criteria,
coverage limits, stable links/DOIs/arXiv IDs, and official code/data links. Do not pad a sparse literature with
irrelevant citations.

**Bandit reasoning** — for each candidate delta, assess three dimensions:

1. **Uncertainty** (of the target belief): Confidence nearest 0.5 = `high`. 0.3-0.4 or 0.6-0.7 = `med`. Near supported/rejected = `low`.
2. **Info gain** (expected discrimination): Would the result clearly push the belief? Check history for similar deltas. High discrimination potential = `high`.
3. **Feasibility**: Quick and straightforward = `high`. Expensive or has failed approaches = `low`.

Record all three in the Frontier table. Use judgment to rank — dimensions make reasoning auditable but don't combine into a formula. Prioritize high-uncertainty + high-info-gain, downrank low-feasibility.

If Frontier is empty, regenerate:
- Find beliefs with confidence 0.3–0.7 (active, uncertain)
- If all beliefs are resolved (supported/rejected), derive new ones: what follow-up questions do the resolved beliefs raise? Add them to BeliefState at 0.5.
- For every new or ungrounded belief, add its one-belief literature-review delta before any empirical delta
- Design deltas that would bisect uncertain beliefs: "if result is X, belief goes up; if Y, belief goes down"
- Rank by expected discrimination
- If no useful deltas possible AND no new beliefs can be derived → `AMBIGUITY` interrupt

### Phase 3: Create run

```
mkdir -p RUNS/R###/artifacts
```

Write `RUNS/R###/PLAN.md` using `templates/PLAN.template.md` as structure. Before handing it to the worker, copy
the exact initial bytes to `RUNS/R###/PLAN.initial.md`. `PLAN.initial.md` is the immutable preregistration snapshot;
`PLAN.md` is the live execution plan and may receive controlled amendments under the policy below.

Every plan must include `## Literature Grounding`:

- For a `literature-review` run, name the one target belief, its exact wording, search questions, query families,
  required counterevidence, implementation/code scan, and coverage standard. Use
  `templates/LITERATURE.template.md` for the report. Literature runs do not need GPU allocation, smoke tests, or
  plots unless the review includes a genuine quantitative meta-analysis. Declare the immutable archive path
  `LITERATURE/B###/R###/` in Resources.
- For every other run type, cite the exact grounding report `REPORTS/R###.md`, summarize how it changed the
  design, and verify the target belief's Literature value is grounded. Missing grounding is a plan-time BLOCKER.

**A good plan is substantive.** Each run is expensive — maximize information extracted per run. A plan should:
- Have **multiple analysis steps** that build on each other (not just "run a script")
- Spell out the **exact analysis logic** the worker should follow — what to compute, how to interpret it, what to look for
- Include **fallback strategies** if the primary data source or approach doesn't work
- Provide **rich context** from prior runs — specific findings, numbers, anomalies to investigate, not just "see R004"
- Target **multiple related beliefs** when a single analysis can inform several
- Define **clear success criteria** — what result would support vs contradict, with thresholds
- Specify **exact resources** — checkpoint paths, dataset locations, which artifacts from prior runs to use. No ambiguity.
- **Maximize hardware utilization** — read INFRA.md (if it exists) for the hardware profile and optimization playbook. Use it to design commands that fully utilize available hardware:
  - **Parallelism**: use the strategy from INFRA.md Playbook → Parallelism (DDP, FSDP, etc.) and include the exact launch command in plan steps
  - **Precision**: use the recommended dtype from INFRA.md Playbook → Precision (BF16, FP16, FP32) — specify explicitly in plan commands
  - **Attention**: if Flash Attention or SDPA is available (check INFRA.md Playbook → Attention), specify it in the plan
  - **Storage**: use paths from INFRA.md Storage → Guidance (fast scratch for checkpoints, large storage for data reads)
  - **CPU-bound work**: parallelize across all cores (see INFRA.md Compute → CPU for core count)
  - Specify device placement and parallelism explicitly in plan commands — don't leave it to the worker to figure out
  - If INFRA.md doesn't exist, fall back to STATE.md Environment for basic GPU/CPU info

**SLURM execution** — if INFRA.md `Job Execution → mode` is `slurm`:
- Include a `## SLURM` section in the plan with walltime estimate, GPU count, memory, and partition
- The worker will generate a standalone `experiment.py` + `job.sh`, submit via `sbatch`, and monitor via `scripts/wait_for_job.sh`
- Plan commands must be self-contained — everything the compute node needs should be in experiment.py (no interactive shell commands)
- Specify `execution mode: slurm` in Resources so the worker knows which path to follow
- **GPU count** — request the minimum needed, not the maximum available. More GPUs = longer queue wait.
  - **Model fits on 1 GPU** (inference, small fine-tune, analysis): request 1 GPU
  - **Training benefits from data parallelism** (large dataset, long training): request GPUs per INFRA.md Parallelism guidance
  - **Model doesn't fit on 1 GPU** (FSDP/ZeRO needed): request the minimum GPUs for the model to fit
  - When in doubt, start with fewer GPUs — queue time matters more than marginal speedup

Fill in:
- Delta: what to change, why, what belief(s) it targets
- Literature Grounding: this run's review protocol, or the prior grounding report and design implications
- Commands: detailed step-by-step analysis (multiple steps, not a single command)
- Resources: exact paths to checkpoints, data, prior artifacts (from STATE.md Environment + prior runs). Include `execution mode: direct | slurm` (from INFRA.md Job Execution)
- Success metrics: what to measure, with baselines and targets
- Stop conditions: when to halt
- Context: relevant beliefs, prior findings with specific numbers, data file paths

#### Controlled plan amendments

Plans are commitments, not brittle scripts. Preserve the initial scientific intent in `PLAN.initial.md`, while
allowing the live `PLAN.md` to be repaired in the same run. A trivial bug must not force a new run.

Classify a proposed change before making it:

1. **Class A — worker-autonomous repair**: typographical errors; broken commands; stale but identity-equivalent
   paths; import/API/version mismatches; serialization or schema bugs; logging/plot/report formatting; retry,
   timeout, batching, worker-count, or memory adjustments; deterministic seed plumbing; and corrections to metric
   implementation that retain the preregistered estimand and recompute every affected arm. The worker fixes these
   directly, updates `PLAN.md`, increments `plan_version`, and appends an Amendment Log row. Continue the same run.
2. **Class B — supervisor-approved, scope-preserving amendment**: an equivalent resource substitution, material
   schedule/compute reallocation within the recorded budget, or a method change that preserves the target belief,
   causal contrast, dataset/model family, primary endpoint, and success criterion. The worker emits
   `AMENDMENT_NEEDED` with the proposed diff and evidence; the supervisor may amend the live plan and resume the
   same worker/run. This is not automatically a BLOCKER and does not require human approval unless another
   interrupt boundary applies.
3. **Class C — scientific redesign**: changing the target belief, main causal estimand/intervention, primary
   model or dataset family, primary endpoint or its success threshold after seeing outcomes, preregistered
   prediction after outcome inspection, or budget/irreversibility boundary. Do not amend this into the current
   run. Preserve the evidence gathered, write a BLOCKER or completed pilot report as appropriate, and create a
   newly planned run. Obtain human input only when an interrupt boundary actually requires it.

Every change to the live plan must be auditable: preserve `PLAN.initial.md`; append rather than rewrite the
`## Amendment Log`; record timestamp, actor, class, issue/evidence, exact before → after change, and why the
scientific interpretation is unchanged; and summarize amendments in the report. Never lower a target, swap the
primary outcome, delete an arm, or revise a prediction because observed results are inconvenient. If a metric bug
is repaired after partial execution, retain the raw outputs and recompute all comparable cells.

### Phase 4: Spawn worker

Read the plan's Delta type. For `literature-review`, assemble the Literature Review Worker Prompt (Section 4B).
For all other types, assemble the Experiment Worker Prompt (Section 4A). Spawn one worker.

**Agent-specific spawning:**
- **Claude Code**: `Task(subagent_type="general-purpose", model="sonnet",prompt=<worker prompt>)`
- **Codex**: Spawn a sub-agent with the worker prompt. Codex handles orchestration natively — it spawns the thread, waits for results, and surfaces the output. The sub-agent runs in the same sandbox with the same file access. Instruct it to read the PLAN, execute, and write the REPORT.
- **Other agents**: Execute the worker prompt directly. Follow the same contract — execute the plan, write the report, don't touch STATE.md.

**Codex multi-agent setup** (during init, add to project config or `codex.toml`):
```toml
[features]
multi_agent = true

[agents.worker]
description = "Research worker: executes one plan, fixes logged Class A execution bugs in live PLAN.md, writes a structured report, and never modifies STATE.md or PLAN.initial.md."
```

### Phase 5: Ingest report

Read `REPORTS/R###.md`. Extract:
- Summary (what was done, what was found)
- Results with inline data
- Signal: discriminating / partial / null
- Verdict: supports / contradicts / unclear / BLOCKER
- Which belief was affected
- Confounds
- New hypotheses
- Suggested next deltas
- Plan amendments: version, repair class, why they were scope-preserving, and whether any result was observed
  before each amendment
- If this was a literature review: search coverage, evidence map, closest prior work, reusable assets, grounding
  verdict, recommended direction, and whether the empirical gate is open
- Verify the durable archive exists at `LITERATURE/B###/R###/`, contains `REVIEW.md`, `queries.md`, `evidence.csv`,
  and `sources.bib` (or a complete linked-source fallback), and that `REVIEW.md` is byte-identical to
  `REPORTS/R###.md`

### Phase 6: Compress state

Update STATE.md (see Section 5 for rules):
- Append to Ledger
- Update BeliefState confidence and status based on the evidence
- Add new beliefs from report
- If this was a literature review, set the exact target belief to `grounded (R###, date)` after verifying the
  report satisfies the literature contract; otherwise leave it pending and treat the report as BLOCKER/unclear
- Update `LITERATURE/INDEX.md` for the target belief with the exact hypothesis, latest review, date, evidence
  verdict, recommended direction, archive path, and run-report path. Initialize it from
  `templates/LITERATURE_INDEX.template.md` if absent. Never overwrite prior review directories.
- Update Frontier: remove completed delta, consider adding suggested next deltas
- Check for paradigm shift (Section 5): if any belief was rejected or dropped ≥0.3, cascade to children
- **Update SYNTHESIS.md** if: (1) paradigm shift this cycle, (2) a belief reached supported/rejected, or (3) 5+ runs since last update. If SYNTHESIS.md doesn't exist, create from template. Write for a human who hasn't followed the loop.
- Update Meta (run count, date)

#### Phase 6b: Curate, commit, and push the completed run

Phase 6b is mandatory for every completed experimental or literature-review run. Human authorization to commit
and push must be recorded in project instructions or obtained explicitly; initialization should ask for it. If
authorization is absent, stop at `IRREVERSIBLE` before the first commit/push. Never infer permission to publish.

1. **Inspect scope before staging**:
   - Run `git status --short`, inspect unstaged diffs, and compare with the pre-run HEAD.
   - Identify the exact files produced or intentionally changed by this run. Preserve unrelated human/agent work.
   - Never use `git add .`, `git add -A`, or `git add --all`. Stage explicit confirmed paths with
     `git add -- <path...>`.
2. **Manage `.gitignore`**:
   - Ignore secrets, environment directories, caches, wandb internals, raw logs, checkpoints, generated model
     weights, and large transient outputs.
   - Keep both the immutable initial plan and the final live plan, reports, source/scripts, lightweight structured
     metrics, and report-linked plots under version control.
   - Inspect sizes before staging. Do not push files ≥100 MiB to ordinary GitHub Git; normally keep generated
     artifacts below 50 MiB, add run-specific ignore rules for larger reproducible outputs, and document their
     external/storage path in the report. Do not introduce Git LFS without explicit authorization.
3. **Validate the candidate commit**:
   - Run relevant tests plus `git diff --check`.
   - Inspect `git diff --cached --stat`, `git diff --cached --name-only`, and the staged diff for secrets,
     accidental data, unrelated edits, and missing run artifacts.
   - Required scope normally includes `RUNS/R###/PLAN.initial.md`, `RUNS/R###/PLAN.md`, run scripts and lightweight metrics/artifacts,
     `REPORTS/R###.md`, literature archive + index for review runs, `STATE.md`, triggered `SYNTHESIS.md`, and any
     shared code/config/`.gitignore` intentionally changed by the run.
4. **Use a non-default research branch**:
   - If currently on the repository's default branch, create/switch to the configured research branch before the
     commit. Do not commit run work directly to the default branch.
   - Reuse the existing research branch on later cycles; never force-push or rewrite published run history.
5. **Commit atomically**:
   - Experimental/analysis run: `research(R###): <concise delta>`
   - Literature run: `literature(R###): ground belief #N`
   - One completed run should map to one primary commit containing plan → execution evidence → report → state
     compression. Do not create empty commits.
6. **Push and verify**:
   - Push the exact current branch to the configured remote, setting upstream on first push:
     `git push -u <remote> HEAD` (later `git push`).
   - Verify local HEAD equals the remote-tracking branch after push and record the commit hash in the user-facing
     interrupt/final summary when the loop eventually stops.
   - Retry a transient push failure up to 2–3 times after diagnosis. Authentication failure, non-fast-forward
     requiring a merge/rebase decision, branch protection, missing remote, or repeated network failure is a
     `BLOCKER`; do not force-push.

**The cycle is not complete until Phase 6b succeeds.** Do not start the next plan, emit a between-cycle summary,
or schedule continuation while the completed run exists only locally.

### Phase 7: Check interrupts, schedule continuation

**(a) Confirm Phase 6b succeeded, then evaluate interrupt boundaries** (Section 6). If any trigger → stop and
report to human. A local-only completed run is a BLOCKER, not a successful cycle boundary.

**(b) Schedule the next cycle.** Even when no interrupt fires, the loop should self-schedule a wakeup before yielding. This keeps progress trackable, lets the human interject between cycles, and survives session pauses. The default cadence is short — pick a delay that matches what's pending (e.g. ~60s when no external job is in flight; longer when a slow SLURM job or remote API is the bottleneck).

Agent-specific:

- **Claude Code, inside a `/loop` dynamic session** (the supervisor was started via `/loop run the research loop` with no interval): call the `ScheduleWakeup` tool at the end of every cycle. Pass the same `/loop` prompt verbatim so the next firing re-enters the supervisor at Phase 1. Choose `delaySeconds` based on what you're waiting on (60–270s if a job is about to settle; 1200–1800s if genuinely idle). Set `reason` to one short specific sentence (e.g. `"checking R042 SLURM job, ~5min remaining"`) — this is shown to the human as the tracking signal.
- **Claude Code, NOT inside `/loop`**: continue to Phase 1 in the same turn. Do not invent a scheduling call.
- **Codex**: use the OS scheduler via `at`. Codex has no `/loop` equivalent, so this is the parallel mechanism — `at` runs a fresh `codex exec` at the scheduled time, achieving the same "wake up later and resume" behavior.

  ```bash
  # Schedule next cycle in 30 minutes (adjust delay as needed)
  echo "cd $(pwd) && codex exec --full-auto 'continue research loop — read STATE.md and proceed from Phase 1'" \
      | at now + 30 minutes
  ```

  Requires `at` (Linux) or `atrun` enabled (macOS: `sudo launchctl load -w /System/Library/LaunchDaemons/com.apple.atrun.plist`). If `at` is unavailable, fall back to continuing in the same session and note the limitation in STATE.md Scratch.

**(c) Then return to Phase 1** (or yield, if you scheduled a deferred wakeup in step b).

---

## 3. Contracts

### STATE.md
- **Owner**: Supervisor
- **Worker**: read-only
- **Environment section**: managed by environment agent, read by workers
- Updated after every run

### INFRA.md
- **Owner**: Environment agent (created during init, updated on hardware changes)
- **Supervisor**: read-only (extracts playbook for worker prompts and plan creation)
- **Worker**: read-only (follows playbook for precision, parallelism, storage)
- Re-run environment agent to update after hardware changes (new GPUs, moved to cluster, etc.)

### PLAN.md (per run)
- **Owner**: Supervisor creates the initial/live pair; Worker may edit only the live plan under Class A
- `PLAN.initial.md` is the immutable preregistration snapshot; `PLAN.md` is the versioned, amendable execution plan
- Must specify exact resource identities and paths; identity-equivalent path repairs are Class A, resource
  substitutions are Class B or C depending on scientific impact
- A plan problem triggers repair or `AMENDMENT_NEEDED` before BLOCKER; only Class C redesign or an interrupt
  boundary requires ending the run

### REPORT.md (per run)
- **Owner**: Worker creates, Supervisor reads
- Experimental runs follow `templates/REPORT.template.md`; literature-review runs follow
  `templates/LITERATURE.template.md`
- **Must be human-readable** — a researcher should understand what happened by reading just the report
- All data inline — numbers, tables, key outputs in the report itself, not just pointers to JSON files
- Visualizations embedded with `![description](path)` — generate plots for numerical experimental results;
  literature reviews may use a structured evidence table without a plot

### LITERATURE archive
- **Worker**: writes versioned review files under `LITERATURE/B###/R###/`
- **Supervisor**: validates the archive and updates `LITERATURE/INDEX.md` during compression
- `REVIEW.md` must be byte-identical to `REPORTS/R###.md`; Git stores identical content as one blob
- `queries.md`, `evidence.csv`, and `sources.bib` preserve reproducible search and machine-readable grounding
- Reviews are immutable. Refreshes create a new run subdirectory and update the index; never overwrite history.

### SYNTHESIS.md
- **Owner**: Supervisor
- **Worker**: no access
- Updated after paradigm shifts, belief resolutions, or every 5 runs
- Human-facing — readable without STATE.md context

### Supervisor NEVER
- Parses raw logs or debugs mid-run
- Silently rewrites `PLAN.initial.md`, the Amendment Log, predictions, primary endpoints, or success thresholds
- Forces a new run for a Class A repair that the worker can resolve locally
- Skips state compression
- Runs experiments directly (always spawn a worker)
- Manages environment directly (spawn environment agent)
- Stages unrelated files, uses blanket `git add`, force-pushes, or starts another run before the previous run's
  commit is verified on the remote

### Worker NEVER
- Modifies STATE.md
- Modifies `PLAN.initial.md`, or changes `PLAN.md` outside the controlled amendment policy
- Chooses new research directions (suggests only via "New hypotheses" and "Next tests" in report)
- Silently substitutes a scientifically different checkpoint, dataset, intervention, or endpoint
- Ignores stop conditions
- Commits, pushes, changes branches, or edits `.gitignore`; Git publication belongs to the supervisor after state
  compression

---

## 4. Worker Prompt Templates

### 4A. Experiment Worker Prompt Template

> Supervisor fills `{PLAN_CONTENT}`, `{RUN_ID}`, `{ENV_SETUP}`, and `{INFRA_PLAYBOOK}` before spawning.
> `{ENV_SETUP}` comes from the Environment section of STATE.md.
> `{INFRA_PLAYBOOK}` comes from INFRA.md (Optimization Playbook + Storage Guidance + GPU table). If INFRA.md doesn't exist, omit the Hardware & Optimization section entirely.

```
You are a research Worker executing a single experiment run.

## Environment

Before running any commands, activate the project environment:
{ENV_SETUP}

Verify the environment is correct before proceeding (e.g. `which python`, quick import check).
If a package is missing, install it using the project's env manager (`pip install <pkg>` inside an active conda/venv; `uv pip install <pkg>` or `uv add <pkg>` for uv projects; `pixi add <pkg>` for pixi). In SLURM mode, install on the login node into the target env — compute nodes mount the same filesystem and load the same env (verify `which python` resolves to the same absolute path on both).

## Hardware & Optimization

{INFRA_PLAYBOOK}

## Your plan

{PLAN_CONTENT}

## Contract (strict)

- NEVER modify STATE.md
- NEVER modify `PLAN.initial.md`. You MAY repair the live `PLAN.md` under the Controlled plan amendments policy:
  fix Class A issues locally, increment `plan_version`, append the Amendment Log, and continue the same run.
  For Class B, emit `AMENDMENT_NEEDED` with an exact proposed diff for supervisor approval. Class C is BLOCKER.
- NEVER choose new research directions (suggest via "New hypotheses" and "Next tests" only)
- Use the resource identities specified in the live plan. Repair an identity-equivalent path locally; do not
  silently substitute a different model, dataset, or intervention.
- If any stop condition triggers, immediately report verdict = BLOCKER
- Null results are valuable — report honestly
- Verify the plan's `## Literature Grounding` cites a completed review for every target belief. Missing or pending
  grounding is a BLOCKER; do not begin the experiment.

## Hardware utilization

Follow the Hardware & Optimization playbook above. Specifically:
- **Precision**: use the recommended dtype. Wrap training/inference in the recommended autocast context.
- **Attention**: use the recommended attention mechanism (Flash Attention, SDPA, or standard).
- **Parallelism**: use the recommended strategy and launch command. If the plan specifies DDP, use `torchrun` as shown.
- **Storage**: write checkpoints and large intermediates to the fast scratch path. Read data from the dataset path.
- For CPU-bound work, parallelize across all available cores.
- The plan specifies device placement — follow it. If unspecified, use the playbook defaults.
- If no Hardware & Optimization section is provided, use all available GPUs and default to FP32.

## Execution

**Check the plan's Resources section for `execution mode`.**

- **mode = direct** (default): Execute commands directly in the shell.
- **mode = slurm**: Generate experiment.py + job.sh, submit via sbatch, monitor with `scripts/wait_for_job.sh`. See `templates/OBSERVABILITY.md` → SLURM Execution Workflow for the full procedure. Do NOT manually poll `squeue` — `wait_for_job.sh` handles monitoring.

**Smoke test before hero run** (when the plan has a `## Smoke Test` section): generate `experiment_smoke.py` + `job_smoke.sh` from the smoke config, submit to the fast-queue partition, validate VRAM and throughput, refine the hero walltime if needed. Only submit the hero run after the smoke passes. See OBSERVABILITY.md → Step 0.

**Failure recovery is part of the run.** If a command fails or the SLURM job exits non-zero: read the logs,
diagnose, repair Class A issues in the live plan/code, and re-run. Iterate up to 2-3 times. Emit
`AMENDMENT_NEEDED` for a Class B change. Escalate to BLOCKER only for Class C redesign, an exhausted repair, or a
defined interrupt boundary. See `templates/OBSERVABILITY.md` → Step 5 for SLURM-specific recovery patterns.

For both modes, follow `templates/OBSERVABILITY.md`:
- Set up the run directory: `mkdir -p RUNS/{RUN_ID}/logs RUNS/{RUN_ID}/metrics RUNS/{RUN_ID}/artifacts`
- Write full logs to `logs/` and structured metrics to `metrics/` (every step)
- Emit DELTA markers to stdout (sparse milestones for automation)
- Save artifacts (plots, checkpoints) to `artifacts/`, scripts to `scripts/`

## Report

Write your report to REPORTS/{RUN_ID}.md. The report must be HUMAN-READABLE — a researcher should understand what happened by reading it alone.

### Report rules:
- Start with a plain-language summary (what you did, what you found, what it means)
- Put ALL data inline — numbers, tables, key values directly in the report. Do NOT just point to JSON files.
- Use data from `RUNS/{RUN_ID}/metrics/` as the authoritative source for tables and plots
- Generate visualizations. **All plots MUST be saved to `RUNS/{RUN_ID}/artifacts/<filename>`, never under `REPORTS/`.** When the plan lists bare filenames (e.g. `r101_loss.png`), prepend `RUNS/{RUN_ID}/artifacts/` — the plan's `output dir` is the authoritative destination, the bare filename is just a label. Embed with `![description](../RUNS/{RUN_ID}/artifacts/filename.png)` (the `../` is required because the report lives in `REPORTS/` and `RUNS/` is its sibling).
- Include your analysis — why do the results look this way? What's the interpretation?
- The structured sections (Signal, Verdict, etc.) come AFTER the human-readable content

### Report structure:

# REPORT — {RUN_ID}

## Summary
(2-3 sentences: what was tested, what was found, what it means for the research question)

## Motivation
(Why this experiment? What belief is being tested? What would support vs contradict?)

## Method
(What was done, step by step — enough that a human could reproduce)

## Results

### Data
(Inline tables with actual numbers. ALL key metrics here, not in separate files.)

| Metric | Value | Notes |
|--------|-------|-------|
(every important measurement)

### Visualizations
(Generate plots. Embed them. Path is relative to REPORTS/{RUN_ID}.md, so use `../RUNS/...`.)
![description](../RUNS/{RUN_ID}/artifacts/plot_name.png)

### Analysis
(Interpret the results. Why do they look this way? What patterns do you see? What's surprising?)

## Signal
- **discrimination**: (discriminating | partial | null)
- (why — what did we learn or fail to learn?)
- (key observation that might matter for future runs)

## Verdict
**<supports | contradicts | unclear | BLOCKER>** — belief #N: <how this evidence affects the belief>

## Confounds
- (what else could explain the result?)

## New hypotheses
<!-- Did this run reveal something that suggests a NEW belief to track? -->
- (new hypothesis, if any, with reasoning)

## Next tests
1. (delta that would further discriminate, and why)
2. (alternative approach if this direction is exhausted)
3. (wild card — something unexpected this run suggested)

## Artifacts
- `artifacts/<file>` — <what it contains>

## Meta
- **run_id**: {RUN_ID}
- **delta**: (what was tested)
- **started**: (timestamp)
- **completed**: (timestamp)
- **status**: completed | failed | blocked
- **execution**: (direct | slurm)
- **slurm_job_id**: (job ID, if slurm)
- **wandb_run**: (wandb run URL, if applicable)
```

### 4B. Literature Review Worker Prompt Template

> Use this prompt only when `PLAN.md` has `type: literature-review`. The review is a real run: it gets an R### ID,
> preserved initial plan, amendable live plan, report, Ledger row, and state compression, but it does not execute
> the proposed experiment.

```
You are a research Worker executing one literature-grounding run: {RUN_ID}.

## Environment

The project root and research state are available in the current workspace. Read the preserved initial plan and
the current live plan; use only the target belief and search scope authorized there. Internet/database search is required unless the plan records
an offline constraint; if current search is impossible, write a BLOCKER report rather than relying on memory.

## Your plan

{PLAN_CONTENT}

## Contract (strict)

- NEVER modify STATE.md, SYNTHESIS.md, or `PLAN.initial.md`. Class A repairs to live `PLAN.md` are allowed and
  must be versioned in its Amendment Log; Class B requires `AMENDMENT_NEEDED`; Class C is BLOCKER.
- Review exactly one target hypothesis. Do not silently broaden or replace it.
- Do not run the proposed empirical experiment. Small deterministic checks that only verify a paper, repository,
  dataset, or metric are allowed when the plan authorizes them.
- Search multiple query families: exact hypothesis/phenomenon, proposed mechanism, and methodological or failure-
  mode terms. Follow citation trails in both directions for the key sources.
- Prioritize primary sources and official code/data. A survey can organize the field, but trace decisive claims to
  original papers. Read enough methods/results to assess what was actually tested; abstracts alone are not enough
  for key evidence.
- Seek and report the strongest contrary or null evidence. Distinguish direct tests, adjacent evidence, conceptual
  analogy, and speculation.
- Record search date, databases/search engines, exact query strings, inclusion/exclusion criteria, and coverage
  limits. Usually include at least five relevant primary sources when the field contains them; document sparse
  literature rather than padding the count.
- Give stable direct citations (DOI, arXiv, publisher/conference page, or official repository URL) for every key
  claim. Never cite a search-results page.
- Identify reusable official code, data, measures, prompts, checkpoints, baselines, and evaluation protocols.
- End with an actionable direction: keep, narrow, reframe, deprioritize, or drop the hypothesis, and explain how
  the first empirical plan should change.
- New hypotheses may be suggested only in the report. Each will enter STATE.md as literature=pending and require
  its own future review round.

## Output

Write the full review using `templates/LITERATURE.template.md` exactly to both:

- `REPORTS/{RUN_ID}.md`
- `LITERATURE/B{BELIEF_ID_PADDED}/{RUN_ID}/REVIEW.md`

The two files must be byte-identical. Also write:

- `LITERATURE/B{BELIEF_ID_PADDED}/{RUN_ID}/queries.md` — exact query log, database/search engine, date, result
  screening, and inclusion/exclusion notes
- `LITERATURE/B{BELIEF_ID_PADDED}/{RUN_ID}/evidence.csv` — one row per included source with citation, stable URL,
  source type, relationship, tested claim, finding, limitations, and code/data URL
- `LITERATURE/B{BELIEF_ID_PADDED}/{RUN_ID}/sources.bib` — BibTeX where available; if BibTeX is unavailable, store
  a complete linked citation list in this file and state the fallback format at the top

Put the evidence map and source list inline in the review as well, so it remains independently auditable. Save
optional plots or auxiliary extraction artifacts under `RUNS/{RUN_ID}/artifacts/` and list them in the review.
```

---

## 5. State Compression Rules

> After ingesting a report, update STATE.md as follows.
> Compression is lossy by design — but the full report is always available for re-reading.

### Ledger
Append one row:
```
| R### | <delta> | <signal> | <verdict> | #N | [link](REPORTS/R###.md) |
```

### BeliefState — update existing
If the BeliefState table lacks a Parent column, treat all beliefs as root. If it lacks a Literature column, treat
beliefs without a dedicated linked review as pending. Add both columns on the next compression.

Read the report's verdict and evidence. Judge:
- **supports + discriminating**: meaningful increase in confidence
- **supports + partial**: small increase
- **contradicts + discriminating**: meaningful decrease in confidence
- **contradicts + partial**: small decrease
- **unclear or null**: no confidence change, but note what happened in evidence column

Update status:
- Confidence ≥ 0.8 → `supported`
- Confidence ≤ 0.2 → `rejected`
- Conflicting discriminating evidence → `conflicting`

Use your judgment on magnitude. The point is directional accuracy, not false precision.

For a completed literature-review run:

- Verify it followed `templates/LITERATURE.template.md` and contains a reproducible search protocol, primary-
  evidence map, contrary evidence, novelty/gap analysis, implementation guidance, and direction recommendation.
- If adequate, set Literature to `grounded (R###, YYYY-MM-DD)` for that exact belief. If inadequate or search was
  blocked, keep `pending`/`refresh-needed` and add a corrective literature-review delta.
- Literature is evidence and may update confidence, but label it `[literature R###]` in Key evidence so it is not
  confused with project-generated evidence. Calibrate the update to directness, methodological quality,
  independence, and match to the exact claim.
- Verify the versioned literature archive is complete and `REVIEW.md` is byte-identical to the run report; update
  `LITERATURE/INDEX.md`. Missing or divergent archive files keep the literature gate closed.
- Apply the review's direction recommendation to the Frontier. A `drop` recommendation does not automatically
  reject a belief; use the evidence and standard confidence rules. A material reframe creates a new pending belief.

### BeliefState — add new beliefs

**This is critical for keeping the loop alive.** After updating existing beliefs, ask:

1. **Did the worker report new hypotheses?** Check the "New hypotheses" section of the report. Add any well-reasoned ones as new beliefs at confidence 0.5 and Literature `pending`.
2. **Did a resolved belief open new questions?** When a belief reaches supported/rejected, the answer often raises deeper questions. Example: belief "A outperforms B" reaches 0.85 → add new belief "A outperforms B because of factor X" at 0.5 and Literature `pending`.
3. **Did something unexpected show up?** Anomalies, confounds, or surprising observations in the report may suggest hypotheses nobody considered at init time.

The belief space should grow as you learn, not just shrink. If all beliefs are resolved and no new ones are emerging, the research question may be answered — or the agent is not looking deep enough.

### Frontier
- Remove the completed delta
- **Add literature-review deltas for new beliefs first** — every new belief gets one dedicated review round, ranked
  ahead of empirical deltas targeting it
- Add empirical deltas targeting new beliefs only as blocked entries until their Literature status is grounded
- Review the report's "Next tests" — add any that would discriminate on uncertain beliefs
- Re-rank: assess Uncertainty, Info gain, Feasibility for each delta. Prioritize high-uncertainty targets with high info-gain.
- Never select an empirical entry whose target belief is `pending` or `refresh-needed`, even if its rank is highest
- If Frontier lacks scoring dimension columns, add them on next compression.
- For beliefs that have accumulated multiple null results: consider whether the belief is testable, or needs reformulation

### Paradigm shift detection

After updating beliefs and before updating Frontier, check for cascading impact:

1. **Trigger**: A belief is rejected (confidence ≤ 0.2) OR confidence drops ≥ 0.3 in a single update.

2. **Cascade**: Find all beliefs whose Parent references the affected belief. Set status to `needs-review`. Cascade recursively — if a child is itself a parent, flag its children too. Do NOT change children's confidence — that requires re-evaluation.

3. **Severity**:
   - **Minor** (no cascade): confidence adjustment, no children affected. No paradigm bump.
   - **Major** (cascade triggered): increment `paradigm` in Meta (v1 → v2). Add to Scratch: `--- Paradigm v2 (date) --- Belief #N rejected. Children #X, #Y flagged. Reason: <summary>.`

4. **On major update**: For each `needs-review` child, add a frontier entry to re-evaluate it. The delta should test whether the child still holds given the parent's new status.

5. **Resolution**: `needs-review` → `active` (with updated confidence) once a run explicitly re-evaluates it. If no new evidence, supervisor may adjust confidence down 0.1-0.2 noting "indirect adjustment" in evidence.

### Meta
- Increment `total_runs`
- Update `last_updated`
- Phase 6b then commits and pushes this compressed state with the complete run scope

---

## 6. Interrupt Boundaries

| Boundary | Condition | Action |
|----------|-----------|--------|
| `BUDGET` | Cumulative time exceeds policy max | Stop. Report what was learned. |
| `NULL_STREAK` | N consecutive null-signal runs | Stop. The current approach isn't producing discrimination. Suggest new direction. |
| `BLOCKER` | Worker returns BLOCKER, or Phase 6b cannot safely commit/push after recovery attempts | Stop. Present details; for Git failures include branch, local commit if any, remote, and exact error. Never force-push. |
| `AMBIGUITY` | Frontier empty AND can't regenerate | Stop. Ask human for new hypotheses. |
| `IRREVERSIBLE` | Next delta requires irreversible action | Pause. Get human approval. |

When any interrupt triggers:
1. Note it in Scratch section of STATE.md
2. Tell the human: what happened, what was learned, what's next
3. Wait for human input before resuming

---

## 7. wandb Report Generation

On significant events (paradigm shift, belief resolved, every 5 runs), spawn a sub-agent to create a versioned wandb Report snapshot. Skip if wandb mode is `disabled`.

The sub-agent reads `templates/WANDB_REPORTS.md` for the full spec. The supervisor passes: version number, project name, and latest run ID.

**Must run in background.** On Claude Code, this means `Task(..., run_in_background=True, ...)`; on Codex, spawn the sub-agent detached. Without that, the Task call blocks the supervisor and stalls the loop. The supervisor proceeds to Phase 1 of the next cycle immediately after spawning — it does not wait for the Report URL. The completion notification arrives later; record the URL in STATE.md Scratch and SYNTHESIS.md when it does.

Track versions in STATE.md Scratch:
```
wandb_report_v1: <url> (after R005)
wandb_report_v2: <url> (after R008, paradigm shift)
```
