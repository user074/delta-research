"""Buffered, append-only experiment telemetry; standard library only."""
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f'.{path.name}.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class ExperimentLogger:
    """Call at a chosen interval after aggregating GPU metrics on device.

    Give concurrent ranks/attempts separate run_dir values. History remains on
    disk across retries; final result files are replaced atomically.
    """
    def __init__(self, run_dir, log_name='experiment.log', flush_interval=100):
        if flush_interval < 1:
            raise ValueError('flush_interval must be positive')
        root = Path(run_dir)
        (root / 'logs').mkdir(parents=True, exist_ok=True)
        self.metrics_dir = root / 'metrics'
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = (root / 'logs' / log_name).open('a')
        self.history_file = (self.metrics_dir / 'history.jsonl').open('a')
        self.flush_interval = flush_interval
        self.pending = 0
        self.closed = False

    def log_step(self, **values):
        values.setdefault('timestamp', datetime.now(timezone.utc).isoformat())
        encoded = json.dumps(values, allow_nan=False)
        self.history_file.write(encoded + '\n')
        self.log_file.write('\t'.join(f'{k}={v}' for k, v in values.items()) + '\n')
        self.pending += 1
        if self.pending >= self.flush_interval:
            self.save_history()

    def log_results(self, results, name='results.json'):
        atomic_json(self.metrics_dir / name, results)

    def save_history(self):
        if not self.closed:
            self.log_file.flush()
            self.history_file.flush()
            self.pending = 0

    def close(self):
        if self.closed:
            return
        try:
            self.save_history()
        finally:
            try:
                self.log_file.close()
            finally:
                self.history_file.close()
                self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self.close()
        except Exception:
            if exc_type is None:
                raise
        return False
