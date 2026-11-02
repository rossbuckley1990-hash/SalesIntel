"""The worker must respect source-requested recovery delays."""
from datetime import UTC, datetime
import importlib.util
from pathlib import Path
import httpx
import pytest

path = Path(__file__).resolve().parents[1] / 'scripts' / 'market_monitor.py'
spec = importlib.util.spec_from_file_location('market_monitor_cli', path)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


def status_error(code, value):
    request = httpx.Request('GET', 'https://example.test')
    response = httpx.Response(code, request=request, headers={'Retry-After': value})
    return httpx.HTTPStatusError('failed', request=request, response=response)


def test_retry_after_seconds_and_http_date():
    now = datetime(2026, 1, 1, tzinfo=UTC)
    assert worker.retry_after_seconds(status_error(429, '120'), now) == 120
    assert worker.retry_after_seconds(status_error(503, 'Thu, 01 Jan 2026 00:05:00 GMT'), now) == 300
    assert worker.retry_after_seconds(status_error(500, '120'), now) == 0
    assert worker.retry_after_seconds(status_error(429, 'invalid'), now) == 0
    assert worker.retry_after_seconds(status_error(429, '172800'), now) == 172800
    assert worker.retry_after_seconds(status_error(403, '900'), now) == 0
    assert worker.retry_after_seconds(status_error(403, '900'), now, include_403=True) == 900


def test_retry_deadline_survives_worker_restart_and_fails_closed(tmp_path):
    path = tmp_path / 'retry.json'
    now = datetime(2026, 1, 1, tzinfo=UTC)
    assert worker.load_retry_deadline(path) is None
    deadline = worker.save_retry_deadline(path, 172800, now)
    assert worker.load_retry_deadline(path) == deadline
    assert deadline.isoformat() == '2026-01-03T00:00:00+00:00'
    assert path.stat().st_mode & 0o777 == 0o600
    path.write_text('{not valid json')
    with pytest.raises(RuntimeError, match='Invalid persisted'):
        worker.load_retry_deadline(path)


def test_launchd_config_has_no_embedded_secrets_and_separate_source_workers(tmp_path):
    path = Path(__file__).resolve().parents[1] / 'scripts' / 'generate_market_launch_agents.py'
    spec = importlib.util.spec_from_file_location('market_launch_agents', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    database = tmp_path / 'misi.db'
    fts = module.make_plist('find-a-tender', database)
    cf = module.make_plist('contracts-finder', database)
    assert fts['Label'] != cf['Label']
    assert fts['RunAtLoad'] and fts['KeepAlive']
    assert fts['EnvironmentVariables']['DATABASE_URL'].endswith('/misi.db')
    assert set(fts['EnvironmentVariables']) == {'APP_ENV', 'PYTHONPATH', 'DATABASE_URL'}
    assert 'find-a-tender' in fts['ProgramArguments']
    assert 'contracts-finder' in cf['ProgramArguments']
    backfill = module.make_backfill_plist(database)
    assert backfill['KeepAlive'] == {'SuccessfulExit': False}
    assert '--daily-budget' in backfill['ProgramArguments']
    assert set(backfill['EnvironmentVariables']) == {'APP_ENV', 'PYTHONPATH', 'DATABASE_URL'}
