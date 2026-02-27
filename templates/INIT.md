# Initialization

> Run this when STATE.md does not exist.
> The human is present. Use them — they know the project better than any README.

---

## Step 1: Understand the project and write agent instructions

### 1a: Read the codebase

Before talking to the human, scan the repo like a standard /init:
- Key files, project structure, languages, frameworks, what it does
- Entry points, configs, existing documentation
- Note anything relevant to research (data directories, model code, experiment scripts)

### 1b: Interview the human

The code reading gives you a head start. Use it. Don't ask the human things you can already see in the code — instead, lead with your understanding and let them correct or extend it.

**Do NOT dump all questions at once.** This is a conversation, not a form. One round at a time. Wait for the human's response before moving to the next round.

**Round 1 — Project context**:
Lead with what you learned from the code and present it to the human. For example: *"From reading the repo, this looks like [X] that does [Y]. The main entry point is [Z]. Is that right? What's the research question you're trying to answer?"*

Let the human confirm, correct, or add what's missing. Ask about what they've tried and what worked/didn't. Talk to human until you have a good understanding of the project and their research goals.

**Round 2 — Hypotheses** (dig deeper based on round 1):
Ask the human to list their hypotheses one by one. Do not dump all questions at once.
- What do you think is true but haven't proven? (these become seed beliefs)
- What are the competing explanations? (these shape the frontier)
- What would change your mind? (this defines what "discriminating" means)

**Round 3 — Practical setup**:
Ask the human to list their constraints one by one. Do not dump all questions at once.
- What does success look like? When would you stop?
- Any constraints — time budget, compute limits, things not to touch?
- Any irreversible actions to watch for?

Adapt the interview based on what the human says. If they mention something interesting, follow up. The goal is to extract their mental model of the problem — not just fill in template fields.

### 1c: Write CLAUDE.md / AGENTS.md

Detect which agent is running. Write or update the appropriate instruction file(s).

| Agent | Instruction file | Multi-agent config |
|-------|-----------------|-------------------|
| Claude Code | `CLAUDE.md` | N/A (Task tool built-in) |
| OpenAI Codex | `AGENTS.md` | `codex.toml` or project config |
| Cursor | `.cursorrules` | N/A |

If unsure, write both `CLAUDE.md` and `AGENTS.md`.

If CLAUDE.md or AGENTS.md already exists, read it first. Incorporate any useful existing content into the updated file — don't discard what's already there.

If there is a README.md, read it and include the important parts (project purpose, setup, key commands) — don't make the agent re-discover what's already documented.

The file should contain:

- **Project overview** — the goal is to give future agent sessions enough context to be productive immediately, without re-reading the whole codebase:
  - What the project does (one paragraph)
  - High-level architecture: how the major components fit together, data flow, key abstractions. Focus on the "big picture" that requires reading multiple files to understand — things an agent can't figure out from a single file
  - Key files and entry points (only the important ones, not an exhaustive listing — agents can discover the rest with tools)
  - Common commands: how to run the project, run tests, build, etc. For research projects this might be how to run experiments, launch training, evaluate models
  - Important gotchas, non-obvious conventions, or anything that would trip up a new contributor
  - Avoid: listing every file/directory (easily discovered), generic development practices, information that duplicates README.md verbatim
- **Research loop** section:
  - Research question and goals (from interview)
  - Key constraints (from interview)
  - Pointer: `See delta-research/templates/SUPERVISOR.md for the loop spec`
  - Pointer: `Current state (beliefs, what's been tried, frontier) lives in STATE.md`
  - How to run: `To continue research, say: "run the research loop"`

For Codex, also enable multi-agent in config:
```toml
[features]
multi_agent = true

[agents.worker]
description = "Research worker: executes a single experiment plan, writes a structured report. Never modifies STATE.md or PLAN.md."
```

---

## Step 2: Environment setup

Spawn an environment agent to handle setup. This is separate from the research loop — the supervisor does not manage conda, GPUs, or dependencies directly.

The environment agent should:
- Detect active conda/venv, confirm with human
- Check GPU availability if relevant (`nvidia-smi`)
- Verify key dependencies are importable
- Install missing packages within the env
- Locate model checkpoints, datasets, and other resources
- Record everything in STATE.md Environment section
- Check user how many GPUs to use during training and maximize the utilization of the GPUs
- Check whether to use wandb for logging during training and how to configure it (start a new project, existing project, etc.)
- Check whether there are any existing data, model, or trained checkpoints directories and how to use them. If there are, ask the user to confirm whether to use them. If there are no existing directories, ask the user how would they like to create them.

**Agent-specific spawning:**
- **Claude Code**: `Task(subagent_type="general-purpose", prompt="Set up and verify the research environment. <details from interview>. Record in STATE.md Environment section.")`
- **Codex**: Spawn a sub-agent for environment setup.

The environment can be re-invoked later (new model, GPU change) without touching research state.

---

## Step 3: Set up permissions for autonomous operation

The research loop runs shell commands (python scripts, data processing, etc.). Configure permissions so the loop can run without approval prompts interrupting it.

**Claude Code** — create or update `.claude/settings.local.json`:
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
For full autonomy (if the human agrees), use `"allow": ["Bash(*)"]`. The conda/venv env is the safety boundary.

**Codex** — runs in a sandboxed container by default, so permissions are less of a concern. Use `--full-auto` flag when launching. Ensure the container image has the right conda env and dependencies pre-installed, or let the agent install them.

**Other agents** — configure equivalent auto-approval for shell commands per the agent's docs.

Ask the human which permission level they want before writing the config. Show them the options:
1. **Scoped** (recommended): python, pip, conda, mkdir only
2. **Full autonomy**: all shell commands (`Bash(*)`)
3. **Manual**: no auto-permissions, approve each command

---

## Step 4: Create project structure

```
mkdir -p REPORTS RUNS ARTIFACTS
```

---

## Step 5: Create STATE.md

Use `templates/STATE.template.md` as structure. Fill in from the interview:
- Project name, goal, date
- Seed beliefs from the human's hypotheses (confidence 0.5)
- Initial frontier: deltas that would discriminate between competing hypotheses
- Policy: budget, interrupt thresholds
- Environment section populated by environment agent

---

## Step 6: Confirm with human

Show STATE.md and the written CLAUDE.md/AGENTS.md. Are the seed beliefs right? Is the frontier targeting the right questions? Anything missing from the environment setup? Are permissions configured correctly?

Once confirmed, tell the human: *"To start the research loop, say: run the research loop"*. The agent will then read `templates/SUPERVISOR.md` and begin cycling.
