# delta-research

A structured research control loop. Downloads into any repo. Agent-agnostic.

## Design

**Delta-first**: the unit of progress is *what changed → what happened → what it means*.

```
Supervisor (long-lived)         Worker (short-lived, per run)
  Read STATE.md                   Read PLAN.md
  Pick delta from Frontier        Execute commands
  Write PLAN.md ─────────────────► Save artifacts
  Wait for report ◄────────────── Write REPORT.md
  Compress into STATE.md
  Recompile DASHBOARD.md
  Check interrupt boundaries
  Repeat
```

**Supervisor** = decision + memory. Never parses raw logs. Never debugs scripts mid-run.
**Worker** = execution + evidence. Never changes global state. Never picks direction.

The separation is the autonomy enabler.

## Quick start

```bash
# Drop into any existing repo:
git clone <this-repo> /tmp/delta-research
cp -r /tmp/delta-research/{scripts,templates} ./
cp /tmp/delta-research/.gitkeep ./ARTIFACTS/plots/ 2>/dev/null; true

# Initialize
./scripts/init.sh "My Research" "Understand X by testing Y"

# Edit STATE.md: replace seed beliefs and frontier with your own

# Option A: let the supervisor run autonomously
./scripts/supervisor.sh 5          # up to 5 cycles

# Option B: manual single run
./scripts/new_run.sh "test hypothesis A"
vim RUNS/R001/PLAN.md              # fill in the plan
./scripts/worker.sh R001           # execute
```

## The three critical artifacts

### STATE.md — memory + control surface
| Section | Purpose |
|---------|---------|
| BeliefState | Supported / rejected / conflicting beliefs with confidence scores |
| Ledger | Append-only: run → delta → metric → signal → verdict |
| Frontier | Ranked next deltas, each says what it disambiguates + cost/risk |
| Policy | Interrupt rules, scoring thresholds, template stats |
| Scratch | Open questions, hunches |

### PLAN.md — supervisor → worker instruction
- Delta definition (what changed / intent / disambiguates)
- Protocol lock (baseline, controlled vars, eval method — immutable)
- Commands (exact steps)
- Stop conditions (BLOCKER if...)

### REPORT.md — worker → supervisor evidence
- Result table (metric / baseline / observed / Δ)
- Signal score (0–1) + 2-bullet justification
- Verdict (supports / contradicts / unclear / BLOCKER)
- Confounds
- Next tests (top 3)

## Interrupt boundaries

The supervisor keeps going by default. It stops when:
- **BUDGET**: wall-clock time exceeded
- **NULL_STREAK**: N consecutive low-signal runs
- **BLOCKER**: worker reports a blocking issue
- **AMBIGUITY**: frontier empty and regeneration fails
- **IRREVERSIBLE**: next delta needs human approval

## Structure

```
STATE.md                 # Single source of truth
DASHBOARD.md             # Auto-compiled summary
REPORTS/R###.md          # Structured evidence per run
RUNS/R###/PLAN.md        # Execution plan per run
RUNS/R###/artifacts/     # Data, logs, outputs
ARTIFACTS/plots/         # Generated visualizations
scripts/
  init.sh                # Initialize in any repo
  supervisor.sh          # Long-lived control loop
  worker.sh              # Single-run executor
  new_run.sh             # Create run skeleton
  compile_dashboard.py   # STATE.md → DASHBOARD.md
templates/               # All markdown templates
CLAUDE.md                # Agent guidelines (auto-generated)
```

## Agent compatibility

The loop is markdown-based by design — easy to migrate between agents:
- **Claude Code**: uses `claude --print -p` for supervisor/worker spawning
- **Cursor**: append `templates/GUIDELINES.append.md` to `.cursorrules`
- **Other agents**: the contract is just files — any agent that reads/writes markdown works
- **Manual**: create plans by hand, execute yourself, write reports

## Prerequisites

- `claude` CLI in PATH (for automated supervisor/worker)
- Python 3.8+ (for dashboard compiler)
- Optional: matplotlib (for plots)
