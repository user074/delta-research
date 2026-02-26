# Testing the Research Loop

Modular tests for each stage of the loop. Each test has sample inputs and instructions for what to tell the agent. Run one at a time, inspect the output.

## Test 1: Plan generation

**Input**: `plan_generation/STATE.md` — a state with 3 beliefs, 2 prior runs, 2 frontier candidates.

**Run**: Tell the agent:
> "You are a research supervisor. Read `tests/plan_generation/STATE.md` and `delta-research/templates/SUPERVISOR.md` section 2. Generate a plan for the next run. Write it to `tests/plan_generation/output_PLAN.md`."

**Check**:
- Does the plan have multiple analysis steps (not just "run a script")?
- Does it specify exact resources (checkpoint paths, dataset paths)?
- Does it target the most uncertain belief (#2, confidence 0.5)?
- Does it include rich context with specific numbers from prior runs?
- Does it define what would support vs contradict?

## Test 2: Worker execution

**Input**: `worker_execution/PLAN.md` — a concrete plan with steps that run pure Python (no special deps).

**Run**: Tell the agent:
> "You are a research worker. Read `tests/worker_execution/PLAN.md` and follow the contract in `delta-research/templates/SUPERVISOR.md` section 4. Execute the plan and write your report to `tests/worker_execution/output_REPORT.md`."

**Check**:
- Does the report start with a human-readable Summary + Motivation?
- Is all data inline (numbers in tables, not just "see JSON")?
- Are there visualizations embedded with `![](path)`?
- Is there an Analysis section interpreting the results?
- Does it include Signal, Verdict, New hypotheses, Next tests?

## Test 3: State compression

**Input**: `state_compression/STATE_before.md` + `state_compression/REPORT.md`

**Run**: Tell the agent:
> "You are a research supervisor. Read `delta-research/templates/SUPERVISOR.md` section 5. Given the state in `tests/state_compression/STATE_before.md` and the report in `tests/state_compression/REPORT.md`, produce the updated state. Write it to `tests/state_compression/output_STATE_after.md`."

**Check**:
- Was a new row appended to the Ledger?
- Did belief #2 confidence increase (report supports it)?
- Was the completed delta removed from Frontier?
- Were new beliefs added from the report's "New hypotheses" section?
- Were new deltas added to Frontier for the new beliefs?
- Did Meta update (total_runs, last_updated)?

## Comparing agent policies

After changing `SUPERVISOR.md`, re-run the tests and diff:
```
diff tests/state_compression/output_STATE_after.md tests/state_compression/output_STATE_after_v2.md
```

This lets you see how policy changes affect state transitions without running a full experiment.
