# delta-research

LLM-driven research loop. Copy into any project. The agent reads one file and runs everything.

## Quick start

1. Copy `delta-research/` into your project
2. Tell your agent: *"Read `./delta-research/README.md` and initialize the research loop"*
3. The agent will read `templates/SUPERVISOR.md` section 2, ask you about your research goals and hypotheses, detect your environment (conda/venv), and create `STATE.md`
4. To run: *"Run the research loop"*

The loop runs autonomously — picks deltas, spawns workers, ingests reports, compresses state, repeats. It stops only on interrupt boundaries (budget exceeded, blocker hit, no more hypotheses to test).

Works with Claude Code, OpenAI Codex, Cursor, or any agent that reads markdown and executes commands.

## Initialization

When told to initialize, the agent will:
1. Read your project to understand context
2. Ask about your research question, hypotheses, and constraints
3. Detect your conda/venv environment and verify dependencies
4. Create `STATE.md` with seed beliefs and an initial experiment frontier
5. Create directories (`REPORTS/`, `RUNS/`, `ARTIFACTS/`)
6. Inject a research loop pointer into your project's `CLAUDE.md`

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

## Core idea

The loop treats research as a bandit problem over hypothesis space. Each run targets the most uncertain belief with a delta designed to discriminate — push the belief clearly toward supported or rejected. The agent uses accumulated history to get better at picking informative experiments.

Negative results that clearly reject a hypothesis are as valuable as positive ones. The goal is to bisect the belief space efficiently.
