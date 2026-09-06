#!/usr/bin/env bash
# Compatibility entry point. Success requires SLURM completion and DELTA-DONE
# or DELTA-SMOKE-DONE (SMOKE_DONE), not just a marker. See wait_for_job.py.
set -euo pipefail
exec python3 "$(dirname "$0")/wait_for_job.py" "$@"
