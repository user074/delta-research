"""Behavioral regressions. No live models, GPU jobs or network services."""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))
from experiment_logger import ExperimentLogger
from loop_runtime import update, next_action
from wait_for_job import monitor, scheduler_state, SchedulerUnavailable
from run_command import run
from agent_harness import execute, prepare_workspace, command_for, review_verdict


class TempCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)


class LoggerTests(TempCase):
    def test_append_close_and_results(self):
        for step in (1, 2):
            log = ExperimentLogger(self.root)
            log.log_step(step=step, loss=0.5)
            log.log_results({'samples': step})
            log.close()
            log.close()
            self.assertFalse(hasattr(log, 'history'))
        rows = [json.loads(s) for s in (self.root / 'metrics/history.jsonl').read_text().splitlines()]
        self.assertEqual([r['step'] for r in rows], [1, 2])
        self.assertTrue(all('timestamp' in r for r in rows))
        self.assertEqual(json.loads((self.root / 'metrics/results.json').read_text()), {'samples': 2})

    def test_cleanup_does_not_mask_experiment_error(self):
        log = ExperimentLogger(self.root)
        with self.assertRaisesRegex(ValueError, 'measurement failed'):
            with patch.object(log, 'close', side_effect=OSError('disk failed')):
                with log:
                    raise ValueError('measurement failed')
        log.close()


class MonitorTests(TempCase):
    def watch(self, content, state='success', timeout=0.08, grace=0):
        output = self.root / 'job.out'
        output.write_text(content)
        with patch('wait_for_job.scheduler_state', return_value=state), contextlib.redirect_stdout(io.StringIO()):
            return monitor('123', output, timeout, 0.01, grace)

    def test_completed_smoke_and_full_job(self):
        for marker in ('DELTA-SMOKE-DONE', 'DELTA-DONE'):
            self.assertEqual(self.watch(f'[{marker}] R001\n'), 0)

    def test_later_failure_overrides_done(self):
        self.assertEqual(self.watch('[DELTA-DONE] R001\n[DELTA-BLOCKER] rank failed\n'), 1)

    def test_scheduler_failure_overrides_done(self):
        self.assertEqual(self.watch('[DELTA-DONE] R001\n', state='failed'), 1)

    def test_success_marker_while_running_is_not_success(self):
        self.assertEqual(self.watch('[DELTA-DONE] R001\n', state='active'), 3)

    def test_missing_marker(self):
        self.assertEqual(self.watch('ended\n'), 2)

    def test_accounting_error_is_unknown(self):
        output = self.root / 'job.out'
        output.write_text('[DELTA-DONE]\n')
        with patch('wait_for_job.scheduler_state', side_effect=SchedulerUnavailable('offline')), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(monitor('123', output, 1, .01, 0), 4)

    def test_chatty_output_cannot_extend_deadline(self):
        output = self.root / 'chatty.out'
        output.touch()
        stop = threading.Event()
        def produce():
            with output.open('a') as stream:
                while not stop.wait(.005):
                    stream.write('training step\n')
                    stream.flush()
        producer = threading.Thread(target=produce)
        producer.start()
        start = time.monotonic()
        try:
            with patch('wait_for_job.scheduler_state', return_value='active'), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(monitor('123', output, .12, .01, 0), 3)
        finally:
            stop.set()
            producer.join()
        self.assertLess(time.monotonic() - start, .7)

    def test_failure_after_large_backlog(self):
        self.assertEqual(self.watch('[DELTA-DONE]\n' + ('training\n' * 18000) + '[DELTA-BLOCKER]\n', timeout=1, grace=1), 1)

    def test_exact_accounting_row(self):
        with patch('wait_for_job.query', side_effect=['', '123.batch|COMPLETED|0:0\n123|FAILED|1:0\n']):
            self.assertEqual(scheduler_state('123', time.monotonic() + 1), 'failed')


class DirectTests(TempCase):
    def test_status_write_failure_stops_spawned_process(self):
        from experiment_logger import atomic_json
        launched = []
        real_popen = subprocess.Popen
        def spawn(*args, **kwargs):
            process = real_popen(*args, **kwargs)
            launched.append(process)
            return process
        def write_status(path, value):
            if value.get('status') == 'running':
                raise OSError('status disk failure')
            atomic_json(path, value)
        with patch('run_command.subprocess.Popen', side_effect=spawn), \
                patch('run_command.atomic_json', side_effect=write_status):
            code = run([sys.executable, '-c', 'import time; time.sleep(10)'],
                       self.root / 'out.log', self.root / 'status.json', 3)
        self.assertEqual(code, 1)
        self.assertIsNotNone(launched[0].poll())
        self.assertEqual(json.loads((self.root / 'status.json').read_text())['status'], 'failed')

    def test_nonzero_exit_survives_logging(self):
        with contextlib.redirect_stdout(io.StringIO()):
            code = run([sys.executable, '-c', 'raise RuntimeError("failure")'],
                       self.root / 'out.log', self.root / 'status.json', 3)
        self.assertEqual(code, 1)
        self.assertEqual(json.loads((self.root / 'status.json').read_text())['returncode'], 1)
        self.assertIn('RuntimeError', (self.root / 'out.log').read_text())

    def test_timeout_and_attempt_reuse(self):
        with contextlib.redirect_stdout(io.StringIO()):
            code = run([sys.executable, '-c', 'import time; time.sleep(10)'],
                       self.root / 'out.log', self.root / 'status.json', .05)
        self.assertEqual(code, 124)
        with self.assertRaises(FileExistsError):
            run(['true'], self.root / 'other.log', self.root / 'status.json', 1)


class RuntimeTests(TempCase):
    def setUp(self):
        super().setUp()
        update(self.root, 'task-1', 'claim')
        self.deadline = time.time() + 60
        update(self.root, 'task-1', 'budget', deadline=self.deadline)

    def call(self, action, **values):
        return update(self.root, 'task-1', action, **values)

    def plan(self):
        path = self.root / 'RUNS/R001/PLAN.md'
        path.parent.mkdir(parents=True)
        path.write_text('baseline + treatment\n')
        self.call('begin', run_id='R001')

    def compress_files(self):
        (self.root / 'REPORTS').mkdir(exist_ok=True)
        (self.root / 'REPORTS/R001.md').write_text('Result supports the measured claim.\n')
        (self.root / 'STATE.md').write_text('## Ledger\n| Run | Result |\n| R001 | measured |\n\n## Frontier\n')

    def test_second_supervisor_rejected_and_same_owner_resumes(self):
        with self.assertRaisesRegex(ValueError, 'already owned'):
            update(self.root, 'task-2', 'claim')
        self.plan()
        self.call('begin', run_id='R001')
        self.assertEqual(self.call('status')['deadline'], self.deadline)
        with self.assertRaisesRegex(ValueError, 'existing run'):
            self.call('begin', run_id='R002')

    def test_cli_mutation_does_not_replay_attempt_history(self):
        self.plan()
        command = [sys.executable, str(ROOT / 'scripts/loop_runtime.py'),
                   '--root', str(self.root), '--owner', 'task-1', 'reserve',
                   '--attempt', 'A001', '--condition', 'baseline', '--command', 'long command body']
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        reply = json.loads(result.stdout)
        self.assertEqual(reply['attempt_status'], 'launching')
        self.assertNotIn('long command body', result.stdout)
        self.assertNotIn('attempts', reply)
        saved = self.call('status')['active']['attempts']['A001']
        self.assertEqual(saved['command'], 'long command body')

    def test_launch_gap_resumes_existing_attempt(self):
        self.plan()
        self.call('reserve', attempt='A001', condition='baseline', command='python experiment.py')
        self.assertEqual(self.call('status')['next_action'], 'reconcile_existing_jobs')
        with self.assertRaisesRegex(ValueError, 'pending or completed'):
            self.call('reserve', attempt='A002', condition='baseline', command='duplicate')
        self.call('attach', attempt='A001', job_id='123')
        self.assertEqual(self.call('status')['active']['attempts']['A001']['job_id'], '123')
        self.call('finish', attempt='A001', status='failed', evidence='sacct FAILED 1:0')
        self.call('reserve', attempt='A002', condition='baseline', command='repaired command')
        self.assertEqual(len(self.call('status')['active']['attempts']), 2)

    def test_completed_condition_cannot_be_repeated(self):
        self.plan()
        self.call('reserve', attempt='A001', condition='baseline', command='command')
        self.call('finish', attempt='A001', status='completed', evidence='exit 0')
        with self.assertRaisesRegex(ValueError, 'completed'):
            self.call('reserve', attempt='A002', condition='baseline', command='command')

    def test_resume_after_report_and_compression(self):
        self.plan()
        (self.root / 'REPORTS').mkdir()
        (self.root / 'REPORTS/R001.md').write_text('measurement')
        self.assertEqual(self.call('status')['next_action'], 'ingest_existing_report')
        with self.assertRaisesRegex(ValueError, 'saved result'):
            self.call('reserve', attempt='A001', condition='baseline', command='duplicate after crash')
        self.compress_files()
        self.assertEqual(self.call('status')['next_action'], 'publish_existing_result')
        with self.assertRaisesRegex(ValueError, 'saved result'):
            self.call('reserve', attempt='A001', condition='baseline', command='duplicate after crash')
        self.call('phase', phase='compressed')
        with self.assertRaises(ValueError):
            self.call('archive')

    def test_pending_job_reconciled_before_saved_result(self):
        self.plan()
        self.call('reserve', attempt='A001', condition='baseline', command='command')
        self.compress_files()
        self.assertEqual(self.call('status')['next_action'], 'reconcile_existing_jobs')
        with self.assertRaisesRegex(ValueError, 'pending attempts'):
            self.call('phase', phase='compressed')

    def test_deadline_survives_resume_and_blocks_launch(self):
        self.plan()
        with patch('loop_runtime.time.time', return_value=self.deadline + 1):
            self.assertTrue(self.call('status')['budget_expired'])
            with self.assertRaisesRegex(ValueError, 'budget expired'):
                self.call('reserve', attempt='A001', condition='baseline', command='late command')

    def test_duplicate_ledger_rejected(self):
        self.plan()
        self.compress_files()
        with (self.root / 'STATE.md').open('w') as stream:
            stream.write('## Ledger\n| R001 | measured |\n| R001 | duplicate |\n')
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            self.call('phase', phase='compressed')

    def test_publication_failure_preserves_result_and_retry(self):
        self.plan()
        self.compress_files()
        remote = self.root / 'remote.git'
        def git(*args):
            return subprocess.run(['git', '-C', str(self.root), '-c', 'user.name=Test',
                '-c', 'user.email=test@example.invalid', '-c', 'commit.gpgsign=false',
                '-c', f'core.hooksPath={self.root / "no-hooks"}', *args],
                capture_output=True, text=True, check=True).stdout.strip()
        git('init', '-q')
        git('checkout', '-b', 'codex/research')
        git('add', '--', 'STATE.md', 'REPORTS/R001.md', 'RUNS/R001/PLAN.md')
        git('commit', '-qm', 'research(R001): measured')
        commit = git('rev-parse', 'HEAD')
        subprocess.run(['git', 'init', '--bare', '-q', str(remote)], check=True)
        self.call('phase', phase='committed', commit=commit)
        with self.assertRaises(ValueError):
            self.call('phase', phase='published', commit=commit, remote=str(remote), branch='codex/research')
        self.assertEqual(self.call('status')['active']['phase'], 'committed')
        self.assertEqual(self.call('status')['next_action'], 'publish_existing_result')
        git('push', str(remote), 'HEAD:refs/heads/codex/research')
        self.call('phase', phase='published', commit=commit, remote=str(remote), branch='codex/research')
        self.assertEqual(self.call('status')['next_action'], 'check_interrupts')
        self.call('archive')
        self.assertEqual(self.call('status')['completed'], ['R001'])


class HarnessTests(TempCase):
    def fake_cli(self, body):
        directory = self.root / 'bin'
        directory.mkdir(exist_ok=True)
        cli = directory / 'codex'
        cli.write_text(f'#!{sys.executable}\nimport sys\nif "--version" in sys.argv:\n print("fake-cli 1")\n sys.exit(0)\n' + body)
        cli.chmod(0o755)
        return patch.dict(os.environ, PATH=str(directory) + os.pathsep + os.environ['PATH'])

    def test_no_golden_outputs_copied(self):
        workspace = prepare_workspace(ROOT, self.root / 'eval')
        self.assertTrue((workspace / 'tests/worker_execution/PLAN.md').exists())
        self.assertFalse((workspace / 'tests/worker_execution/output_REPORT.md').exists())
        self.assertFalse((workspace / 'tests/worker_execution/artifacts').exists())

    def test_cli_generation_failure_fails_process(self):
        with self.fake_cli('sys.exit(42)\n'):
            result = subprocess.run([sys.executable, str(ROOT / 'tests/run_tests.py'),
                '--run', '--agent', 'codex', '--test', 'plan', '--output-dir', str(self.root / 'eval')],
                capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('exited with code 42', result.stdout)
        self.assertNotIn('21/21 passed', result.stdout)

    def test_cli_review_failure_fails_process(self):
        with self.fake_cli('sys.exit(42)\n'):
            result = subprocess.run([sys.executable, str(ROOT / 'tests/run_tests.py'),
                '--review', '--agent', 'codex', '--test', 'plan', '--output-dir', str(self.root / 'eval')],
                capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('exited with code 42', result.stdout)

    def test_zero_exit_without_output_fails(self):
        workspace = prepare_workspace(ROOT, self.root / 'eval')
        with self.fake_cli('sys.stdin.read()\n'):
            result = execute('codex', 'gpt-5.6-sol', 'medium', workspace, 'prompt',
                             [workspace / 'result.md'], 'missing', 1)
        self.assertFalse(result['ok'])
        self.assertIn('missing', result['error'])

    def test_timeout_is_failure(self):
        workspace = prepare_workspace(ROOT, self.root / 'eval')
        with self.fake_cli('import time\ntime.sleep(10)\n'):
            result = execute('codex', 'gpt-5.6-sol', 'medium', workspace, 'prompt',
                             [workspace / 'result.md'], 'timeout', .05)
        self.assertFalse(result['ok'])
        self.assertIn('timed out', result['error'])

    def test_model_route_and_usage_manifest(self):
        workspace = prepare_workspace(ROOT, self.root / 'eval')
        body = ('from pathlib import Path\nsys.stdin.read()\nPath("result.md").write_text("fresh")\n'
                'print(\'{"type":"turn.completed","usage":{"input_tokens":12,"output_tokens":3}}\')\n')
        with self.fake_cli(body):
            result = execute('codex', 'gpt-5.6-sol', 'medium', workspace, 'prompt',
                             [workspace / 'result.md'], 'success', 1)
        self.assertTrue(result['ok'])
        self.assertEqual(result['usage'][0]['output_tokens'], 3)
        command = result['command']
        self.assertEqual(command[command.index('--model') + 1], 'gpt-5.6-sol')
        self.assertIn('model_reasoning_effort="medium"', command)

    def test_changed_input_is_failure(self):
        workspace = prepare_workspace(ROOT, self.root / 'eval')
        body = ('from pathlib import Path\nsys.stdin.read()\nPath("result.md").write_text("fresh")\n'
                'Path("tests/worker_execution/PLAN.md").write_text("tampered")\n')
        with self.fake_cli(body):
            result = execute('codex', 'gpt-5.6-sol', 'medium', workspace, 'prompt',
                             [workspace / 'result.md'], 'tamper', 1)
        self.assertFalse(result['ok'])
        self.assertIn('protected inputs', result['error'])

    def test_review_verdict_fails_closed(self):
        path = self.root / 'review.json'
        for value in ('{}', '{"passed":"true","issues":[]}', '{"passed":false,"issues":["invalid comparison"]}',
                      '{"passed":true,"issues":["contradiction"]}'):
            path.write_text(value)
            self.assertFalse(review_verdict(path)[0])
        path.write_text('{"passed":true,"issues":[]}')
        self.assertTrue(review_verdict(path)[0])


class PolicyTests(unittest.TestCase):
    def test_single_report_scaffold_and_no_answer_in_planning_prompt(self):
        from run_tests import PROMPTS
        self.assertNotIn("choose belief #3", PROMPTS['plan_generation'])
        supervisor = (ROOT / 'templates/SUPERVISOR.md').read_text()
        self.assertNotIn('# REPORT — {RUN_ID}', supervisor)
        init = (ROOT / 'templates/INIT.md').read_text()
        self.assertNotIn('at now +', init)
        self.assertNotIn('**Wandb Report triggers**', init)
        self.assertIn('AGENTS.fragment.md', init)

    def test_worker_routing_and_file_ownership(self):
        text = (ROOT / 'templates/research-worker.toml').read_text()
        self.assertIn('model = "gpt-5.6-sol"', text)
        self.assertIn('model_reasoning_effort = "medium"', text)
        self.assertIn('Do not modify STATE.md, SYNTHESIS.md', text)
        text = (ROOT / 'templates/WANDB_REPORTS.md').read_text()
        self.assertIn('Never edit STATE.md or SYNTHESIS.md', text)


if __name__ == '__main__':
    unittest.main()
