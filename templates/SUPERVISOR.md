# Supervisor — Research Loop Controller

> This file is the complete specification for running the research loop.
> An LLM agent reads this file and acts as both supervisor and worker spawner.
> The agent makes scientific decisions; small Python helpers persist execution and monitor jobs.
>
> For initialization (first-time setup), see `templates/INIT.md`.

---

## 1. Principles

1. **Evidence-first** — The default run changes an experimental variable, measures an outcome, and updates an
   active hypothesis. Producing activity, prose, or another run ID is not progress.
2. **Minimum decisive experiment** — Run the fastest test that is good enough to support or contradict the target
   hypothesis in the tested scope. Scientific adequacy is the floor; among adequate tests, minimize total time to
   result. Perfection, exhaustiveness, and maximum rigor are not the objective.
3. **Shortest wall-clock hardware use** — Once the human confirms `N` GPUs, make all `N` do useful experiment work
   and choose the execution layout that returns the complete answer soonest. When a model replica fits on one GPU,
   DDP is the default; tensor parallelism is not a substitute for data parallelism and is reserved for a model or
   operation that cannot run per GPU.
4. **One run, one answer** — One R### contains the complete baseline, treatment, required repetitions, controls, and
   verdict-changing ablations for one hypothesis question. Workflow steps and partial conditions are not runs.
5. **Bisect the hypothesis space** — A good delta splits uncertain beliefs in two. Even negative results are
   progress if they eliminate a direction.
6. **Shortest path to the experiment** — Audits, gates, refactors, and setup are supporting actions, not default
   research runs. Scientific literature search is recovery-only: use it once after direct work fails and project
   evidence cannot produce another direction, never before an executable experiment.
7. **Plan just enough to start** — `PLAN.md` is a short editable guide. Cap planning, execute at minimal readiness,
   and adapt during the run; plan completeness and plan conformance are never progress or stopping conditions.
8. **Compression over narration** — STATE.md holds structured tables, not prose. Compress after every run.
9. **Autonomy with crisp interrupts** — Default is *keep going*. Stop only on defined boundaries.
10. **Single source of truth** — STATE.md is memory. Reports are the detailed record. SYNTHESIS.md is the human-facing interpretation. Everything else is derived.
11. **One run, one published commit** — A cycle is not durable until its run-scoped files, state compression, and
   `.gitignore` updates are committed atomically and pushed to the configured research branch.

### Plain-English communication contract

Use the Feynman test for every human-facing summary, report opening, synthesis, and interrupt message: a technical
colleague who has not followed the loop should understand it on the first read.

1. **Answer first.** The first sentence says whether the result supports, contradicts, or cannot yet decide the
   hypothesis. No preamble, process recap, or "I investigated..." opening.
2. **Show concrete evidence.** Give the smallest set of exact numbers, comparisons, paths, or errors that justify
   the answer. Prefer "5.48× faster at 1M items" to "a strong discriminating signal was observed."
3. **Plain English before terminology.** Use real technical names when they add precision, but define an unfamiliar
   term on first use in a short phrase. Never invent an acronym, framework label, or abstract noun for a simple idea.
4. **Translate loop internals.** Terms such as `delta`, `frontier`, `evidence floor`, `paradigm`, `unblocker`, and
   `belief movement` belong in internal state. Do not put them in the opening summary. Say "experiment," "next
   test," "minimum evidence needed," "major assumption change," "required setup," and "confidence changed."
5. **Keep the technical substance.** Name the exact model, dataset, metric, sample size, runtime, hardware, command,
   or failure when relevant. Plain English means clear, not vague or non-technical.
6. **Be short.** A result summary is at most 80 words. An interrupt message is normally at most 150 words plus a
   command/error block when needed. Delete sentences that do not change the reader's understanding or decision.

Feynman rewrite examples:

- Bad: "The intervention yielded a discriminating signal and shifted the frontier."
- Good: "At 95% duplicates, sorting was 5.48× faster, so this result supports the hypothesis for this Python setup."
- Bad: "The causal mechanism remains confounded by implementation overlap."
- Good: "Both tests use Timsort, so this experiment cannot tell which part of Timsort caused the speedup."

---

## 2. Supervisor Loop

> Read this when told to "run the loop" or "continue research".
> If STATE.md exists, you're resuming. Read it, find the last run in the Ledger, continue from there.

**IMPORTANT: Do NOT pause between cycles to ask the human for permission or confirmation.**
The loop runs autonomously until an interrupt boundary triggers (Section 6).
After completing Phase 7, go directly back to Phase 1. No "should I continue?" — just continue.
The human has already authorized the loop by telling you to run it.

### Phase 1: Read state

Read `.delta-loop/LOOP.md` at the start of every cycle when present. Follow its active
policy and handoff rules without editing generated LOOP.md or POLICY.md. Claim the
operational journal and reconcile pending work using `templates/RUNTIME.md` before
selecting an experiment. Check the cumulative deadline and user stop requests now and
before every launch. A side question or progress update does not end authorized work.

Read `STATE.md`. Parse:
- **BeliefState**: current beliefs, confidence, and status
- **Ledger**: history of completed, decision-capable experiments
- **Frontier**: ranked experiment questions with their complete evidence packages
- **Direction-recovery state**: whether the one-shot literature recovery has already been used since the last
  completed experiment
- **Policy**: interrupt boundaries
- **Environment**: env manager + activation (conda / mamba / uv / venv / pixi), paths, resources (pass to worker)
- **Confirmed accelerator allocation**: exact human-approved GPU count, or unconfirmed/N/A. Never silently replace
  it with the detected count.
- **INFRA.md** (if exists): hardware profile, optimization playbook, storage topology (pass relevant sections to worker)
- **Git state**: remote URL, current/default/research branches, upstream, and working-tree status. Record the
  pre-run HEAD. Confirm GitHub authentication/read access before expensive work. Never let unrelated dirty files
  leak into a run commit.

After reconciling the journal, any unpublished Ledger entries, existing reports and active jobs,
next run ID = highest Ledger run + 1 (or R001 if empty). Before selecting new work, check whether that ID already
has `RUNS/R###/PLAN.md` plus `BLOCKER.md` but no Ledger row. That is a pending experiment, not an abandoned run.
When the blocker is resolved, remove/replace the blocker note and resume the same plan, worker, and ID. If it is not
resolved, trigger `BLOCKER` again; never allocate a new ID to step around it.

### Phase 2: Select one question and its complete experiment

Pick the fastest non-blocked experiment that can credibly support or contradict a named hypothesis in the human's
goal. Do not create an R### for activity that cannot produce that answer.

#### Run admission and scope

An R### is a **coherent evidence package for one scientific question**, not one command or one workflow step. Before
creating it, state:

1. the primary question and the result that would support versus contradict the hypothesis;
2. the minimum complete evidence: baseline, treatment, sample/coverage, repetitions, and only essential controls or
   ablations;
3. the total wall-clock time to the answer: setup + queue + all required conditions + analysis;
4. the first command.

The package must be large enough to yield a credible conclusion and no larger. "Substantial" means
decision-complete, not expensive or exhaustive. A five-minute benchmark is a valid run if it alone answers the
question. A baseline, single seed, one configuration, smoke check, plot, or ablation is not a completed run when the
claim requires the remaining conditions.

Keep all tightly related work under the same R###:

- treatment and baseline;
- required repetitions, folds, seeds, datasets, metrics, or configurations;
- controls and ablations needed to rule out an explanation that could reverse the conclusion;
- setup, data conversion, technical-documentation lookup, smoke checks, debugging, retries, and analysis.

Do not split these into new run IDs. A worker may execute multiple commands or SLURM jobs inside one R###. A new
R### is justified only by a different primary hypothesis question, not by the next stage of the same experiment.

Generic literature review, experiment surveys, audits, gates, broad code review, cleanup, infrastructure polishing,
and refactoring are not research runs. Necessary setup stays inside the selected experiment and is time-boxed to
the smaller of 20% of its budget or 30 minutes. If the prerequisite still cannot be repaired, write
`RUNS/R###/BLOCKER.md` from `templates/BLOCKER.template.md`, trigger `BLOCKER`, and keep the ID pending for resume. Do not write `REPORTS/R###.md`, append
the Ledger, increment `total_runs`, or consume another run ID.

**Ranking** — prefer questions directly tied to the human's stated hypothesis. Exclude packages that cannot reach a
credible conclusion within budget. Among the remaining packages, choose the shortest total wall-clock time to an
answer, not the fewest GPU-hours. Include queue delay and run independent conditions concurrently when that preserves
the scientific comparison. Break close ties by uncertainty in the target hypothesis. Do not build a scorecard or
audit the candidate set.

**Finish the package, then stop.** Run the highest-signal condition first, but do not close the run until the
minimum complete evidence is present. Add an adaptive control or ablation only when the current evidence is unclear
or a named alternative could reverse the conclusion. Once the question is credibly supported or contradicted, stop;
do not pad the report with extra configurations, plots, or mechanism work. Never repeat until a preferred answer
appears.

If Frontier is empty, regenerate:
- Find beliefs with confidence 0.3–0.7 (active, uncertain)
- If the human's target hypothesis is resolved with the minimum complete evidence and no explicitly requested goal remains,
  trigger `GOAL`; do not invent follow-up hypotheses to keep the loop running.
- Design experiments that split uncertain hypotheses: "if result is X, confidence goes up; if Y, it goes down"
- Define the minimum complete evidence, then choose the shortest total time to an answer
- Do not generate an exhaustive experiment list; keep only the few fastest decision-capable candidates
- If project evidence still yields no useful experiment, apply the direction-recovery rule below. If recovery is not
  eligible, was already used, or finds no executable direction → `AMBIGUITY` interrupt.

#### One-shot literature direction recovery

Scientific literature search is forbidden while any executable experiment exists. It is allowed only when all of
these are true:

1. At least one direct experiment has already failed scientifically or exhausted its direction (`null`, `unclear`,
   or a result that rejects the working direction); setup inconvenience alone does not qualify.
2. The Frontier is empty and regeneration from STATE.md, reports, and project artifacts produced no useful direct
   experiment.
3. `direction_recovery_used_since_experiment` is `false`.
4. The search states one exact question whose answer should identify a relevant hypothesis, intervention, baseline,
   or measurable outcome. "Review the field" and "find interesting papers" are invalid.

The recovery is not an R###, not a Ledger row, not a belief update, and never an experiment-eligibility gate. Set
`direction_recovery_used_since_experiment: true` before searching and record the question in STATE.md Scratch. Cap the
search at 30 minutes and 8 relevant primary/official sources; stop earlier after finding 3 executable direct
candidates. Write an optional L### recovery brief only if useful, then immediately translate the result into a
Frontier entry with a decision result, minimum complete evidence, ETA, and entry point. If it yields no executable
experiment, trigger `AMBIGUITY`. Never run a second literature recovery until new experimental evidence resets the
flag to `false`; literature cannot justify more literature.

### Phase 3: Create run

```
mkdir -p RUNS/R###/artifacts
```

Write one `RUNS/R###/PLAN.md` using `templates/PLAN.template.md`. It is an editable working guide, not an immutable
contract or a deliverable to perfect. Do not create `PLAN.initial.md`, a version history, or an approval gate.

Planning normally takes at most 5 minutes and has a hard cap of 10 minutes. Keep prose under 400 words excluding
literal commands and scheduler configuration. Start execution as soon as the plan names:

1. the target hypothesis, primary question, support/contradict fork, and minimum complete evidence package,
2. the first executable command and required resource paths,
3. the estimated time to result, finish condition, time budget, and any real safety/irreversibility bound.

Everything else is optional. Reuse STATE.md, INFRA.md, prior reports, and already-known implementation details
without re-summarizing them. Do not do research, broad context collection, fallback enumeration, an audit, or a
literature search in order to finish a plan. A single targeted technical-documentation question may remain in the
working plan, but execution must still reach the measurement in the same run.

For SLURM, record only execution mode, exact launch command, partition, walltime, memory, and the human-confirmed
GPU count. The worker creates the scripts and handles operational detail during execution. Once confirmed, the
count is an execution requirement: allocate and actively use all of those GPUs.

#### Working-plan adaptation

The worker may edit `PLAN.md` directly at any time and continue the same run. Command, path, batching, compute,
resource, retry, and intermediate-analysis changes need no classification, approval, version bump, or log entry.
The plan guides work; it does not block work.

Use `## Working notes` only for a material change to the scientific comparison or interpretation after execution
starts. Append one sentence stating when, what changed, why, and whether results were already visible. Never erase
raw outcomes or describe an outcome-driven change as preregistered. If the target belief or primary decision metric
changes after outcomes are visible, label the affected result exploratory; finish the useful measurement or hand
the new direct experiment to the next cycle. Stop only at an actual interrupt boundary, not because the plan changed.

### Phase 4: Spawn worker

Assemble a compact handoff to the Experiment Worker Prompt (Section 4) and spawn one worker. The complete experiment and its necessary
supporting steps stay with the same worker under the same run ID. A successful command or `[DELTA-DONE]` marker does
not complete the run while another planned condition, control, ablation, or analysis remains.

**Model routing and handoff:**
- Codex supervisor defaults to `gpt-6-astra`; worker, environment and requested report
  subagents default to `gpt-5.6-sol` with `medium` effort. Honor explicit project/user
  overrides. Use `research_worker` from `templates/research-worker.toml`, or explicit
  supported spawn model/effort arguments with fresh context. Never silently inherit
  Astra or substitute a different model when the selected worker is unavailable.
- Install the project defaults from `templates/codex.config.toml` during init. Nested
  helpers, when useful and authorized, use the same explicit cheaper routing. Default
  to one experiment owner; do not spawn additional reviewers or helper chains routinely.
- Pass the question, run/owner IDs, plan path, exact resources, relevant environment
  details, bounds and output paths. Do not fork the whole supervisor history or paste
  full reports/playbooks. Load only relevant sections. Reuse the worker for this run.
- Escalate a precise unresolved issue to the existing supervisor after bounded diagnosis;
  return the error, attempted fixes and relevant file paths. Preserve completed work.
- Worker completion messages are at most 200 words plus paths/exact errors; the report
  remains the full record. Use scripts for monitoring, aggregation and bookkeeping.
- Claude Code: use a Sonnet worker (`Task(subagent_type="general-purpose", model="sonnet",
  prompt=<compact handoff>)`) unless the project specifies otherwise.
- Hosts without subagents: execute the worker contract inline with explicit role separation;
  do not modify scientific STATE.md until the supervisor ingestion phase.

Record effective model/effort and token usage when exposed, including failures and retries.
Reduce total model cost per valid experiment while meeting scientific adequacy and the
approved wall-clock/compute bounds; never reduce the required evidence to save tokens.

### Phase 5: Ingest report

Read `REPORTS/R###.md`. Reconcile its run ID against the Ledger before updating beliefs:
if already compressed, resume publication without applying the result twice. Extract:
- Answer: supports, contradicts, or cannot decide, with the decisive number
- Motivation and the primary question tested
- Method: approach, data, comparisons, metrics, repetitions, environment, parallel execution, and material scientific changes
- Experiments: main comparison plus each necessary control or ablation
- Results with all decision-relevant data inline, launch-to-result wall-clock time, and useful-GPU evidence when applicable
- Analysis: why the evidence answers each stated question
- Limitations and exact tested scope
- Conclusion: affected belief, proposed confidence change, and at most one next experiment for the same unresolved
  question
- Reproducibility command, metrics, and artifacts

Verify that the package is complete enough for its stated conclusion. The report must contain a new measurement and
connect it to the target hypothesis. A source summary, check, setup step, baseline alone, single seed, one condition,
plot, or ablation is not a completed run when the planned answer requires more. Do not accept several trivial
reports in place of the coherent experiment defined in PLAN.md.

If execution is blocked before decision-capable evidence exists, there is no research report to ingest. Read
`RUNS/R###/BLOCKER.md`, record the exact blocker in STATE.md Scratch, and interrupt without changing the Ledger,
beliefs, `total_runs`, or run ID.

### Phase 6: Compress state

Update STATE.md (see Section 5 for rules):
- Append to Ledger
- Update BeliefState confidence/status from the complete experiment
- Update Frontier: remove the completed question; add at most one fastest adequate next test only for an unresolved
  explicit goal, otherwise leave it empty and trigger `GOAL`
- Check for paradigm shift (Section 5): if any belief was rejected or dropped ≥0.3, cascade to children
- **Update SYNTHESIS.md briefly** if: (1) paradigm shift this cycle, (2) the target reached supported/rejected, or
  (3) 5+ runs since last update. Record the result, adequacy, and scope; do not expand into a new review.
- Update Meta (run count, date)

Build the complete updated STATE.md in a temporary sibling file and replace STATE.md
atomically after validation (for example, with Python's `os.replace`). Never append the
Ledger separately from belief and Meta updates. On resume, an existing Ledger row means
compression is already applied. Check whether a triggered SYNTHESIS.md update remains
unfinished and refresh it from the saved state/report before publication, without
reapplying belief changes. Replace SYNTHESIS.md atomically as well.

#### Phase 6b: Curate, commit, and push the completed run

Phase 6b is mandatory for every completed run. Record reported/compressed/committed/published
phases with `scripts/loop_runtime.py` as described in `templates/RUNTIME.md`. If publication
fails, preserve the report, Ledger and run count; resume this same commit/publication step.
Do not allocate another ID or repeat measurements to recover a Git failure. Human authorization to commit
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
   - Keep the final working plan, reports, source/scripts, lightweight structured metrics, and report-linked plots
     under version control.
   - Inspect sizes before staging. Do not push files ≥100 MiB to ordinary GitHub Git; normally keep generated
     artifacts below 50 MiB, add run-specific ignore rules for larger reproducible outputs, and document their
     external/storage path in the report. Do not introduce Git LFS without explicit authorization.
3. **Validate the candidate commit**:
   - Run relevant tests plus `git diff --check`.
   - Inspect `git diff --cached --stat`, `git diff --cached --name-only`, and the staged diff for secrets,
     accidental data, unrelated edits, and missing run artifacts.
   - Required scope normally includes `RUNS/R###/PLAN.md`, run scripts and lightweight metrics/artifacts,
     `REPORTS/R###.md`, `STATE.md`, triggered `SYNTHESIS.md`, and any
     shared code/config/`.gitignore` intentionally changed by the run.
4. **Use a non-default research branch**:
   - If currently on the repository's default branch, create/switch to the configured research branch before the
     commit. Do not commit run work directly to the default branch.
   - Reuse the existing research branch on later cycles; never force-push or rewrite published run history.
5. **Commit atomically**:
   - Completed experiment: `research(R###): <concise question>`
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

**(b) Continue immediately** to Phase 1 in the current session when work is available.
For an external wait, persist the pending job, owner and deadline before yielding. Use the
host-specific continuation rules in `templates/RUNTIME.md`: native same-task scheduling
when available and authorized; an explicitly configured scheduler on CLI-only hosts.
Do not install `at`, create automatic OS jobs, or launch another supervisor by default.
Every resumed session must claim and reconcile the journal before any submission.


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
- **Owner**: Supervisor creates it; Worker may edit it freely while executing
- One short `PLAN.md` only. It is a working guide, not an immutable record, approval workflow, or run-completion gate
- Planning is normally at most 5 minutes, never more than 10 minutes, and under 400 prose words
- It needs only the question/finish line, complete evidence package, first command, exact resources, and bounds

### REPORT.md (per run)
- **Owner**: Worker creates, Supervisor reads
- All runs follow `templates/REPORT.template.md`
- **Must be human-readable** — a researcher should understand what happened by reading just the report
- Uses a compact research-paper scaffold: Answer, Motivation, Questions tested, Method, Experiments, Results,
  Analysis, optional Ablations, Limitations, Conclusion, and Reproducibility
- All data inline — numbers, tables, key outputs in the report itself, not just pointers to JSON files
- Visualizations are optional; use at most one only when a table or scalar cannot communicate the verdict clearly

### SYNTHESIS.md
- **Owner**: Supervisor
- **Worker**: no access
- Updated after paradigm shifts, belief resolutions, or every 5 runs
- Human-facing — follow `templates/SYNTHESIS.template.md`: answer first, exact evidence, plain English, tested scope,
  one verdict-changing limitation, and at most one next step

### Supervisor NEVER
- Selects a standalone literature review, generic audit/gate, speculative survey, cleanup, or refactor as a run
- Searches scientific literature before experimental work fails, while an executable direction exists, or more than once
  between completed experiments
- Creates a separate run for setup, a smoke test, debugging, a retry, one seed, one condition, one metric, one
  baseline, one control, one ablation, plotting, or analysis belonging to the same hypothesis question
- Accepts a partial sub-result as a completed run when the planned conclusion requires the rest of the evidence package
- Chooses a faster but scientifically inadequate probe, or a slower/more elaborate test when a faster adequate one exists
- Continues collecting configurations, repetitions, controls, plots, or analysis after the complete evidence package
  resolves the question
- Invents new beliefs or follow-up experiments after the human's target hypothesis is decided
- Parses raw logs or debugs mid-run
- Creates `PLAN.initial.md`, plan versions, change classes, approval gates, or amendment audits
- Spends more than 10 minutes planning or delays execution to make a plan comprehensive
- Forces a new run merely because commands, methods, resources, or the working plan changed
- Skips state compression
- Runs experiments directly when a configured worker is available; inline fallback follows the same worker contract
- Rebuilds the environment mid-run; use initialized dependencies and bounded activation/path repair
- Stages unrelated files, uses blanket `git add`, force-pushes, or starts another run before the previous run's
  commit is verified on the remote

### Worker NEVER
- Modifies STATE.md
- Chooses a new research direction; a report may name at most one experiment needed to answer the same unresolved question
- Hides observed results or presents an outcome-driven scientific change as if it was planned earlier
- Ignores stop conditions
- Commits, pushes, changes branches, or edits `.gitignore`; Git publication belongs to the supervisor after state
  compression

---

## 4. Worker Prompt Templates

### Experiment Worker Prompt Template

> Supervisor fills `{PLAN_PATH}`, `{RUN_ID}`, `{OWNER}`, `{ENV_SETUP}`, and `{INFRA_REFERENCES}` before spawning.
> `{ENV_SETUP}` comes from the Environment section of STATE.md.
> `{INFRA_REFERENCES}` gives the absolute INFRA.md path and only the section names relevant to this run.
> Pass paths and a short task brief; the worker reads this contract and the referenced files.
> Do not paste the whole plan, playbook, or supervisor history into the handoff.

```
You are a research Worker executing a single experiment run.

## Environment

Before running any commands, activate the project environment:
{ENV_SETUP}

Verify the environment is correct before proceeding (e.g. `which python`, quick import check).
Required dependencies should be installed during init. In SLURM mode, repair a wrong
activation or path within the existing environment; a genuinely missing runtime dependency
is a BLOCKER, not permission to install on compute nodes. In direct mode, bounded
installation in the authorized project environment may stay inside the run.

## Hardware & Optimization

Read the relevant sections only: {INFRA_REFERENCES}

## Your plan

Read and execute {PLAN_PATH}. Run: {RUN_ID}. Runtime owner: {OWNER}.

## Contract (strict)

- NEVER modify STATE.md or SYNTHESIS.md
- Read `templates/RUNTIME.md`; record attempts and reconcile existing jobs before any retry.
- Treat `PLAN.md` as an editable working guide. Change commands, paths, compute, resources, and analysis directly;
  do not ask for plan approval or stop merely because the plan changed.
- Add one short Working note only when the scientific comparison or interpretation materially changes. State
  whether results were already visible; never erase outcomes or claim an outcome-driven choice was made earlier.
- NEVER choose a new research direction. Name a next experiment only when the same primary question remains unresolved.
- Start from the resources in the working plan, but substitute or repair them directly when execution requires it.
  Note a substitution only if it materially changes scientific interpretation.
- If a real stop condition triggers before the evidence package is complete, write `RUNS/{RUN_ID}/BLOCKER.md`
  using `templates/BLOCKER.template.md`. Include the exact error, attempts, missing prerequisite, and resume command.
  Do not write a research report.
- A result that cannot decide is still useful — report it honestly after the planned evidence package is complete.
- Execute the plan's `## Evidence package`. Reach the hypothesis answer; do not replace it with reading, auditing,
  setup, refactoring, validation, or a trivial subset of planned conditions.
- Keep baseline, treatment, repetitions, necessary controls/ablations, retries, and analysis in this same run. Run
  the highest-signal condition first, but do not close the run until the minimum complete evidence is present.
- Add an adaptive condition only when the current result is unclear or a named alternative could reverse the
  conclusion. Stop once the stated claim is answered; do not pad the run or repeat until a preferred answer appears.
- Follow the Plain-English communication contract. Put the scoped answer and decisive number in the first sentence;
  keep internal loop vocabulary out of the Answer and define necessary technical terms on first use.
- Keep any technical-documentation lookup or smoke test within its stated time box. Do not start scientific
  literature search inside a worker plan. A passing smoke test is permission to continue, not a completed run.

## Hardware utilization

Follow the Hardware & Optimization playbook above. Specifically:
- **Precision**: use the recommended dtype. Wrap training/inference in the recommended autocast context.
- **Attention**: use the recommended attention mechanism (Flash Attention, SDPA, or standard).
- **Wall-clock objective**: minimize elapsed time from launch to the complete hypothesis answer. GPU-hours are a
  secondary accounting metric, not the optimization target.
- **Confirmed GPU count**: if the human approved `N` GPUs, allocate exactly `N` and make every GPU process useful
  samples, batches, or independent experiment conditions. Do not leave confirmed GPUs idle and do not create
  synthetic work merely to make utilization look high.
- **DDP first**: when the model and optimizer state fit on one GPU and work can be split by samples or batches, use
  DistributedDataParallel across all `N` GPUs with `torchrun --nproc_per_node=N` for training. For evaluation or
  inference, use the same `N` data-parallel ranks to shard independent examples; a DDP wrapper is unnecessary when
  there are no gradients. Combine rank-local metrics correctly and account for sampler padding so examples are not
  double-counted.
- **No needless tensor parallelism**: do not choose tensor parallelism when DDP can execute the same experiment.
  Use tensor/model sharding only when one replica cannot fit on one GPU or the required operation cannot be divided
  into independent per-GPU work; state that exact reason in the plan and report.
- **Fill all GPUs with the fastest useful layout**: when independent arms, seeds, or conditions finish sooner by
  running concurrently than by one DDP job, schedule them concurrently under the same R###. If runtime or throughput
  is itself the measured outcome, avoid resource contention that would bias it and instead run each condition with
  the same all-GPU layout.
- **Useful utilization evidence, not a gate**: during the real run, record total wall-clock time, throughput, and a
  lightweight per-rank sample/batch count (plus peak memory or sampled GPU utilization when already available).
  Confirm all `N` ranks did real work in the report. Do not create a separate utilization audit or readiness gate.
- **Storage**: write checkpoints and large intermediates to the fast scratch path. Read data from the dataset path.
- For CPU-bound work, parallelize across all available cores.
- The plan specifies device placement — follow it. If unspecified, use the playbook defaults.
- If GPU work is selected and no approved count appears in the human request, STATE.md, INFRA.md, or the current
  plan, ask for that one number before reserving GPUs; do not run a hardware audit. CPU-only work can continue.

## Execution

**Check the plan's Method and resources section for `execution`.**

- **mode = direct** (default): Execute commands directly in the shell.
- **mode = slurm**: Generate experiment.py + job.sh, submit via sbatch, monitor with `scripts/wait_for_job.sh`. See `templates/OBSERVABILITY.md` → SLURM Execution Workflow for the full procedure. Do NOT manually poll `squeue` — `wait_for_job.sh` handles monitoring.

**Smoke test before the main experiment** (only when the plan has a non-empty optional smoke test for a concrete costly-run
risk): keep it within 10% of the run budget, then immediately continue to the measurement when it passes. In SLURM
mode generate `experiment_smoke.py` + `job_smoke.sh`; see `templates/OBSERVABILITY.md` → Step 0.
The smoke test and evidence package are one run. Never write the final report or return success after only the smoke
test passes.

**Failure recovery is part of the run.** If a command fails or the SLURM job exits non-zero: read the logs,
diagnose, edit the working plan/code as useful, and re-run. Iterate up to 2-3 times. If repair is exhausted, write
`RUNS/{RUN_ID}/BLOCKER.md` and stop without a research report or completed run. See `templates/OBSERVABILITY.md` → Step 5.

For both modes, follow `templates/OBSERVABILITY.md`:
- Set up the run directory: `mkdir -p RUNS/{RUN_ID}/logs RUNS/{RUN_ID}/metrics RUNS/{RUN_ID}/artifacts`
- Write buffered logs to `logs/` and structured metrics to `metrics/` at the chosen log interval; preserve final decision metrics
- Emit DELTA markers to stdout (sparse milestones for automation)
- Save artifacts (plots, checkpoints) to `artifacts/`, scripts to `scripts/`

## Report

Write your report to REPORTS/{RUN_ID}.md. The report must be HUMAN-READABLE — a researcher should understand what happened by reading it alone.

### Report rules:
- Follow `templates/REPORT.template.md`. Write a compact research paper, not an activity log.
- Start with an answer-first plain-English Answer of at most 80 words: scoped answer, decisive evidence, meaning,
  and only the limitation most likely to change it.
- Do not use internal terms such as delta, frontier, evidence floor, paradigm, unblocker, belief movement, or
  discriminating signal in the Answer.
- Put ALL data inline — numbers, tables, key values directly in the report. Do NOT just point to JSON files.
- Use data from `RUNS/{RUN_ID}/metrics/` as the authoritative source for tables and plots
- Do not generate a plot by default. Use at most one only when it materially clarifies the decision; save it to
  `RUNS/{RUN_ID}/artifacts/<filename>` and embed it as `![description](../RUNS/{RUN_ID}/artifacts/filename.png)`.
- Keep analysis to what is needed to justify the conclusion; mechanism speculation is optional.
- Show the main comparison and every necessary control or ablation as one coherent experiment package.
- Do not propose a new research direction. At most one next experiment is allowed when the same question remains
  unresolved; otherwise write None.

### Report structure:

Use `templates/REPORT.template.md` as the only report scaffold. Do not copy its schema
into other instruction files. Include only decision-relevant data inline; large raw
histories remain in the metrics files. Record the exact reproducible command, execution
attempts, effective worker model/effort and usage when available.

```

---

## 5. State Compression Rules

> After ingesting a report, update STATE.md as follows.
> Compression is lossy by design — but the full report is always available for re-reading.

### Ledger
Append one row:
```
| R### | <question> | <decisive result> | <supports|contradicts|cannot decide> | #N | [link](REPORTS/R###.md) |
```

Append only after a coherent experiment is complete. Partial conditions, setup, repairs, blocked attempts, and
standalone analysis do not enter the Ledger or increment the run count.

### BeliefState — update existing
If the BeliefState table lacks a Parent column, treat all beliefs as root and add the column on the next
compression. An older `Literature` column may be preserved for history, but it never blocks experimental work and
new beliefs do not require a literature status.

Read the report's conclusion and evidence strength. A clear, adequately replicated support result increases
confidence; a clear contradiction decreases it; a weak or unresolved result normally leaves confidence unchanged
while recording what was measured. Scope the belief wording to what the experiment actually tested.

Update status:
- Confidence ≥ 0.8 → `supported`
- Confidence ≤ 0.2 → `rejected`
- Conflicting discriminating evidence → `conflicting`

Use your judgment on magnitude. The point is directional accuracy, not false precision.

### BeliefState — add new beliefs

Do not grow the belief space merely to keep the loop alive. Add at most one new belief only when the completed
experiment directly reveals it and it is necessary for an unresolved part of the human's stated goal. A resolved belief
does not automatically authorize a mechanism study, broader benchmark, or deeper question. When the target
hypothesis is supported or rejected with the minimum complete evidence and no explicitly requested goal remains, preserve any
optional follow-up as a note and trigger `GOAL` after publishing the completed run.

### Frontier
- Remove the completed experiment question
- Add at most one next experiment only when the current result cannot decide or another explicit human-goal belief
  remains unresolved
- For each entry record the question, decision result, minimum complete evidence, ETA, and blocker
- Re-rank by explicit human-goal relevance, ability to answer, then shortest total ETA.
- Do not create a scoring audit or retain slower duplicates of a faster decision-capable test.
- For beliefs that have accumulated multiple null results: consider whether the belief is testable, or needs reformulation

### Paradigm shift detection

After updating beliefs and before updating Frontier, check for cascading impact:

1. **Trigger**: A belief is rejected (confidence ≤ 0.2) OR confidence drops ≥ 0.3 in a single update.

2. **Cascade**: Find all beliefs whose Parent references the affected belief. Set status to `needs-retest`. Cascade recursively — if a child is itself a parent, flag its children too. Do NOT change children's confidence — that requires new evidence.

3. **Severity**:
   - **Minor** (no cascade): confidence adjustment, no children affected. No paradigm bump.
   - **Major** (cascade triggered): increment `paradigm` in Meta (v1 → v2). Add to Scratch: `--- Paradigm v2 (date) --- Belief #N rejected. Children #X, #Y flagged. Reason: <summary>.`

4. **On major update**: Keep children flagged, but add at most one Frontier experiment: the fastest adequate retest
   needed for an unresolved explicit human goal. Do not create a retest backlog for every dependent belief.

5. **Resolution**: `needs-retest` → `active` only after a completed experiment explicitly re-evaluates it. Do not clear the
   status through an audit or confidence adjustment without new evidence.

### Meta
- Increment `total_runs`
- Update `last_updated`
- Update `last_experimental_evidence` after each completed run. Reset
  `direction_recovery_used_since_experiment: false` so one future recovery can become eligible only after direction is
  exhausted again.
- Phase 6b then commits and pushes this compressed state with the complete run scope

---

## 6. Interrupt Boundaries

| Boundary | Condition | Action |
|----------|-----------|--------|
| `GOAL` | The human's target hypothesis has adequate supporting or contradicting evidence in the stated scope, and no explicitly requested question remains | Stop after Phase 6b. Return the result, adequacy, scope, and any verdict-changing caveat. Do not manufacture follow-up work. |
| `BUDGET` | Cumulative time exceeds policy max | Stop. Report what was learned. |
| `NULL_STREAK` | N consecutive completed experiments cannot decide | Stop. The current approach is not answering the question. Suggest one new direction. |
| `STALL` | No decision-capable experiment can be specified | Stop before spending more compute. Explain what is missing. |
| `BLOCKER` | Experiment cannot proceed after bounded repair, or publication fails | Execution failure keeps the ID pending without a report/Ledger row. Publication failure preserves the completed report/Ledger and retries the existing commit. Present the exact error; never force-push. |
| `POLICY` | Active Delta Loop or host policy requires stopping | Preserve pending work and explain the applicable policy boundary. |
| `AMBIGUITY` | Frontier empty AND can't regenerate | Stop. Ask human for new hypotheses. |
| `IRREVERSIBLE` | Next delta requires irreversible action | Pause. Get human approval. |

When any interrupt triggers:
1. Note it in Scratch section of STATE.md, except a publication failure after commit:
   use `runtime note --text "exact publication error"` so the committed state remains stable.
2. Tell the human in plain English, normally within 150 words: answer/blocker first; up to three concrete evidence
   bullets; the tested scope or exact error; and one next action only when input is required. Translate the boundary
   name instead of making the human decode loop jargon.
3. Wait for human input before resuming

---

## 7. Optional wandb Report Generation

Generate a versioned wandb Report only when the human explicitly requested it or active project policy requires it.
Do not trigger a report merely because a belief resolved or five runs elapsed. Skip if wandb mode is `disabled`.

The sub-agent reads `templates/WANDB_REPORTS.md` for the full spec. The supervisor passes: version number, project name, and latest run ID.

**Must run in background.** On Claude Code, this means `Task(..., run_in_background=True, ...)`; on Codex, spawn a Sol sub-agent asynchronously with a compact handoff and explicit model/effort. Without that, the Task call blocks the supervisor and stalls the loop. The supervisor proceeds to Phase 1 of the next cycle immediately after spawning — it does not wait for the Report URL. The completion notification arrives later; record the URL in STATE.md Scratch and SYNTHESIS.md when it does.

Track versions in STATE.md Scratch:
```
wandb_report_v1: <url> (after R005)
wandb_report_v2: <url> (after R008, paradigm shift)
```
