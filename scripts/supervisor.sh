#!/usr/bin/env bash
# =============================================================================
# supervisor.sh — Long-lived research control loop
#
# Design principles:
#   Delta-first: unit of progress is what changed → what happened → what it means
#   Compression: continuously compress runs into BeliefState + Frontier
#   Autonomy with crisp interrupts: keep going unless boundary triggers
#   Clean credit: one major delta per run
#
# Usage: ./scripts/supervisor.sh [max_runs]
# Requires: claude CLI in PATH
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

MAX_RUNS="${1:-0}"  # 0 = unlimited
RUN_COUNT=0
NULL_STREAK=0
START_TIME=$(date +%s)

# --- Load policy from STATE.md ---

load_policy() {
  local state="$ROOT/STATE.md"
  NULL_STREAK_LIMIT=$(grep -oP '(?<=NULL_STREAK.*:\s)\d+' "$state" 2>/dev/null || echo "3")
  MAX_BUDGET=$(grep -oP '(?<=BUDGET.*exceeds\s)\S+' "$state" 2>/dev/null || echo "60min")
  # Convert budget to seconds
  BUDGET_NUM=$(echo "$MAX_BUDGET" | grep -oP '\d+')
  BUDGET_UNIT=$(echo "$MAX_BUDGET" | grep -oP '[a-z]+')
  case "$BUDGET_UNIT" in
    min) BUDGET_SECS=$((BUDGET_NUM * 60)) ;;
    h|hr|hour) BUDGET_SECS=$((BUDGET_NUM * 3600)) ;;
    *) BUDGET_SECS=$((BUDGET_NUM * 60)) ;;
  esac
}

# --- Logging ---

log() { echo "[supervisor $(date +%H:%M:%S)] $*"; }

# --- Run ID management ---

next_run_id() {
  local last
  last=$(ls -d "$ROOT/RUNS/R"* 2>/dev/null | sort -V | tail -1 | grep -oE '[0-9]+' || echo "0")
  printf "R%03d" "$(( 10#$last + 1 ))"
}

# --- Frontier operations ---

frontier_is_empty() {
  local count
  count=$(sed -n '/^## Frontier/,/^## /p' "$ROOT/STATE.md" \
    | grep '^\s*|' | tail -n +3 | grep -v '^\s*$' | wc -l)
  [ "$count" -eq 0 ]
}

pick_top_delta() {
  # Return the top non-blocked delta from frontier
  sed -n '/^## Frontier/,/^## /p' "$ROOT/STATE.md" \
    | grep '^\s*|' \
    | tail -n +3 \
    | while IFS='|' read -r _ rank delta disamb cost risk blocked _rest; do
        blocked_trimmed=$(echo "$blocked" | xargs)
        if [ "$blocked_trimmed" = "—" ] || [ -z "$blocked_trimmed" ]; then
          echo "$delta" | xargs
          return 0
        fi
      done
}

# --- Interrupt boundary checks ---

check_interrupts() {
  # BUDGET: wall-clock time exceeded
  local elapsed=$(( $(date +%s) - START_TIME ))
  if [ "$elapsed" -ge "$BUDGET_SECS" ]; then
    log "INTERRUPT [BUDGET]: ${elapsed}s elapsed, limit ${BUDGET_SECS}s"
    return 1
  fi

  # NULL_STREAK: consecutive low-signal runs
  if [ "$NULL_STREAK" -ge "$NULL_STREAK_LIMIT" ]; then
    log "INTERRUPT [NULL_STREAK]: $NULL_STREAK consecutive low-signal runs (limit: $NULL_STREAK_LIMIT)"
    return 1
  fi

  # MAX_RUNS: explicit run cap
  if [ "$MAX_RUNS" -gt 0 ] && [ "$RUN_COUNT" -ge "$MAX_RUNS" ]; then
    log "INTERRUPT [MAX_RUNS]: completed $RUN_COUNT of $MAX_RUNS"
    return 1
  fi

  return 0
}

# --- Phase 1: Select delta ---

select_delta() {
  local delta
  delta=$(pick_top_delta)

  if [ -z "$delta" ]; then
    log "Frontier exhausted or all blocked. Regenerating..."
    regenerate_frontier
    delta=$(pick_top_delta)
  fi

  if [ -z "$delta" ]; then
    log "INTERRUPT [AMBIGUITY]: Cannot generate frontier. Human input needed."
    return 1
  fi

  echo "$delta"
}

regenerate_frontier() {
  log "Asking agent to regenerate frontier from current state..."
  claude --print -p "You are a research supervisor. Read $ROOT/STATE.md.

The frontier is empty or all deltas are blocked. Based on:
- Current BeliefState (which beliefs need more evidence?)
- Ledger (what has been tried? what signal patterns emerged?)
- Template stats (which delta types produce signal?)
- Scratch notes

Generate 3-5 new ranked deltas for the Frontier table.

Output ONLY markdown table rows (no header, no fence) in this format:
| Rank | Delta | Disambiguates | Cost | Risk | Blocked by |

Rules:
- Each delta must test exactly one thing (clean credit assignment)
- Rank by expected information gain, not by ease
- Mark cost as low/medium/high
- Mark risk as low/medium/high
- Use '—' for unblocked deltas" > /tmp/frontier_rows.txt 2>/dev/null || true

  if [ -s /tmp/frontier_rows.txt ]; then
    python3 -c "
import re
state = open('$ROOT/STATE.md').read()
rows = open('/tmp/frontier_rows.txt').read().strip()
header = '''| Rank | Delta | Disambiguates | Cost | Risk | Blocked by |
|------|-------|---------------|------|------|------------|
'''
section = '## Frontier\n<!-- Ranked next deltas. Each says what it disambiguates and its cost/risk. -->\n<!-- Supervisor picks top non-blocked entry. Regenerate when empty. -->\n\n' + header + rows + '\n'
state = re.sub(r'## Frontier.*?(?=\n## )', section, state, flags=re.DOTALL)
open('$ROOT/STATE.md', 'w').write(state)
"
    log "Frontier regenerated."
  else
    log "WARNING: Frontier regeneration produced no output."
  fi
}

# --- Phase 2: Write plan ---

write_plan() {
  local run_id="$1" delta="$2" run_dir="$3"

  log "Generating PLAN for $run_id: $delta"
  claude --print -p "You are a research supervisor writing an execution plan.

Read $ROOT/STATE.md for full context (beliefs, ledger, frontier).

Write a PLAN for run $run_id with delta: \"$delta\"

Use this EXACT structure (fill in all fields, no placeholders):

# PLAN — $run_id

## Delta
- **what changed**: [specific change being tested]
- **intent**: [why we're testing this]
- **disambiguates**: [which belief or question this resolves]
- **type**: [exploration|validation|ablation|baseline|debug]

## Protocol lock
- **baseline**: [what to compare against]
- **controlled vars**: [what must stay the same]
- **eval method**: [how to measure]

## Commands
\`\`\`
[exact commands the worker should run, one per line]
\`\`\`

## Success metrics
| Metric | Baseline | Target | How to measure |
|--------|----------|--------|----------------|
| [metric] | [baseline value] | [target value] | [measurement method] |

## Stop conditions
- BLOCKER if: [condition that should halt execution]
- TIMEOUT after: 10 min

## Context
[relevant beliefs and prior run results from STATE.md]

## Meta
- **run_id**: $run_id
- **created**: $(date +%Y-%m-%d)
- **time_budget**: 10 min
- **status**: planned

Rules:
- One major delta only (clean credit assignment)
- Commands must be concrete and executable
- Protocol lock fields are immutable during execution" > "$run_dir/PLAN.md" 2>/dev/null
}

# --- Phase 3: Spawn worker ---

spawn_worker() {
  local run_id="$1" run_dir="$2"
  local report_path="$ROOT/REPORTS/${run_id}.md"

  log "Spawning worker for $run_id..."
  "$ROOT/scripts/worker.sh" "$run_id" 2>&1 | while IFS= read -r line; do
    echo "  [worker] $line"
  done

  # Check for report
  if [ -f "$report_path" ]; then
    echo "$report_path"
  else
    echo ""
  fi
}

# --- Phase 4: Ingest report, compress state ---

ingest_report() {
  local run_id="$1" report_path="$2"

  log "Ingesting report and compressing state..."
  claude --print -p "You are a research supervisor. Your job is to compress a run result into state updates.

Read these files:
1. $ROOT/STATE.md (current state)
2. $report_path (latest run report)

Perform these updates to STATE.md:

1. LEDGER: append one row: | $run_id | [delta] | [key metric] | [signal score] | [verdict] | REPORTS/${run_id}.md |
2. BELIEFSTATE: update confidence for affected beliefs based on the verdict
   - 'supports' → increase confidence by 0.1-0.2
   - 'contradicts' → decrease confidence by 0.1-0.2
   - 'unclear' → no change, note in evidence
   - 'BLOCKER' → flag belief as conflicting
   - Promote to 'supported' if confidence ≥ 0.8
   - Demote to 'rejected' if confidence ≤ 0.2
   - Mark 'conflicting' if evidence splits
3. FRONTIER: remove the completed delta. Add any 'next tests' from the report.
4. TEMPLATE STATS: update delta type averages
5. META: increment total_runs, update last_updated to $(date +%Y-%m-%d)
6. SCRATCH: add any notable observations

Output the COMPLETE updated STATE.md. All sections must be present.
Output ONLY the file content, no commentary." > "$ROOT/STATE.md.tmp" 2>/dev/null || true

  if [ -s "$ROOT/STATE.md.tmp" ]; then
    mv "$ROOT/STATE.md.tmp" "$ROOT/STATE.md"
    log "STATE.md compressed and updated."
    return 0
  else
    rm -f "$ROOT/STATE.md.tmp"
    log "WARNING: State compression failed. STATE.md unchanged."
    return 1
  fi
}

# --- Phase 5: Check verdict for BLOCKER ---

check_blocker() {
  local report_path="$1"
  if grep -q '^\*\*BLOCKER\*\*' "$report_path" 2>/dev/null; then
    log "INTERRUPT [BLOCKER]: Worker reported BLOCKER verdict."
    return 0
  fi
  return 1
}

# --- Extract signal score from report ---

extract_signal() {
  local report_path="$1"
  grep -oP '(?<=\*\*score\*\*:\s)[0-9.]+' "$report_path" 2>/dev/null || echo "0"
}

# =============================================================================
# MAIN LOOP
# =============================================================================

if [ ! -f "$ROOT/STATE.md" ]; then
  log "ERROR: STATE.md not found. Run: ./scripts/init.sh \"Project\" \"Goal\""
  exit 1
fi

if ! command -v claude &>/dev/null; then
  log "ERROR: 'claude' CLI not found in PATH"
  exit 1
fi

load_policy
log "=== Supervisor starting ==="
log "Budget: ${BUDGET_SECS}s | Null streak limit: $NULL_STREAK_LIMIT | Max runs: ${MAX_RUNS:-∞}"

while true; do
  # --- Interrupt check ---
  if ! check_interrupts; then
    break
  fi

  log "━━━ Cycle $((RUN_COUNT + 1)) ━━━"

  # --- Phase 1: Select delta ---
  DELTA=$(select_delta) || break
  log "Delta: $DELTA"

  # --- Create run directory ---
  RUN_ID=$(next_run_id)
  RUN_DIR="$ROOT/RUNS/$RUN_ID"
  mkdir -p "$RUN_DIR/artifacts"

  # --- Phase 2: Write plan ---
  write_plan "$RUN_ID" "$DELTA" "$RUN_DIR"

  if [ ! -s "$RUN_DIR/PLAN.md" ]; then
    log "WARNING: Plan generation failed. Skipping."
    continue
  fi

  # --- Phase 3: Spawn worker ---
  REPORT_PATH=$(spawn_worker "$RUN_ID" "$RUN_DIR")

  if [ -z "$REPORT_PATH" ] || [ ! -f "$REPORT_PATH" ]; then
    REPORT_PATH="$ROOT/REPORTS/${RUN_ID}.md"
    # Worker creates fallback report, but double-check
    if [ ! -f "$REPORT_PATH" ]; then
      log "WARNING: No report produced. Recording null result."
      NULL_STREAK=$((NULL_STREAK + 1))
      RUN_COUNT=$((RUN_COUNT + 1))
      continue
    fi
  fi

  # --- Check BLOCKER ---
  if check_blocker "$REPORT_PATH"; then
    ingest_report "$RUN_ID" "$REPORT_PATH" || true
    break
  fi

  # --- Track signal for null streak ---
  SIGNAL=$(extract_signal "$REPORT_PATH")
  if python3 -c "exit(0 if float('$SIGNAL') < 0.2 else 1)" 2>/dev/null; then
    NULL_STREAK=$((NULL_STREAK + 1))
    log "Low signal ($SIGNAL). Null streak: $NULL_STREAK"
  else
    NULL_STREAK=0
  fi

  # --- Phase 4: Ingest and compress ---
  ingest_report "$RUN_ID" "$REPORT_PATH"

  # --- Phase 5: Recompile dashboard ---
  python3 "$ROOT/scripts/compile_dashboard.py" --plots 2>/dev/null || \
    python3 "$ROOT/scripts/compile_dashboard.py" 2>/dev/null || \
    log "WARNING: Dashboard compilation failed"

  RUN_COUNT=$((RUN_COUNT + 1))
  log "Cycle complete. Runs: $RUN_COUNT | Null streak: $NULL_STREAK"
  echo ""
done

# Final dashboard compile
python3 "$ROOT/scripts/compile_dashboard.py" 2>/dev/null || true

ELAPSED=$(( $(date +%s) - START_TIME ))
log "=== Supervisor stopped: $RUN_COUNT runs in ${ELAPSED}s ==="
