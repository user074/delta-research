#!/usr/bin/env bash
# =============================================================================
# new_run.sh — Create a new run directory with PLAN skeleton
#
# Usage:
#   ./scripts/new_run.sh "delta description"
#   ./scripts/new_run.sh                      # creates with placeholders
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

# --- Determine next run ID ---

LAST_RUN=$(ls -d "$ROOT/RUNS/R"* 2>/dev/null | sort -V | tail -1 | grep -oE '[0-9]+' || echo "0")
NEXT_NUM=$((10#$LAST_RUN + 1))
RUN_ID=$(printf "R%03d" "$NEXT_NUM")

DATE="$(date +%Y-%m-%d)"
DELTA="${1:-_describe the delta here_}"

RUN_DIR="$ROOT/RUNS/$RUN_ID"
mkdir -p "$RUN_DIR/artifacts"

# --- Generate PLAN.md ---

cat > "$RUN_DIR/PLAN.md" <<EOF
# PLAN — $RUN_ID

## Delta
- **what changed**: $DELTA
- **intent**: _why we're testing this_
- **disambiguates**: _which belief or question this resolves_
- **type**: exploration

## Protocol lock
- **baseline**: _what to compare against_
- **controlled vars**: _what must stay the same_
- **eval method**: _how to measure_

## Commands
\`\`\`
_command 1_
_command 2_
\`\`\`

## Success metrics
| Metric | Baseline | Target | How to measure |
|--------|----------|--------|----------------|
| _metric_ | _baseline_ | _target_ | _method_ |

## Stop conditions
- BLOCKER if: _critical failure condition_
- TIMEOUT after: 10 min

## Context
_See STATE.md for current beliefs and prior runs._

## Meta
- **run_id**: $RUN_ID
- **created**: $DATE
- **time_budget**: 10 min
- **status**: planned
EOF

echo "$RUN_ID"
echo "  Plan:      $RUN_DIR/PLAN.md"
echo "  Artifacts: $RUN_DIR/artifacts/"
echo ""
echo "Next: edit the PLAN, then run ./scripts/worker.sh $RUN_ID"
