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

1. Initialize the agent in your project. First 'conda activate your-env' or 'source venv/bin/activate'. Then you start your code agent. If you want true yolo mode use '--dangerously-skip-permissions' flag (claude code) or '--yolo' flag (codex). If you have not initialized your agent you should use command '/init' to initialize the agent.
2. Copy `delta-research/` into your project
3. Tell your agent: *"Read `./delta-research/README.md` and initialize the research loop"*
4. The agent will read `templates/SUPERVISOR.md` section 2, ask you about your research goals and hypotheses, detect your environment (conda/venv), and create `STATE.md`
5. **To start the automated research loop**: Just tell your agent: *"Run the research loop"*

The loop runs autonomously — picks deltas, spawns workers, ingests reports, compresses state, repeats. It stops only on interrupt boundaries (budget exceeded, blocker hit, no more hypotheses to test).

Works with Claude Code, OpenAI Codex, Cursor, or any agent that reads markdown and executes commands.

## Initialization

When told to initialize, the agent will:
1. **Interview you** — ask about your research question, hypotheses, what you've tried, what would change your mind
2. **Set up environment** — spawn an environment agent to detect conda/venv, GPUs, verify dependencies, locate checkpoints and datasets
3. **Create `STATE.md`** — seed beliefs from your hypotheses, initial experiment frontier, environment config
4. **Create directories** — `REPORTS/`, `RUNS/`, `ARTIFACTS/`
5. **Inject config** — research loop pointer into `CLAUDE.md` / `AGENTS.md`

The full procedure is in `templates/SUPERVISOR.md` section 2.

## Permissions for autonomous operation

The loop runs shell commands (python scripts, data processing, etc.). To avoid approval prompts interrupting autonomous runs:

**Claude Code** — configure `.claude/settings.local.json`:
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
Or `"allow": ["Bash(*)"]` for full autonomy (conda env is the safety boundary).

**Codex** — runs in a sandboxed container by default, so permissions are less of a concern. Ensure the container image has the right conda env and dependencies pre-installed, or let the agent install during init.

## What's in the box

```
templates/
  SUPERVISOR.md          # The spec — loop logic, contracts, worker template
  STATE.template.md      # Structure for STATE.md
  PLAN.template.md       # Structure for per-run plans
  REPORT.template.md     # Structure for per-run reports
```

Everything else (`STATE.md`, `RUNS/`, `REPORTS/`, `ARTIFACTS/`) is created by the agent at runtime.

## Running

> "Run the research loop"

The agent reads `templates/SUPERVISOR.md` section 3 and cycles: pick the delta most likely to discriminate uncertain beliefs, spawn a worker, ingest the report, compress state, repeat.


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
