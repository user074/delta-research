#!/usr/bin/env python3
"""Atomic operational journal; never writes scientific STATE.md or submits jobs.

One durable owner per project, one pending run, one record per execution attempt.
Use --root PROJECT and --owner a stable task/session ID on every mutation.
"""
import argparse
import fcntl
import json
import math
import re
import subprocess
import time
from pathlib import Path

from experiment_logger import atomic_json

PHASES = ['planned', 'running', 'reported', 'compressed', 'committed', 'published']


def ledger_runs(root):
    path = root / 'STATE.md'
    if not path.exists():
        return []
    text = path.read_text()
    match = re.search(r'^## Ledger\s*\n(.*?)(?=^## |\Z)', text, re.M | re.S)
    return re.findall(r'^\|\s*(R\d+)\s*\|', match[1], re.M) if match else []


def git(root, *args):
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True,
                            text=True, timeout=30)
    if result.returncode:
        raise ValueError(result.stderr.strip() or 'Git verification failed')
    return result.stdout.strip()


def next_action(root, record):
    if not record:
        return 'select'
    run = record['run_id']
    if record['phase'] == 'published':
        return 'check_interrupts'
    if any(a['status'] in ('launching', 'running') for a in record['attempts'].values()):
        return 'reconcile_existing_jobs'
    if run in ledger_runs(root):
        return 'publish_existing_result'
    if (root / 'REPORTS' / f'{run}.md').exists():
        return 'ingest_existing_report'
    return 'resume_same_plan'


def update(root, owner, action, **values):
    root = Path(root).resolve()
    directory = root / '.delta-runtime'
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'journal.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = directory / 'journal.json'
        data = json.loads(path.read_text()) if path.exists() else {
            'version': 1, 'owner': None, 'deadline': None, 'active': None, 'completed': []}
        active = data['active']
        if action == 'status':
            return {**data, 'next_action': next_action(root, active),
                    'budget_expired': data['deadline'] is not None and time.time() >= data['deadline']}
        if not owner:
            raise ValueError('a stable --owner task/session ID is required')
        if action == 'claim':
            if data['owner'] not in (None, owner):
                raise ValueError(f"project already owned by {data['owner']}")
            data['owner'] = owner
        else:
            if data['owner'] != owner:
                raise ValueError('owner mismatch; claim the project before mutating its journal')
            if action == 'release':
                data['owner'] = None
            elif action == 'budget':
                if not math.isfinite(values['deadline']) or values['deadline'] <= time.time():
                    raise ValueError('deadline must be a future Unix timestamp')
                data['deadline'] = values['deadline']
            elif action == 'note':
                data.setdefault('notes', []).append({'time': time.time(), 'text': values['text']})
            elif action == 'begin':
                run = values['run_id']
                if not re.fullmatch(r'R\d{3,}', run):
                    raise ValueError('run ID must be R followed by at least three digits')
                if active:
                    if active['run_id'] != run:
                        raise ValueError('finish or resume the existing run before allocating another ID')
                    return data  # Idempotent; never resets attempts or the deadline.
                if data['deadline'] is None or time.time() >= data['deadline']:
                    raise ValueError('set an authorized budget before beginning a run')
                ledger = ledger_runs(root)
                next_id = max([int(r[1:]) for r in ledger + data['completed']], default=0) + 1
                if int(run[1:]) != next_id:
                    # A compressed run may need adoption after upgrading the framework.
                    if not (values.get('adopt') and ledger.count(run) == 1):
                        raise ValueError(f'expected R{next_id:03d}; use --adopt only to recover existing work')
                # Legacy pending work must be reconciled before starting a new ID.
                pending = [p.parent.name for p in (root / 'RUNS').glob('R*/PLAN.md')
                           if p.parent.name not in ledger and p.parent.name != run]
                if pending:
                    raise ValueError(f'other pending plans require reconciliation: {pending}')
                data['active'] = {'run_id': run, 'phase': 'planned', 'attempts': {},
                                  'pre_head': values.get('pre_head'), 'commit': None,
                                  'started': time.time()}
            elif action == 'archive':
                if not active or active['phase'] != 'published':
                    raise ValueError('only a verified published run may be archived')
                atomic_json(directory / f"{active['run_id']}.json", active)
                data['completed'].append(active['run_id'])
                data['active'] = None
            else:
                if not active:
                    raise ValueError('no pending run')
                if action == 'reserve':
                    if active['phase'] not in ('planned', 'running'):
                        raise ValueError('evidence already reported; do not launch more jobs')
                    if active['run_id'] in ledger_runs(root) or \
                            (root / 'REPORTS' / f"{active['run_id']}.md").exists():
                        raise ValueError('saved result requires reconciliation; do not launch more jobs')
                    if data['deadline'] is None or time.time() >= data['deadline']:
                        raise ValueError('budget expired; no new attempt may launch')
                    attempt_id = values['attempt']
                    if not re.fullmatch(r'[A-Za-z0-9_-]+', attempt_id):
                        raise ValueError('invalid attempt ID')
                    if attempt_id in active['attempts']:
                        raise ValueError('attempt already exists; reconcile it before using a new attempt ID')
                    condition = values['condition']
                    if any(a['condition'] == condition and a['status'] in ('launching', 'running', 'completed')
                           for a in active['attempts'].values()):
                        raise ValueError('condition already pending or completed')
                    active['attempts'][attempt_id] = {
                        'condition': condition, 'status': 'launching', 'job_id': None,
                        'pid': None, 'command': values['command'], 'created': time.time()}
                    active['phase'] = 'running'
                elif action == 'attach':
                    attempt = active['attempts'][values['attempt']]
                    if attempt['status'] not in ('launching', 'running'):
                        raise ValueError('attempt is already terminal')
                    for key in ('job_id', 'pid'):
                        value = values.get(key)
                        if value is not None:
                            if attempt[key] not in (None, value):
                                raise ValueError('cannot replace an attached job/process ID')
                            attempt[key] = value
                    if not attempt['job_id'] and not attempt['pid']:
                        raise ValueError('supply --job-id or --pid')
                    attempt['status'] = 'running'
                elif action == 'finish':
                    attempt = active['attempts'][values['attempt']]
                    status = values['status']
                    if attempt['status'] in ('completed', 'failed') and attempt['status'] != status:
                        raise ValueError('cannot rewrite a terminal attempt')
                    attempt.update(status=status, evidence=values['evidence'])
                elif action == 'phase':
                    phase = values['phase']
                    if PHASES.index(phase) < PHASES.index(active['phase']):
                        raise ValueError('phase cannot move backwards')
                    run = active['run_id']
                    if PHASES.index(phase) >= PHASES.index('reported'):
                        if any(a['status'] in ('launching', 'running') for a in active['attempts'].values()):
                            raise ValueError('reconcile pending attempts before reporting')
                        if not (root / 'REPORTS' / f'{run}.md').is_file():
                            raise ValueError('report is missing')
                    if PHASES.index(phase) >= PHASES.index('compressed') and ledger_runs(root).count(run) != 1:
                        raise ValueError('compression requires exactly one ledger row for this run')
                    if phase in ('committed', 'published'):
                        commit = values.get('commit') or active['commit']
                        if not commit:
                            raise ValueError('commit hash is required')
                        commit = git(root, 'rev-parse', '--verify', f'{commit}^{{commit}}')
                        if commit == active['pre_head']:
                            raise ValueError('the pre-run commit cannot publish this run')
                        for name in ('STATE.md', f'REPORTS/{run}.md', f'RUNS/{run}/PLAN.md'):
                            content = git(root, 'show', f'{commit}:{name}')
                            if content != (root / name).read_text().strip():
                                raise ValueError(f'commit does not contain current {name}')
                        if phase == 'published':
                            remote = values.get('remote')
                            branch = values.get('branch')
                            if not remote or not branch:
                                raise ValueError('publication requires --remote and --branch')
                            remote_tip = git(root, 'ls-remote', '--exit-code', remote, f'refs/heads/{branch}')
                            if not remote_tip or remote_tip.split()[0] != commit:
                                raise ValueError('remote branch does not match the run commit')
                        active['commit'] = commit
                    active['phase'] = phase
                else:
                    raise ValueError(f'unknown action: {action}')
        atomic_json(path, data)
        return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--owner')
    subs = parser.add_subparsers(dest='action', required=True)
    for name in ('claim', 'release', 'status', 'archive'):
        subs.add_parser(name)
    subs.add_parser('budget').add_argument('--deadline', type=float, required=True)
    subs.add_parser('note').add_argument('--text', required=True)
    begin = subs.add_parser('begin')
    begin.add_argument('--run-id', required=True)
    begin.add_argument('--pre-head')
    begin.add_argument('--adopt', action='store_true')
    reserve = subs.add_parser('reserve')
    reserve.add_argument('--attempt', required=True)
    reserve.add_argument('--condition', required=True)
    reserve.add_argument('--command', required=True)
    attach = subs.add_parser('attach')
    attach.add_argument('--attempt', required=True)
    attach.add_argument('--job-id')
    attach.add_argument('--pid', type=int)
    finish = subs.add_parser('finish')
    finish.add_argument('--attempt', required=True)
    finish.add_argument('--status', choices=['completed', 'failed'], required=True)
    finish.add_argument('--evidence', required=True)
    phase = subs.add_parser('phase')
    phase.add_argument('phase', choices=PHASES)
    phase.add_argument('--commit')
    phase.add_argument('--remote')
    phase.add_argument('--branch')
    args = vars(parser.parse_args())
    try:
        data = update(**args)
        if args['action'] == 'status':
            result = data
        else:
            # Do not replay every old attempt and command after each mutation.
            active = data['active'] or {}
            result = {'action': args['action'], 'owner': data['owner'],
                      'deadline': data['deadline'], 'run_id': active.get('run_id'),
                      'phase': active.get('phase')}
            if args.get('attempt'):
                result['attempt'] = args['attempt']
                result['attempt_status'] = active['attempts'][args['attempt']]['status']
        print(json.dumps(result, indent=2))
    except (ValueError, KeyError, OSError, subprocess.TimeoutExpired) as exc:
        parser.exit(2, f'{exc}\n')


if __name__ == '__main__':
    main()
