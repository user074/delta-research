# Supervisor — Research Loop Controller

> This file is the complete specification for running the research loop.
> An LLM agent reads this file and acts as both supervisor and worker spawner.
> There are no scripts. The agent IS the orchestrator.

---

## 1. Principles

1. **Delta-first** — The unit of progress is *what changed → what happened → what it means*.
2. **Bisect the hypothesis space** — A good delta splits uncertain beliefs in two. Even negative results are progress if they eliminate a direction.
3. **Compression over narration** — STATE.md holds structured tables, not prose. Compress after every run.
4. **Autonomy with crisp interrupts** — Default is *keep going*. Stop only on defined boundaries.
5. **Single source of truth** — STATE.md is memory. Reports are the detailed record. Everything else is derived.

---

## 2. Initialization

> Run this when STATE.md does not exist.

1. **Understand the project.** Read the codebase, README, docs. Understand what exists.

2. **Talk to the human.** Ask:
   - What's the research question?
   - Any existing hypotheses?
   - What does success look like?
   - Budget constraints?
   - Known risks or irreversible actions?

3. **Verify environment.** Check that the execution environment is ready:
   - Detect active conda/venv: run `conda info --envs` or `which python` to find the current environment
   - If the project uses conda, confirm the correct env is active. If not, ask the human which env to use.
   - Record the environment in STATE.md Scratch section (e.g. `conda activate myenv`)
   - Test that key dependencies are importable (a quick `python -c "import ..."` for known project deps)
   - If a dependency is missing, install it within the env (`pip install` inside conda is safe)

4. **Create directories.**
   ```
   mkdir -p REPORTS RUNS ARTIFACTS
   ```

5. **Create STATE.md.** Use `templates/STATE.template.md` as structure. Fill in:
   - Project name, goal, date from the conversation
   - Seed beliefs from the human's hypotheses (confidence 0.5 for unvalidated)
   - Initial frontier: deltas that would discriminate between competing hypotheses
   - Policy: budget, interrupt thresholds
   - Scratch: record the conda/venv environment name and activation command

6. **Inject into agent config file(s).** Detect which agent is running and write to the appropriate file(s). Create if needed, append if exists.

   | Agent | Instruction file | Multi-agent config |
   |-------|-----------------|-------------------|
   | Claude Code | `CLAUDE.md` | N/A (Task tool built-in) |
   | OpenAI Codex | `AGENTS.md` | `codex.toml` or project config |
   | Cursor | `.cursorrules` | N/A |

   If unsure, write to both `CLAUDE.md` and `AGENTS.md`. Content to append:
   ```markdown
   # Research Loop
   This project uses a structured research loop.
   See `delta-research/templates/SUPERVISOR.md` for the full spec.
   State lives in `STATE.md`. To continue: "run the research loop".
   ```

   For Codex, also enable multi-agent in config:
   ```toml
   [features]
   multi_agent = true

   [agents.worker]
   description = "Research worker: executes a single experiment plan, writes a structured report. Never modifies STATE.md or PLAN.md."
   ```

7. **Confirm with human.** Show STATE.md. Are the seed beliefs and frontier right?

---

## 3. Supervisor Loop

> Read this when told to "run the loop" or "continue research".
> If STATE.md exists, you're resuming. Read it, find the last run in the Ledger, continue from there.

**IMPORTANT: Do NOT pause between cycles to ask the human for permission or confirmation.**
The loop runs autonomously until an interrupt boundary triggers (Section 7).
After completing Phase 7, go directly back to Phase 1. No "should I continue?" — just continue.
The human has already authorized the loop by telling you to run it.

### Phase 1: Read state

Read `STATE.md`. Parse:
- **BeliefState**: current beliefs, confidence, status
- **Ledger**: history of completed runs
- **Frontier**: ranked candidate deltas
- **Policy**: interrupt boundaries

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

Fill in:
- Delta: what to change, why, what belief(s) it targets
- Commands: detailed step-by-step analysis (multiple steps, not a single command)
- Success metrics: what to measure, with baselines and targets
- Stop conditions: when to halt
- Context: relevant beliefs, prior findings with specific numbers, data file paths

The plan is **immutable** once handed to the worker. If it needs to change, the worker reports BLOCKER.

### Phase 4: Spawn worker

Assemble the worker prompt (see Section 5) with the plan content and spawn a worker.

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
- Results (what was measured)
- Signal: discriminating / partial / null
- Verdict: supports / contradicts / unclear / BLOCKER
- Which belief was affected
- Confounds
- Suggested next deltas

### Phase 6: Compress state

Update STATE.md (see Section 6 for rules):
- Append to Ledger
- Update BeliefState confidence and status based on the evidence
- Update Frontier: remove completed delta, consider adding suggested next deltas
- Update Meta (run count, date)

### Phase 7: Check interrupts

Evaluate all interrupt boundaries (Section 7). If any trigger → stop and report to human.

If clear → return to Phase 1.

---

## 4. Contracts

### STATE.md
- **Owner**: Supervisor
- **Worker**: read-only
- Updated after every run

### PLAN.md (per run)
- **Owner**: Supervisor creates, Worker reads
- **Immutable** during execution
- If the plan can't be followed, Worker reports BLOCKER

### REPORT.md (per run)
- **Owner**: Worker creates, Supervisor reads
- Must follow `templates/REPORT.template.md` structure
- Should be detailed — there may be signals in the details that compression misses

### Supervisor NEVER
- Parses raw logs or debugs mid-run
- Modifies a plan after handing it to a worker
- Skips state compression
- Runs experiments directly (always spawn a worker)

### Worker NEVER
- Modifies STATE.md
- Modifies PLAN.md
- Chooses new research directions (suggests only via "Next tests" in report)
- Ignores stop conditions

---

## 5. Worker Prompt Template

> Supervisor fills `{PLAN_CONTENT}`, `{RUN_ID}`, and `{ENV_SETUP}` before spawning.
> `{ENV_SETUP}` comes from the Scratch section of STATE.md (e.g. `conda activate myenv`).

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
- NEVER choose new research directions (suggest via "Next tests" only)
- If any stop condition triggers, immediately report verdict = BLOCKER
- Null results are valuable — report honestly
- Be detailed in your report — include observations that might not seem important

## Execution

1. Read the plan carefully
2. Execute the commands in order
3. Record all outputs and measurements
4. Save artifacts to RUNS/{RUN_ID}/artifacts/

## Report

Write your report to REPORTS/{RUN_ID}.md following this structure:

# REPORT — {RUN_ID}

## Result
| Metric | Baseline | Observed | Δ | Notes |
|--------|----------|----------|---|-------|
(fill from measurements)

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
<!-- A resolved belief often opens new questions. "A outperforms B" → "why? is it factor X?" -->
- (new hypothesis, if any, with reasoning)

## Next tests
1. (delta that would further discriminate, and why)
2. (alternative approach if this direction is exhausted)
3. (wild card — something unexpected this run suggested)

## Artifacts
- `artifacts/<file>` — <what it contains>

## Errors
(any errors, or "None")

## Log
```
(key outputs, abbreviated but preserving important details)
```

## Meta
- **run_id**: {RUN_ID}
- **delta**: (what was tested)
- **started**: (timestamp)
- **completed**: (timestamp)
- **status**: completed | failed | blocked
```

---

## 6. State Compression Rules

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

## 7. Interrupt Boundaries

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
