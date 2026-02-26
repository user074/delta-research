# delta-research

LLM-driven research loop. Copy into any project. The agent reads one file and runs everything.

## Key Design Principles
![Research Loop](assets/research_loop.png)

We design around the following principles:
- Delta: The unit of progress is *what changed → what happened → what it means*.
- Bisect the hypothesis space: A good delta splits uncertain beliefs in two. Even negative results are progress if they eliminate a direction.
- High level overview: We track hypotheses that are most likely to be true or false.
- Compatibility with existing tools: Just use your Claude Code or Codex. We recommend use multi-agent mode for Codex.

## Quick start

1. Copy `delta-research/` into your project
2. Activate your environment: `conda activate your-env` or `source venv/bin/activate`
3. Start your code agent. For full autonomy use `--dangerously-skip-permissions` (Claude Code) or `--full-auto` (Codex).
4. Tell your agent: *"Read `./delta-research/README.md` and initialize the research loop"*
5. The agent reads `templates/INIT.md`, interviews you, sets up permissions, detects your environment, and creates `STATE.md`
6. **To start the automated research loop**: Tell your agent: *"Run the research loop"*

The loop runs autonomously — picks deltas, spawns workers, ingests reports, compresses state, repeats. It stops only on interrupt boundaries (budget exceeded, blocker hit, no more hypotheses to test).

Works with Claude Code, OpenAI Codex, Cursor, or any agent that reads markdown and executes commands.

## Initialization

When told to initialize, the agent reads `templates/INIT.md` and will:
1. **Understand the project and write agent instructions** — read the codebase, interview you about research goals/hypotheses/constraints, then write CLAUDE.md/AGENTS.md with project context and research loop pointers
2. **Set up environment** — spawn an environment agent to detect conda/venv, GPUs, verify dependencies, locate checkpoints and datasets
3. **Set up permissions** — configure auto-approval for shell commands so the loop runs without interruption (asks you which level you want)
4. **Create directories** — `REPORTS/`, `RUNS/`, `ARTIFACTS/`
5. **Create `STATE.md`** — seed beliefs from your hypotheses, initial experiment frontier, environment config

The full procedure is in `templates/INIT.md`.

## What's in the box

```
templates/
  INIT.md                # First-time setup — interview, environment, permissions
  SUPERVISOR.md          # The loop — delta selection, worker spawning, state compression
  STATE.template.md      # Structure for STATE.md
  PLAN.template.md       # Structure for per-run plans
  REPORT.template.md     # Structure for per-run reports
```

Everything else (`STATE.md`, `RUNS/`, `REPORTS/`, `ARTIFACTS/`) is created by the agent at runtime.

## Running

> "Run the research loop"

The agent reads `templates/SUPERVISOR.md` and cycles: pick the delta most likely to discriminate uncertain beliefs, spawn a worker, ingest the report, compress state, repeat.

## Core idea

The loop treats research as a bandit problem over hypothesis space. Each run targets the most uncertain belief with a delta designed to discriminate — push the belief clearly toward supported or rejected. The agent uses accumulated history to get better at picking informative experiments.

Negative results that clearly reject a hypothesis are as valuable as positive ones. The goal is to bisect the belief space efficiently.

## Testing

`tests/` has sample fixtures and automated validation. See `tests/README.md` for details.

```bash
# Generate outputs by spawning the agent, then validate
python tests/run_tests.py --run

# Or run a single test
python tests/run_tests.py --run --test plan
python tests/run_tests.py --run --test worker
python tests/run_tests.py --run --test compression

# Validate existing outputs (after generating manually)
python tests/run_tests.py

# Use codex instead of claude
python tests/run_tests.py --run --agent codex
```

The validator checks structural properties: required sections, inline data, visualizations, belief confidence changes, frontier updates, new belief generation. After editing `SUPERVISOR.md`, re-run the tests and compare outputs.
