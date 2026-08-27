#!/usr/bin/env bash
# wait_for_job.sh — Block until a SLURM job completes, streaming DELTA markers.
#
# Usage: scripts/wait_for_job.sh <SLURM_JOB_ID> <OUTPUT_FILE> [TIMEOUT_SECONDS]
#
# Exit codes:
#   0 — DELTA-SMOKE-DONE or DELTA-DONE received (stage completed successfully)
#   1 — DELTA-BLOCKER received (unrecoverable failure)
#   2 — Job vanished from squeue without a success marker
#   3 — Timeout reached
#
# Note: DELTA-ERROR is recoverable — printed but does not terminate monitoring.
#
# Both Claude Code and Codex can run this as a blocking bash command.
# The script tails the SLURM output file and filters for [DELTA-*] lines,
# so the agent only processes meaningful events (not raw training output).

set -euo pipefail

# ---------------------------------------------------------------------------
# Args
# ---------------------------------------------------------------------------
if [[ $# -lt 2 ]]; then
    echo "Usage: scripts/wait_for_job.sh <SLURM_JOB_ID> <OUTPUT_FILE> [TIMEOUT_SECONDS]"
    echo ""
    echo "Blocks until the SLURM job finishes, streaming DELTA markers to stdout."
    echo "Default timeout: 10800 seconds (3 hours)."
    exit 0
fi

JOB_ID="$1"
OUTPUT_FILE="$2"
TIMEOUT="${3:-10800}"

START_TIME=$(date +%s)
TAIL_PID=""
FIFO=""

cleanup() {
    if [[ -n "$TAIL_PID" ]]; then
        kill "$TAIL_PID" 2>/dev/null || true
        wait "$TAIL_PID" 2>/dev/null || true
    fi
    [[ -n "$FIFO" && -p "$FIFO" ]] && rm -f "$FIFO"
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Phase 1: Wait for output file to appear
# ---------------------------------------------------------------------------
echo "[WAIT] Watching job ${JOB_ID} — waiting for ${OUTPUT_FILE}..."

while [[ ! -f "$OUTPUT_FILE" ]]; do
    sleep 2

    NOW=$(date +%s)
    if [[ $((NOW - START_TIME)) -ge $TIMEOUT ]]; then
        echo "[WAIT] Job ${JOB_ID} finished | status=TIMEOUT (output file never appeared)"
        exit 3
    fi

    if ! squeue -j "$JOB_ID" -h 2>/dev/null | grep -q "$JOB_ID"; then
        sleep 5  # Let SLURM flush
        [[ -f "$OUTPUT_FILE" ]] && break
        echo "[WAIT] Job ${JOB_ID} finished | status=VANISHED (no output file)"
        exit 2
    fi
done

echo "[WAIT] Output file appeared — streaming DELTA markers..."

# ---------------------------------------------------------------------------
# Phase 2: Tail output and filter for DELTA markers
# ---------------------------------------------------------------------------
# Use a FIFO so tail runs in the background with a known PID we can clean up.

FIFO=$(mktemp -u /tmp/delta-wait-XXXXXX.fifo)
mkfifo "$FIFO"

tail -n +1 -f "$OUTPUT_FILE" > "$FIFO" 2>/dev/null &
TAIL_PID=$!

# Open FIFO on fd 3 — keeps it open for the entire loop
exec 3< "$FIFO"

FINAL_STATUS=""

while true; do
    # Read with 30s timeout — if no output for 30s, run safety checks
    if IFS= read -r -t 30 LINE <&3; then
        # Got a line — check if it's a DELTA marker
        if [[ "$LINE" == *"[DELTA-"* ]]; then
            echo "$LINE"

            if [[ "$LINE" == *"[DELTA-SMOKE-DONE]"* ]]; then
                FINAL_STATUS="SMOKE_DONE"
                break
            elif [[ "$LINE" == *"[DELTA-DONE]"* ]]; then
                FINAL_STATUS="DONE"
                break
            elif [[ "$LINE" == *"[DELTA-BLOCKER]"* ]]; then
                FINAL_STATUS="BLOCKER"
                break
            fi
            # [DELTA-ERROR] is recoverable — printed but does not terminate monitoring
        fi
    else
        # Read timed out — safety checks

        # Timeout check
        NOW=$(date +%s)
        if [[ $((NOW - START_TIME)) -ge $TIMEOUT ]]; then
            FINAL_STATUS="TIMEOUT"
            break
        fi

        # squeue check — is the job still running?
        if ! squeue -j "$JOB_ID" -h 2>/dev/null | grep -q "$JOB_ID"; then
            sleep 2  # Let buffered output flush

            # Scan the full output file for terminal markers
            if grep -q '\[DELTA-BLOCKER\]' "$OUTPUT_FILE" 2>/dev/null; then
                FINAL_STATUS="BLOCKER"
            elif grep -q '\[DELTA-SMOKE-DONE\]' "$OUTPUT_FILE" 2>/dev/null; then
                FINAL_STATUS="SMOKE_DONE"
            elif grep -q '\[DELTA-DONE\]' "$OUTPUT_FILE" 2>/dev/null; then
                FINAL_STATUS="DONE"
            else
                FINAL_STATUS="VANISHED"
            fi
            break
        fi

        # Job still running, no timeout — continue waiting
    fi
done

# Close the FIFO fd
exec 3<&-

# ---------------------------------------------------------------------------
# Phase 3: Report result
# ---------------------------------------------------------------------------
case "${FINAL_STATUS:-UNKNOWN}" in
    SMOKE_DONE)
        echo "[WAIT] Job ${JOB_ID} finished | status=SMOKE_DONE"
        exit 0
        ;;
    DONE)
        echo "[WAIT] Job ${JOB_ID} finished | status=DONE"
        exit 0
        ;;
    BLOCKER)
        echo "[WAIT] Job ${JOB_ID} finished | status=BLOCKER"
        exit 1
        ;;
    VANISHED)
        echo "[WAIT] Job ${JOB_ID} finished | status=VANISHED (job left squeue without a success marker)"
        exit 2
        ;;
    TIMEOUT)
        echo "[WAIT] Job ${JOB_ID} finished | status=TIMEOUT (exceeded ${TIMEOUT}s)"
        exit 3
        ;;
    *)
        echo "[WAIT] Job ${JOB_ID} finished | status=UNKNOWN"
        exit 2
        ;;
esac
