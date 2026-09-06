"""Fresh evaluation workspaces and observable, fail-closed CLI invocation."""
import hashlib
import json
import os
import signal
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

INPUTS = {
    'initialization': ['SYSTEM_PROFILE.md'],
    'plan_generation': ['STATE.md'],
    'worker_execution': ['PLAN.md'],
    'state_compression': ['STATE_before.md', 'REPORT.md'],
    'slurm_job_generation': ['PLAN.md', 'INFRA.md'],
}
OUTPUTS = {
    'initialization': ['output_INFRA.md'],
    'plan_generation': ['output_PLAN.md'],
    'worker_execution': ['output_REPORT.md'],
    'state_compression': ['output_STATE_after.md'],
    'slurm_job_generation': ['output_experiment.py', 'output_smoke_job.sh', 'output_job.sh'],
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare_workspace(root, destination=None, review_only=False):
    if destination:
        workspace = Path(destination).resolve()
        workspace.mkdir(parents=True, exist_ok=False)
    else:
        parent = root / 'tests' / 'evaluations'
        parent.mkdir(exist_ok=True)
        workspace = Path(tempfile.mkdtemp(prefix='eval-', dir=parent))
    framework = workspace / 'delta-research'
    shutil.copytree(root / 'templates', framework / 'templates')
    shutil.copytree(root / 'scripts', framework / 'scripts',
                    ignore=shutil.ignore_patterns('__pycache__'))
    for case, names in INPUTS.items():
        target = workspace / 'tests' / case
        target.mkdir(parents=True)
        for name in names + (OUTPUTS[case] if review_only else []):
            source = root / 'tests' / case / name
            if source.exists():
                shutil.copy2(source, target / name)
        if review_only and (root / 'tests' / case / 'artifacts').exists():
            shutil.copytree(root / 'tests' / case / 'artifacts', target / 'artifacts')
    (workspace / 'AGENTS.md').write_text(
        'This is an isolated fixture evaluation. Perform only the assigned stage.\n'
        'Do not run the supervisor loop, schedule work, commit, push, or spawn agents.\n'
        'Read the copied framework and supplied inputs; do not seek golden outputs.\n'
        'Keep generated files inside the assigned output directory.\n')
    return workspace


def command_for(agent, model, effort, workspace):
    if agent == 'codex':
        return ['codex', 'exec', '--approve-for-me', '--skip-git-repo-check',
                '--cd', str(workspace), '--model', model,
                '-c', f'model_reasoning_effort="{effort}"',
                '-c', 'agents.enabled=false', '--json', '-']
    if agent == 'claude':
        return ['claude', '-p', '--model', model, '--allowedTools', 'Read,Write,Bash,Edit']
    raise ValueError(f'Unknown agent: {agent}')


def terminate_group(process):
    if os.name == 'posix':
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=0.2)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    else:
        process.kill()


def execute(agent, model, effort, workspace, prompt, outputs, label, timeout):
    """Returns a result even on failure; caller must include ok in its exit status."""
    logs = workspace / 'evaluation_logs'
    logs.mkdir(exist_ok=True)
    if any(path.exists() for path in outputs):
        return {'ok': False, 'error': 'refusing pre-existing generated output', 'label': label}
    command = command_for(agent, model, effort, workspace)
    # Freeze all pre-existing inputs, templates and previously accepted artifacts.
    protected = {p: digest(p) for p in workspace.rglob('*')
                 if p.is_file() and 'evaluation_logs' not in p.parts}
    (logs / f'{label}.prompt.txt').write_text(prompt)
    result = {'label': label, 'model': model, 'effort': effort, 'agent': agent,
              'command': command, 'ok': False, 'usage': [], 'outputs': {}}
    try:
        result['cli_version'] = subprocess.run(
            [agent, '--version'], capture_output=True, text=True, timeout=10
        ).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        result['cli_version'] = None
    start = time.monotonic()
    with (logs / f'{label}.stdout.jsonl').open('w') as stdout, \
            (logs / f'{label}.stderr.log').open('w') as stderr:
        try:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=stdout,
                                       stderr=stderr, text=True, cwd=workspace,
                                       start_new_session=(os.name == 'posix'))
            try:
                process.communicate(prompt, timeout=timeout)
                result['returncode'] = process.returncode
                if process.returncode:
                    result['error'] = f'agent exited with code {process.returncode}'
            except subprocess.TimeoutExpired:
                terminate_group(process)
                process.communicate()
                result['error'] = f'agent timed out after {timeout}s'
                result['returncode'] = process.returncode
        except OSError as exc:
            result['error'] = str(exc)
    result['elapsed_seconds'] = time.monotonic() - start
    changed = [str(p.relative_to(workspace)) for p, sha in protected.items()
               if not p.is_file() or digest(p) != sha]
    if changed:
        result['error'] = 'agent modified protected inputs: ' + ', '.join(changed)
    if not all(p.is_file() and p.stat().st_size for p in outputs):
        result.setdefault('error', 'required output missing or empty')
    for path in outputs:
        if path.is_file():
            result['outputs'][str(path.relative_to(workspace))] = digest(path)
    for line in (logs / f'{label}.stdout.jsonl').read_text().splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get('usage'):
            result['usage'].append(event['usage'])
        if isinstance(event, dict) and event.get('type') == 'turn.failed':
            result['error'] = 'agent reported turn.failed: ' + str(event.get('error', ''))
    result['ok'] = 'error' not in result
    (logs / f'{label}.result.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def review_verdict(path):
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return False, f'invalid review verdict: {exc}'
    if not isinstance(value, dict) or type(value.get('passed')) is not bool \
            or not isinstance(value.get('issues'), list) \
            or not all(isinstance(v, str) for v in value['issues']):
        return False, 'review must contain passed:boolean and issues:string[]'
    return value['passed'] and not value['issues'], '; '.join(value['issues'])
