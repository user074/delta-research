#!/usr/bin/env bash
# =============================================================================
# worker.sh — Short-lived per-run execution agent
#
# Contract:
#   - Reads PLAN.md (immutable input)
#   - Executes commands
#   - Saves artifacts to RUNS/R###/artifacts/
#   - Writes structured REPORT to REPORTS/R###.md
#   - NEVER modifies STATE.md
#   - NEVER chooses new research directions (suggest only, via "next tests")
#   - NEVER modifies protocol lock fields
#   - Reports BLOCKER verdict if stop conditions trigger
#
# Usage: ./scripts/worker.sh R001
# Requires: claude CLI in PATH
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

RUN_ID="${1:?Usage: worker.sh R###}"
RUN_DIR="$ROOT/RUNS/$RUN_ID"
PLAN_PATH="$RUN_DIR/PLAN.md"
REPORT_PATH="$ROOT/REPORTS/${RUN_ID}.md"
ARTIFACTS_DIR="$RUN_DIR/artifacts"

# --- Validations ---

if [ ! -d "$RUN_DIR" ]; then
  echo "ERROR: Run directory not found: $RUN_DIR" >&2
  exit 1
fi

if [ ! -f "$PLAN_PATH" ]; then
  echo "ERROR: PLAN.md not found: $PLAN_PATH" >&2
  exit 1
fi

echo "Starting $RUN_ID"
echo "  Plan: $PLAN_PATH"
echo "  Report: $REPORT_PATH"
echo "  Artifacts: $ARTIFACTS_DIR"

START_TIME=$(date +%Y-%m-%dT%H:%M)

# --- Execute via Claude ---

claude --print -p "You are a research worker. You execute plans and produce structured evidence.

=== YOUR PLAN (read-only — do not modify) ===
$(cat "$PLAN_PATH")

=== STATE CONTEXT (read-only — do not modify STATE.md) ===
$(cat "$ROOT/STATE.md")

=== STRICT CONTRACT ===
1. Execute the Commands section from the plan, in order.
2. For each command, run it and capture output.
3. Save any generated files to: $ARTIFACTS_DIR/
4. If a Stop Condition triggers, immediately write a BLOCKER report and stop.
5. You MUST NOT:
   - Modify STATE.md
   - Modify PLAN.md
   - Choose new research directions (you may suggest in 'Next tests')
   - Change the protocol lock variables
   - Modify files outside $RUN_DIR/ and $REPORT_PATH
6. Be honest: null results are valuable data. Do not fabricate.

=== REPORT FORMAT (write to $REPORT_PATH) ===
Your report MUST use this exact structure:

# REPORT — $RUN_ID

## Result
| Metric | Baseline | Observed | Δ | Notes |
|--------|----------|----------|---|-------|
| [from plan's success metrics] | [baseline] | [what you measured] | [difference] | [notes] |

## Signal
- **score**: [0.0-1.0: 0=no info gained, 1=maximally informative]
- [bullet 1: what we learned]
- [bullet 2: why this signal level]

## Verdict
**[supports|contradicts|unclear|BLOCKER]** — [which belief this affects]

## Confounds
- [what else could explain the result]

## Next tests
1. [suggested delta 1]
2. [suggested delta 2]
3. [suggested delta 3]

## Artifacts
- \`artifacts/[filename]\` — [description]

## Errors
[any errors encountered, or 'None']

## Log (abbreviated)
\`\`\`
[key command outputs, truncated to essentials]
\`\`\`

## Meta
- **run_id**: $RUN_ID
- **delta**: [from plan]
- **started**: $START_TIME
- **completed**: [fill in]
- **status**: [completed|failed|blocker]

IMPORTANT: Write the report to $REPORT_PATH. This is your only deliverable." \
  2>/dev/null || true

# --- Verify output ---

if [ -f "$REPORT_PATH" ]; then
  echo "Report written: $REPORT_PATH"

  # Validate report structure (warn but don't fail)
  MISSING=""
  grep -q '## Result' "$REPORT_PATH" || MISSING="$MISSING Result"
  grep -q '## Signal' "$REPORT_PATH" || MISSING="$MISSING Signal"
  grep -q '## Verdict' "$REPORT_PATH" || MISSING="$MISSING Verdict"
  grep -q '## Confounds' "$REPORT_PATH" || MISSING="$MISSING Confounds"

  if [ -n "$MISSING" ]; then
    echo "WARNING: Report missing sections:$MISSING"
  fi
else
  echo "WARNING: No report produced. Creating failure report."
  DELTA=$(grep -oP '(?<=\*\*what changed\*\*:\s).+' "$PLAN_PATH" 2>/dev/null || echo "unknown")

  cat > "$REPORT_PATH" <<EOF
# REPORT — $RUN_ID

## Result
| Metric | Baseline | Observed | Δ | Notes |
|--------|----------|----------|---|-------|
| completion | success | failure | N/A | worker process failed |

## Signal
- **score**: 0.1
- No information gained from this run
- Worker process failed before producing results

## Verdict
**unclear** — no evidence collected

## Confounds
- Worker execution failure (not related to the delta itself)

## Next tests
1. Retry this delta with simpler commands
2. Debug worker execution environment
3. Reduce scope of the delta

## Artifacts
_None produced._

## Errors
Worker process exited without writing a report. Possible timeout or execution error.

## Log (abbreviated)
\`\`\`
No output captured.
\`\`\`

## Meta
- **run_id**: $RUN_ID
- **delta**: $DELTA
- **started**: $START_TIME
- **completed**: $(date +%Y-%m-%dT%H:%M)
- **status**: failed
EOF
  echo "Failure report written: $REPORT_PATH"
fi

echo "Done."
