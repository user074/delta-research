#!/usr/bin/env bash
# =============================================================================
# init.sh — Initialize the research loop in any repo
#
# Designed to be dropped into an existing project without clobbering.
# Safe to re-run: skips files that already exist, appends guidelines only once.
#
# Usage:
#   ./scripts/init.sh "Project Name" "Research goal"
#   ./scripts/init.sh  (interactive — prompts for name and goal)
#
# What it does:
#   1. Creates STATE.md and DASHBOARD.md from templates (if they don't exist)
#   2. Creates directory structure (REPORTS/, RUNS/, ARTIFACTS/)
#   3. Appends research loop guidelines to CLAUDE.md (or agent config)
#   4. Leaves existing files untouched
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
DATE="$(date +%Y-%m-%d)"

# --- Input ---

if [ $# -ge 2 ]; then
  PROJECT_NAME="$1"
  GOAL="$2"
elif [ $# -eq 1 ]; then
  PROJECT_NAME="$1"
  read -rp "Research goal: " GOAL
else
  read -rp "Project name: " PROJECT_NAME
  read -rp "Research goal: " GOAL
fi

echo "=== Initializing: $PROJECT_NAME ==="
echo "Goal: $GOAL"
echo ""

# --- Directories (always safe) ---

mkdir -p "$ROOT/REPORTS" "$ROOT/RUNS" "$ROOT/ARTIFACTS/plots"
echo "[+] Directories ensured"

# --- STATE.md ---

if [ -f "$ROOT/STATE.md" ]; then
  echo "[~] STATE.md already exists, skipping (delete to regenerate)"
else
  sed \
    -e "s|{{PROJECT_NAME}}|$PROJECT_NAME|g" \
    -e "s|{{GOAL}}|$GOAL|g" \
    -e "s|{{DATE}}|$DATE|g" \
    -e "s|{{SEED_BELIEF}}|_seed belief — edit this_|g" \
    -e "s|{{FIRST_DELTA}}|_first experiment — edit this_|g" \
    -e "s|{{WHAT_IT_TESTS}}|_what question this answers_|g" \
    -e "s|{{MAX_BUDGET}}|60min|g" \
    -e "s|{{NULL_STREAK_LIMIT}}|3|g" \
    "$ROOT/templates/STATE.template.md" > "$ROOT/STATE.md"
  echo "[+] STATE.md created"
fi

# --- DASHBOARD.md ---

if [ -f "$ROOT/DASHBOARD.md" ]; then
  echo "[~] DASHBOARD.md already exists, skipping"
else
  python3 "$ROOT/scripts/compile_dashboard.py" 2>/dev/null || \
    cp "$ROOT/templates/DASHBOARD.template.md" "$ROOT/DASHBOARD.md"
  echo "[+] DASHBOARD.md created"
fi

# --- Agent guidelines ---
# Supports CLAUDE.md (Claude Code), .cursorrules (Cursor), AGENTS.md (generic)
# Appends only once (checks for marker text)

GUIDELINES="$ROOT/templates/GUIDELINES.append.md"
MARKER="Research Loop Guidelines"

append_guidelines() {
  local target="$1"
  if [ -f "$target" ]; then
    if grep -q "$MARKER" "$target" 2>/dev/null; then
      echo "[~] $target already has guidelines"
      return
    fi
    echo "" >> "$target"
    cat "$GUIDELINES" >> "$target"
    echo "[+] Guidelines appended to $target"
  else
    cp "$GUIDELINES" "$target"
    echo "[+] $target created from guidelines"
  fi
}

# Default: CLAUDE.md (works with Claude Code / Claude)
append_guidelines "$ROOT/CLAUDE.md"

# Also append to .cursorrules if it exists (Cursor users)
if [ -f "$ROOT/.cursorrules" ]; then
  append_guidelines "$ROOT/.cursorrules"
fi

# --- REPORTS/README.md and RUNS/README.md (only if missing) ---

for dir in REPORTS RUNS; do
  if [ ! -f "$ROOT/$dir/README.md" ]; then
    echo "# $dir" > "$ROOT/$dir/README.md"
    echo "[+] $dir/README.md created"
  fi
done

# --- .gitkeep for empty dirs ---

touch "$ROOT/ARTIFACTS/plots/.gitkeep"

echo ""
echo "=== Done ==="
echo ""
echo "Next:"
echo "  1. Edit STATE.md — replace seed beliefs and frontier with your own"
echo "  2. ./scripts/new_run.sh \"your delta\" — create first run manually"
echo "  3. ./scripts/supervisor.sh 3 — or let the supervisor run 3 cycles"
echo ""
echo "Files created/checked:"
echo "  STATE.md        — beliefs, ledger, frontier, policy"
echo "  DASHBOARD.md    — auto-generated summary"
echo "  CLAUDE.md       — agent guidelines"
echo "  REPORTS/        — run reports go here"
echo "  RUNS/           — run plans + artifacts go here"
echo "  ARTIFACTS/plots — generated visualizations"
