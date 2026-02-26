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

Don't rely on code alone. The human has context you can't get from files. Run an interactive interview:

**Round 1 — Project context** (ask these, wait for answers):
- What is this project? What does it do?
- What's your research question? What are you trying to figure out?
- What have you tried so far? What worked, what didn't?

**Round 2 — Hypotheses** (dig deeper based on round 1):
- What do you think is true but haven't proven? (these become seed beliefs)
- What are the competing explanations? (these shape the frontier)
- What would change your mind? (this defines what "discriminating" means)

**Round 3 — Practical setup**:
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

The file should contain:

- **Project overview** — what the project does, structure, key files (from 1a)
- **Research loop** section:
  - Research question and goals (from interview)
  - What's been tried, key constraints
  - Pointer: `See delta-research/templates/SUPERVISOR.md for the loop spec`
  - Pointer: `State lives in STATE.md`
  - How to run: `To continue research, say: "run the research loop"`
- If the file already exists, preserve existing non-research content and add/update the research sections

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
