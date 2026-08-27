# Testing the Research Loop

Modular tests for each stage of the loop. Each test has sample inputs and instructions for what to tell the agent. Run one at a time, inspect the output.

## Test 1: Plan generation

**Input**: `plan_generation/STATE.md` — a state with 3 beliefs, 2 prior runs, and a tempting legacy no-progress
frontier item ahead of two direct experiments.

**Run**: Tell the agent:
> "You are a research supervisor. Read `tests/plan_generation/STATE.md` and `delta-research/templates/SUPERVISOR.md` section 2. Generate a plan for the next run. Write it to `tests/plan_generation/output_PLAN.md`."

**Check**:
- Does the plan use the shortest reproducible path to a measurement without padded audits/checks?
- Does it specify exact resources (checkpoint paths, dataset paths)?
- Does it target the most uncertain belief (#2, confidence 0.5)?
- Does the plan name one hypothesis question and its support/contradict fork?
- Does it choose the 8-minute belief-#3 package over the 25-minute belief-#2 package after both can answer?
- Does one R### include the baseline, treatment, repetitions, and necessary controls/ablations?
- Does it state the minimum evidence, total ETA, and finish immediately when the fork resolves?
- Does it avoid substituting literature review, audits, gates, or setup for the experiment?
- Is it a concise editable guide with one first command and no amendment/approval machinery?
- Does it define what would support vs contradict?

## Test 2: Worker execution

**Input**: `worker_execution/PLAN.md` — a short working guide for a pure-Python experiment.

**Run**: Tell the agent:
> "You are a research worker. Read `tests/worker_execution/PLAN.md` and follow the contract in `delta-research/templates/SUPERVISOR.md` section 4. Execute the plan and write your report to `tests/worker_execution/output_REPORT.md`."

**Check**:
- Does the report start with a human-readable Summary + Motivation?
- Does the paper-like report include Answer, Motivation, Questions, Method, Experiments, Results, Analysis,
  optional Ablations, Limitations, Conclusion, and Reproducibility?
- Does the opening give the answer and decisive number in plain English without loop-internal jargon?
- Is all data inline (numbers in tables, not just "see JSON")?
- Does it use at most one visualization, and only if the verdict needs it?
- Is there an Analysis section interpreting the results?
- Does it include Signal and Verdict while limiting new hypotheses to two and next tests to one?

## Test 3: State compression

**Input**: `state_compression/STATE_before.md` + `state_compression/REPORT.md`

**Run**: Tell the agent:
> "You are a research supervisor. Read `delta-research/templates/SUPERVISOR.md` section 5. Given the state in `tests/state_compression/STATE_before.md` and the report in `tests/state_compression/REPORT.md`, produce the updated state. Write it to `tests/state_compression/output_STATE_after.md`."

**Check**:
- Was a new row appended to the Ledger?
- Did belief #2 confidence increase (report supports it)?
- Was the completed delta removed from Frontier?
- Did compression avoid manufacturing new beliefs or a follow-up backlog after the question was decided?
- Did every new belief receive a concrete direct experiment with an expected observation?
- Does the Frontier contain only coherent experiment questions, not setup or partial conditions?
- Did Meta update (total_runs, last_updated)?

## Comparing agent policies

After changing `SUPERVISOR.md`, re-run the tests and diff:
```
diff tests/state_compression/output_STATE_after.md tests/state_compression/output_STATE_after_v2.md
```

This lets you see how policy changes affect state transitions without running a full experiment.

## Framework contract test

Run:

```bash
python tests/run_tests.py --test contracts
```

This validates the evidence-first progress contract, one-step unblock horizon, one-shot literature recovery after
direction failure,
and Phase 6b GitHub commit/push rules without invoking an agent or network operation.
