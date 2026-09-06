#!/usr/bin/env python3
"""Run one attempt with a deadline, durable process status and preserved logs."""
import argparse
import math
import os
import signal
import subprocess
import time
from pathlib import Path

from experiment_logger import atomic_json


def stop(process):
    """Terminate the owned process group, including surviving child processes."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=0.2)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def run(command, log_path, status_path, timeout):
    log_path, status_path = Path(log_path), Path(status_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    # Reserve the attempt before spawning; existing attempts must be reconciled.
    with status_path.open('x') as stream:
        stream.write('{"status": "launching"}\n')
    status = {'status': 'launching', 'command': command, 'started': time.time(),
              'timeout_seconds': timeout}
    process = None
    start = time.monotonic()
    try:
        with log_path.open('x') as log:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                       start_new_session=True)
            status.update(status='running', pid=process.pid)
            atomic_json(status_path, status)
            print(f'[EXEC] pid={process.pid} status={status_path}', flush=True)
            try:
                code = process.wait(timeout=timeout)
                status['status'] = 'completed' if code == 0 else 'failed'
            except (subprocess.TimeoutExpired, KeyboardInterrupt):
                stop(process)
                code = 124
                status['status'] = 'interrupted_or_timed_out'
            status['returncode'] = code
    except OSError as exc:
        if process is not None:
            stop(process)  # A logging/status failure must not leave a live attempt behind.
        status.update(status='failed', error=str(exc), returncode=1)
        code = 1
    finally:
        status['elapsed_seconds'] = time.monotonic() - start
        atomic_json(status_path, status)
    return code if code >= 0 else 128 - code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--log', type=Path, required=True)
    parser.add_argument('--status', type=Path, required=True)
    parser.add_argument('--timeout', type=float, required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command or not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error('a command and a positive timeout are required')
    return run(command, args.log, args.status, args.timeout)


if __name__ == '__main__':
    raise SystemExit(main())
