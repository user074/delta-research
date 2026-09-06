# Testing delta-research

Run the local checks first; neither command invokes a model or submits a job:

```bash
python3 tests/run_tests.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

`run_tests.py` validates the checked-in examples and framework contracts. The unit
tests exercise CLI failures, deadline enforcement, logger cleanup, duplicate-attempt
prevention and recovery after publication failure. They use fake CLI/SLURM responses
and a temporary local Git remote. Passing them does not establish model quality or
live cluster compatibility.

## Live model evaluations

These commands consume model usage. Generation always starts in a fresh workspace
containing framework templates and fixture inputs, without checked-in answers or
worker artifacts:

```bash
# Generate and validate one case first
python3 tests/run_tests.py --run --test plan --output-dir /tmp/delta-plan-eval

# Generate all five cases, review with Sol, and validate
python3 tests/run_tests.py --run --review --agent codex

# Review a snapshot of the checked-in examples, without generating new answers
python3 tests/run_tests.py --review --test worker

# Revalidate a saved evaluation without model calls
python3 tests/run_tests.py --artifacts-dir /tmp/delta-plan-eval/tests --test plan
```

`--output-dir` must name a directory that does not exist. Without it, each evaluation
gets a new directory under `tests/evaluations/`. `--artifacts-dir` is validation-only.
`--test` accepts `init`, `plan`, `worker`, `compression`, `slurm`, `contracts`, or `all`.

The default agent is Codex. Planning and compression use `gpt-6-astra` at high effort;
initialization, worker execution, SLURM script generation and review use `gpt-5.6-sol`
at medium effort. Each case runs without nested agents. Use `--supervisor-model`,
`--worker-model`, `--review-model`, `--supervisor-effort`, and `--worker-effort` to
change routing; worker effort also applies to reviews. `--model` overrides all roles
for a controlled comparison. `--agent claude` uses Sonnet unless `--model` is supplied.
`--timeout SECONDS` overrides the per-invocation time limit.

Generation failure, a missing CLI, timeout, missing or empty output, changed protected
inputs, malformed review verdict or rejected review makes the overall command fail.
An unsuccessful generation is never validated against an old checked-in answer.
Reviews write Markdown feedback and a JSON verdict with `passed` and `issues`.

Each workspace stores a configuration manifest, copied framework, aggregate
`results.json`, and `evaluation_logs/` with exact prompts, commands, CLI versions,
stdout events, stderr, output hashes, errors, elapsed time and token usage when the
CLI exposes it. A CLI return of zero alone does not count as success.

## Cases and comparison criteria

| Case | Inputs | What to inspect |
|---|---|---|
| Initialization | `SYSTEM_PROFILE.md` | Accurate environment, paths, hardware and execution profile |
| Planning | `STATE.md` | Fastest adequate direct experiment, complete evidence, exact resources, short editable plan |
| Worker | `PLAN.md` | Executed measurement, complete comparison, reproducible artifacts, honest answer-first report |
| Compression | `STATE_before.md`, `REPORT.md` | One Ledger update, justified belief changes, no manufactured follow-up work |
| SLURM | `PLAN.md`, `INFRA.md` | Scripts only; all confirmed GPUs useful, failure propagation, logging and environment correctness |

For migration comparisons, change one factor at a time and retain every evaluation,
including failed attempts. Compare scientific adequacy and recovery correctness
before interpreting speed or price. Track total tokens and cost per valid completed
experiment, including worker retries and supervisor review. Prompt size and cheaper
model prices alone do not demonstrate savings on completed research.
