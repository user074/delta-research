# Supervisor — Research Loop Controller

> This file is the complete specification for running the research loop.
> An LLM agent reads this file and acts as both supervisor and worker spawner.
> There are no scripts. The agent IS the orchestrator.
>
> For initialization (first-time setup), see `templates/INIT.md`.

---

## 1. Principles

1. **Delta-first** — The unit of progress is *what changed → what happened → what it means*.
2. **Bisect the hypothesis space** — A good delta splits uncertain beliefs in two. Even negative results are progress if they eliminate a direction.
3. **Compression over narration** — STATE.md holds structured tables, not prose. Compress after every run.
4. **Autonomy with crisp interrupts** — Default is *keep going*. Stop only on defined boundaries.
5. **Single source of truth** — STATE.md is memory. Reports are the detailed record. Everything else is derived.

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
- **BeliefState**: current beliefs, confidence, status
- **Ledger**: history of completed runs
- **Frontier**: ranked candidate deltas
- **Policy**: interrupt boundaries
- **Environment**: conda, paths, resources (pass to worker)

Next run ID = highest Ledger run + 1 (or R001 if empty).

### Phase 2: Select delta

Pick the top-ranked non-blocked Frontier entry.

**Bandit reasoning** — use the Ledger to learn what works:
1. Which beliefs are most uncertain? (confidence nearest 0.5 = highest value to test)
2. For each candidate delta: would the result clearly push a belief toward supported or rejected? Or would it likely produce an ambiguous result?
3. Check history: have similar deltas produced discriminating results? Have we tried this direction and gotten only null?
4. Pick the delta with the highest expected discrimination for the most uncertain belief.

If Frontier is empty, regenerate:
- Find beliefs with confidence 0.3–0.7 (active, uncertain)
- If all beliefs are resolved (supported/rejected), derive new ones: what follow-up questions do the resolved beliefs raise? Add them to BeliefState at 0.5.
- Design deltas that would bisect uncertain beliefs: "if result is X, belief goes up; if Y, belief goes down"
- Rank by expected discrimination
- If no useful deltas possible AND no new beliefs can be derived → `AMBIGUITY` interrupt

### Phase 3: Create run

```
mkdir -p RUNS/R###/artifacts
```

Write `RUNS/R###/PLAN.md` using `templates/PLAN.template.md` as structure.

**A good plan is substantive.** Each run is expensive — maximize information extracted per run. A plan should:
- Have **multiple analysis steps** that build on each other (not just "run a script")
- Spell out the **exact analysis logic** the worker should follow — what to compute, how to interpret it, what to look for
- Include **fallback strategies** if the primary data source or approach doesn't work
- Provide **rich context** from prior runs — specific findings, numbers, anomalies to investigate, not just "see R004"
- Target **multiple related beliefs** when a single analysis can inform several
- Define **clear success criteria** — what result would support vs contradict, with thresholds
- Specify **exact resources** — checkpoint paths, dataset locations, which artifacts from prior runs to use. No ambiguity.

Fill in:
- Delta: what to change, why, what belief(s) it targets
- Commands: detailed step-by-step analysis (multiple steps, not a single command)
- Resources: exact paths to checkpoints, data, prior artifacts (from STATE.md Environment + prior runs)
- Success metrics: what to measure, with baselines and targets
- Stop conditions: when to halt
- Context: relevant beliefs, prior findings with specific numbers, data file paths

The plan is **immutable** once handed to the worker. If it needs to change, the worker reports BLOCKER.

### Phase 4: Spawn worker

Assemble the worker prompt (see Section 4) with the plan content and spawn a worker.

**Agent-specific spawning:**
- **Claude Code**: `Task(subagent_type="general-purpose", prompt=<worker prompt>)`
- **Codex**: Spawn a sub-agent with the worker prompt. Codex handles orchestration natively — it spawns the thread, waits for results, and surfaces the output. The sub-agent runs in the same sandbox with the same file access. Instruct it to read the PLAN, execute, and write the REPORT.
- **Other agents**: Execute the worker prompt directly. Follow the same contract — execute the plan, write the report, don't touch STATE.md.

**Codex multi-agent setup** (during init, add to project config or `codex.toml`):
```toml
[features]
multi_agent = true

[agents.worker]
description = "Research worker: executes a single experiment plan, writes a structured report. Never modifies STATE.md or PLAN.md."
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

### Phase 6: Compress state

Update STATE.md (see Section 5 for rules):
- Append to Ledger
- Update BeliefState confidence and status based on the evidence
- Add new beliefs from report
- Update Frontier: remove completed delta, consider adding suggested next deltas
- Update Meta (run count, date)

### Phase 7: Check interrupts

Evaluate all interrupt boundaries (Section 6). If any trigger → stop and report to human.

If clear → return to Phase 1.

---

## 3. Contracts

### STATE.md
- **Owner**: Supervisor
- **Worker**: read-only
- **Environment section**: managed by environment agent, read by workers
- Updated after every run

### PLAN.md (per run)
- **Owner**: Supervisor creates, Worker reads
- **Immutable** during execution
- Must specify exact resource paths (checkpoints, datasets, artifacts) — worker uses what's listed
- If the plan can't be followed or a resource is missing, Worker reports BLOCKER

### REPORT.md (per run)
- **Owner**: Worker creates, Supervisor reads
- Must follow `templates/REPORT.template.md` structure
- **Must be human-readable** — a researcher should understand what happened by reading just the report
- All data inline — numbers, tables, key outputs in the report itself, not just pointers to JSON files
- Visualizations embedded with `![description](path)` — generate plots for any numerical results

### Supervisor NEVER
- Parses raw logs or debugs mid-run
- Modifies a plan after handing it to a worker
- Skips state compression
- Runs experiments directly (always spawn a worker)
- Manages environment directly (spawn environment agent)

### Worker NEVER
- Modifies STATE.md
- Modifies PLAN.md
- Chooses new research directions (suggests only via "New hypotheses" and "Next tests" in report)
- Uses resources not specified in the plan (wrong checkpoint, different dataset)
- Ignores stop conditions

---

## 4. Worker Prompt Template

> Supervisor fills `{PLAN_CONTENT}`, `{RUN_ID}`, and `{ENV_SETUP}` before spawning.
> `{ENV_SETUP}` comes from the Environment section of STATE.md.

```
You are a research Worker executing a single experiment run.

## Environment

Before running any commands, activate the project environment:
{ENV_SETUP}

Verify the environment is correct before proceeding (e.g. `which python`, quick import check).
If a package is missing, install it within the env (`pip install <pkg>`).

## Your plan

{PLAN_CONTENT}

## Contract (strict)

- NEVER modify STATE.md
- NEVER modify PLAN.md
- NEVER choose new research directions (suggest via "New hypotheses" and "Next tests" only)
- ONLY use resources specified in the plan (checkpoints, datasets, artifacts). If a resource is missing or wrong, BLOCKER.
- If any stop condition triggers, immediately report verdict = BLOCKER
- Null results are valuable — report honestly

## Execution

1. Read the plan carefully
2. Execute the commands in order
3. Record all outputs and measurements
4. Save artifacts to RUNS/{RUN_ID}/artifacts/

## Report

Write your report to REPORTS/{RUN_ID}.md. The report must be HUMAN-READABLE — a researcher should understand what happened by reading it alone.

### Report rules:
- Start with a plain-language summary (what you did, what you found, what it means)
- Put ALL data inline — numbers, tables, key values directly in the report. Do NOT just point to JSON files.
- Generate visualizations for any numerical results. Save plots to `RUNS/{RUN_ID}/artifacts/` and embed in the report with `![description](RUNS/{RUN_ID}/artifacts/filename.png)`
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
(Generate plots. Embed them.)
![description](RUNS/{RUN_ID}/artifacts/plot_name.png)

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

### BeliefState — add new beliefs

**This is critical for keeping the loop alive.** After updating existing beliefs, ask:

1. **Did the worker report new hypotheses?** Check the "New hypotheses" section of the report. Add any well-reasoned ones as new beliefs at confidence 0.5.
2. **Did a resolved belief open new questions?** When a belief reaches supported/rejected, the answer often raises deeper questions. Example: belief "A outperforms B" reaches 0.85 → add new belief "A outperforms B because of factor X" at 0.5.
3. **Did something unexpected show up?** Anomalies, confounds, or surprising observations in the report may suggest hypotheses nobody considered at init time.

The belief space should grow as you learn, not just shrink. If all beliefs are resolved and no new ones are emerging, the research question may be answered — or the agent is not looking deep enough.

### Frontier
- Remove the completed delta
- **Add deltas targeting new beliefs** — every new belief should have at least one candidate delta
- Review the report's "Next tests" — add any that would discriminate on uncertain beliefs
- Re-rank: prioritize deltas targeting the most uncertain beliefs (nearest 0.5)
- For beliefs that have accumulated multiple null results: consider whether the belief is testable, or needs reformulation

### Meta
- Increment `total_runs`
- Update `last_updated`

---

## 6. Interrupt Boundaries

| Boundary | Condition | Action |
|----------|-----------|--------|
| `BUDGET` | Cumulative time exceeds policy max | Stop. Report what was learned. |
| `NULL_STREAK` | N consecutive null-signal runs | Stop. The current approach isn't producing discrimination. Suggest new direction. |
| `BLOCKER` | Worker returns BLOCKER | Stop. Present details. |
| `AMBIGUITY` | Frontier empty AND can't regenerate | Stop. Ask human for new hypotheses. |
| `IRREVERSIBLE` | Next delta requires irreversible action | Pause. Get human approval. |

When any interrupt triggers:
1. Note it in Scratch section of STATE.md
2. Tell the human: what happened, what was learned, what's next
3. Wait for human input before resuming
