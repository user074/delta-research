# delta-research

LLM-driven research loop. Copy into any project. The agent reads one file and runs everything.

## Setup

Copy `delta-research/` into your project. Tell your agent:

> "Initialize the research loop for this project"

It reads `templates/SUPERVISOR.md` section 2, talks to you about goals and hypotheses, creates `STATE.md`.

## Running

> "Run the research loop"

The agent reads `templates/SUPERVISOR.md` section 3 and cycles: pick the delta most likely to discriminate uncertain beliefs, spawn a worker, ingest the report, compress state, repeat.

## What's in the box

```
templates/
  SUPERVISOR.md          # The spec — loop logic, contracts, worker template
  STATE.template.md      # Structure for STATE.md
  PLAN.template.md       # Structure for per-run plans
  REPORT.template.md     # Structure for per-run reports
```

Everything else is created by the agent at runtime.

## Core idea

The loop treats research as a bandit problem over hypothesis space. Each run is a delta that targets the most uncertain belief. Signal is categorical — did this run discriminate (clearly support or contradict a belief), partially inform, or produce nothing? The agent uses accumulated history to get better at picking informative experiments.

Negative results that clearly reject a hypothesis are as valuable as positive ones. The goal is to bisect the belief space efficiently.
