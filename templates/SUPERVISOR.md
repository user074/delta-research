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

3. **Create directories.**
   ```
   mkdir -p REPORTS RUNS ARTIFACTS
   ```

4. **Create STATE.md.** Use `templates/STATE.template.md` as structure. Fill in:
   - Project name, goal, date from the conversation
   - Seed beliefs from the human's hypotheses (confidence 0.5 for unvalidated)
   - Initial frontier: deltas that would discriminate between competing hypotheses
   - Policy: budget, interrupt thresholds

5. **Inject into project's CLAUDE.md** (create if needed). Append a pointer:
   ```markdown
   # Research Loop
   This project uses a structured research loop.
   See `delta-research/templates/SUPERVISOR.md` for the full spec.
   State lives in `STATE.md`. To continue: "run the research loop".
   ```

6. **Confirm with human.** Show STATE.md. Are the seed beliefs and frontier right?

---

## 3. Supervisor Loop

> Read this when told to "run the loop" or "continue research".
> If STATE.md exists, you're resuming. Read it, find the last run in the Ledger, continue from there.

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
- Find beliefs with confidence 0.3–0.7
- Design deltas that would bisect: "if result is X, belief goes up; if Y, belief goes down"
- Rank by expected discrimination
- If no useful deltas possible → `AMBIGUITY` interrupt

### Phase 3: Create run

```
mkdir -p RUNS/R###/artifacts
```

Write `RUNS/R###/PLAN.md` using `templates/PLAN.template.md` as structure. Fill in:
- Delta: what to change, why, what belief it targets
- Commands: exact steps the worker executes
- Success metrics: what to measure
- Stop conditions: when to halt
- Context: relevant beliefs and prior run results from STATE.md

The plan is **immutable** once handed to the worker. If it needs to change, the worker reports BLOCKER.

### Phase 4: Spawn worker

Assemble the worker prompt (see Section 5) with the plan content and spawn:
```
Task(subagent_type="general-purpose", prompt=<assembled worker prompt>)
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

> Supervisor fills `{PLAN_CONTENT}` and `{RUN_ID}` before spawning.

```
You are a research Worker executing a single experiment run.

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

### BeliefState
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

### Frontier
- Remove the completed delta
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
