#!/usr/bin/env python3
"""Bounded SLURM monitoring. Markers never override scheduler failure.

0: scheduler success plus DONE/SMOKE_DONE; 1: job failure/BLOCKER;
2: completed job without a success marker; 3: monitoring timeout;
4: scheduler/accounting could not establish state. Never cancels a job.
"""
import argparse
import math
import subprocess
import time
from pathlib import Path


class SchedulerUnavailable(Exception):
    pass


def query(command, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError
    try:
        result = subprocess.run(command, text=True, capture_output=True,
                                timeout=min(10, remaining))
    except subprocess.TimeoutExpired as exc:
        if time.monotonic() >= deadline:
            raise TimeoutError from exc
        raise SchedulerUnavailable('scheduler command timed out') from exc
    except OSError as exc:
        raise SchedulerUnavailable(str(exc)) from exc
    if result.returncode:
        raise SchedulerUnavailable(result.stderr.strip() or 'scheduler query failed')
    return result.stdout


def scheduler_state(job_id, deadline):
    queue = query(['squeue', '-h', '-j', job_id, '-o', '%i|%T'], deadline)
    if queue.strip():
        return 'active'
    accounting = query(['sacct', '-X', '-n', '-P', '-j', job_id,
                        '-o', 'JobIDRaw,State,ExitCode'], deadline)
    for line in accounting.splitlines():
        fields = line.split('|')
        if len(fields) < 3 or fields[0].strip() != job_id:
            continue
        if not fields[1].strip() or not fields[2].strip():
            raise SchedulerUnavailable('incomplete accounting row')
        state, code = fields[1].strip().split()[0].rstrip('+'), fields[2].strip()
        if state == 'COMPLETED':
            return 'success' if code == '0:0' else 'failed'
        if state in {'FAILED', 'CANCELLED', 'TIMEOUT', 'OUT_OF_MEMORY',
                     'NODE_FAIL', 'PREEMPTED', 'BOOT_FAIL', 'DEADLINE', 'REVOKED'}:
            return 'failed'
        return 'active'
    raise SchedulerUnavailable('job absent from queue; accounting not available yet')


def monitor(job_id, output, timeout=10800, poll_interval=5, grace=30):
    deadline = time.monotonic() + timeout
    offset = 0
    pending = ''
    success = smoke = blocker = False
    uncertain_since = completed_since = None
    next_query = 0
    state = 'unknown'
    while True:
        now = time.monotonic()
        if now >= deadline:
            print('[WAIT] TIMEOUT: monitoring ended; job may still be running', flush=True)
            return 3
        # Bound reading so chatty output cannot starve the deadline or scheduler.
        try:
            with Path(output).open('r', errors='replace') as stream:
                if Path(output).stat().st_size < offset:
                    raise ValueError('output truncated; use a unique path per attempt')
                stream.seek(offset)
                chunk = stream.read(65536)
                offset = stream.tell()
        except FileNotFoundError:
            chunk = ''
        pending += chunk
        lines = pending.split('\n')
        pending = lines.pop()
        for line in lines:
            if '[DELTA-' in line:
                print(line, flush=True)
            blocker |= '[DELTA-BLOCKER]' in line
            smoke |= '[DELTA-SMOKE-DONE]' in line
            success |= '[DELTA-DONE]' in line or smoke
        if blocker:
            print('[WAIT] BLOCKER: reconcile job state before retrying', flush=True)
            return 1
        if now >= next_query:
            next_query = now + poll_interval
            try:
                state = scheduler_state(job_id, deadline)
                uncertain_since = None
            except TimeoutError:
                return 3
            except SchedulerUnavailable as exc:
                uncertain_since = uncertain_since if uncertain_since is not None else now
                if now - uncertain_since >= grace:
                    print(f'[WAIT] UNKNOWN: {exc}; do not resubmit blindly', flush=True)
                    return 4
                state = 'unknown'
        if time.monotonic() >= deadline:
            return 3
        if state == 'failed':
            print('[WAIT] FAILED: scheduler reports job failure', flush=True)
            return 1
        if state == 'success':
            completed_since = completed_since if completed_since is not None else now
            # Drain all final output before accepting a success marker.
            if len(chunk) < 65536 and not pending and success:
                print('[WAIT] SMOKE_DONE' if smoke else '[WAIT] DONE', flush=True)
                return 0
            if len(chunk) < 65536 and now - completed_since >= grace:
                print('[WAIT] MISSING_MARKER: completed without full success record', flush=True)
                return 2
        if len(chunk) == 65536:
            continue  # Drain backlog without sleeping or flooding SLURM queries.
        time.sleep(max(0, min(poll_interval, deadline - time.monotonic())))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('job_id')
    parser.add_argument('output', type=Path)
    parser.add_argument('timeout', nargs='?', type=float, default=10800)
    parser.add_argument('--poll-interval', type=float, default=5)
    parser.add_argument('--grace', type=float, default=30)
    args = parser.parse_args()
    if not all(math.isfinite(v) for v in (args.timeout, args.poll_interval, args.grace)) \
            or args.timeout <= 0 or args.poll_interval <= 0 or args.grace < 0:
        parser.error('timeout and poll interval must be positive; grace must be nonnegative')
    if not args.job_id or any(c not in '0123456789_+.' for c in args.job_id):
        parser.error('expected a numeric SLURM job ID (or array task ID)')
    return monitor(args.job_id, args.output, args.timeout, args.poll_interval, args.grace)


if __name__ == '__main__':
    raise SystemExit(main())
