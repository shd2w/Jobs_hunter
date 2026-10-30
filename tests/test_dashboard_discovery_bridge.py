"""Real HTTP/worker path with controlled JobSpy boundary; not live source proof."""
import json
import sys
from threading import Thread
from types import SimpleNamespace
import pandas as pd
import pytest
from jobhunter_app.automatic import AutomaticDiscovery
from jobhunter_app.sources import register, scan
from jobhunter_app.store import Store
from jobhunter_app.web import make_server
from tests.test_web_local import request, token


def test_dashboard_action_dispatches_generated_queries_and_reports_intake(tmp_path, monkeypatch):
    monkeypatch.setattr(AutomaticDiscovery, 'start', lambda self: None)
    calls = []
    def scrape(**kw):
        calls.append(kw)
        return pd.DataFrame([{'job_url': 'https://example.org/jobs/dashboard', 'title': 'Unfamiliar Wizard',
                             'company': 'Fixture', 'description': 'Python SQL'}])
    monkeypatch.setitem(sys.modules, 'jobspy', SimpleNamespace(scrape_jobs=scrape))
    def unavailable(*args, **kwargs): raise OSError('fixture native outage')
    monkeypatch.setattr('jobhunter_app.network.get', unavailable)
    # The controlled collection tests cover Scrapling itself; do not perform native HTTP here.
    monkeypatch.setattr('jobhunter_app.scrapling_engine.collect', unavailable)
    store = Store(tmp_path/'app.db')
    store.save_profile({'skills': ['Python', 'SQL'], 'matching': {'preferred_title_terms': ['backend']}})
    server = make_server(store, 0, automatic=True)
    thread = Thread(target=server.serve_forever, daemon=True); thread.start(); web = (store, server)
    try:
        before = json.loads(request(web, 'GET', '/api/automatic')[2])
        assert len(before['sources']) == 16 and before['runtime']['dashboard_profile_search']
        assert request(web, 'POST', '/api/profile-search', {})[0] == 403
        headers = {'X-JobHunter-Token': token(web)}
        assert request(web, 'POST', '/api/profile-search', {'force': True}, headers)[0] == 400
        assert request(web, 'POST', '/api/profile-search', {}, headers)[0] == 200
        assert calls == []  # HTTP only queues; never holds the request on provider latency.
        again = json.loads(request(web, 'POST', '/api/profile-search', {}, headers)[2])
        assert again['already_pending']
        server.automatic.cycle()
        assert calls and calls[0]['search_term'] == 'Python Developer'
        after = json.loads(request(web, 'GET', '/api/automatic')[2])
        report = after['profile_search']
        assert report['counts']['canonical_insertions'] == 1
        assert report['status'] == 'partial' and any(t['status'] == 'failed' for t in report['tasks'])
        assert 'Unfamiliar Wizard' == store.jobs()[0]['title']
        assert 'profile_search_requested' in after and not after['profile_search_requested']
        assert request(web, 'POST', '/api/automatic', {'enabled': False}, headers)[0] == 200
        assert request(web, 'POST', '/api/profile-search', {}, headers)[0] == 400
    finally:
        server.shutdown(); server.server_close(); thread.join(3)


def test_runtime_diagnostics_read_only_in_manual_mode(tmp_path):
    store = Store(tmp_path/'app.db'); server = make_server(store, 0)
    thread = Thread(target=server.serve_forever, daemon=True); thread.start(); web = (store, server)
    try:
        for path in ('/api/runtime', '/api/automatic'):
            status, _, raw = request(web, 'GET', path)
            assert status == 200
            value = json.loads(raw)
            runtime = value.get('runtime', value)
            assert runtime['build'] == 'dashboard-cli-consistency-1'
            assert len(runtime['code_fingerprint']) == 12
            assert set(runtime['engines']) == {'jobspy', 'scrapling'}
            assert str(tmp_path) not in raw.decode()
        with store.connect() as db:
            assert not db.execute("SELECT 1 FROM sqlite_master WHERE name='autonomy_meta'").fetchone()
            assert db.execute('SELECT COUNT(*) FROM sources').fetchone()[0] == 0
    finally:
        server.shutdown(); server.server_close(); thread.join(3)


@pytest.mark.parametrize('kind', ['payload', 'content_type', 'private_error'])
def test_source_diagnostic_is_specific_but_does_not_leak_payload(tmp_path, monkeypatch, kind):
    store = Store(tmp_path/'app.db'); sid = register(store, 'arbeitnow', 'de', True)
    def get(*args, **kwargs):
        if kind == 'private_error': raise ValueError('candidate-private-body-and-secret')
        return (b'{}', 'application/json') if kind == 'payload' else (b'<html>secret</html>', 'text/html')
    monkeypatch.setattr('jobhunter_app.network.get', get)
    with pytest.raises(ValueError): scan(store, sid, mirror_legacy=False)
    with store.connect() as db:
        run = db.execute('SELECT status,metrics FROM runs').fetchone()
        metrics = json.loads(run['metrics'])
        source = db.execute('SELECT * FROM sources').fetchone()
    assert run['status'] == 'failed' and source['last_run'] and source['approved']
    assert metrics['failure_stage'] == 'retrieval' and metrics['failure_code'] == 'response_validation'
    assert metrics['error_type'] == 'ValueError'
    assert 'secret' not in json.dumps(metrics) and 'candidate-private' not in json.dumps(metrics)
    assert bool(metrics.get('validation_hint')) == (kind != 'private_error')


def test_profile_run_passes_pause_cancellation_and_no_approval_override(tmp_path, monkeypatch):
    worker = AutomaticDiscovery(Store(tmp_path/'app.db'))
    seen = {}
    def run(store, profile_id, **kwargs):
        seen.update(kwargs)
        worker.choice(False)
        assert kwargs['cancel_event'].is_set()
    monkeypatch.setattr('jobhunter_app.discovery_run.run', run)
    worker.search(); worker.cycle()
    assert seen['approve_public_ats'] is False and seen['max_attempts'] == 12
    assert worker.status()['phase'] == 'paused'


def test_running_search_status_uses_persisted_task_counts(tmp_path):
    from jobhunter_app.discovery_state import ensure
    from jobhunter_app.runtime_status import latest_search
    from jobhunter_app.store import dump, now
    store = Store(tmp_path/'app.db'); ensure(store)
    with store.connect() as db:
        db.execute('INSERT INTO search_runs VALUES(?,?,?,?,?,?,?)', ('r', 'default', 'v', now(), None, 'running', '{}'))
        task = {'source_id': 'jobspy_indeed:configured', 'started_at': now(), 'result': {'inserted': 2}}
        db.execute('INSERT INTO search_tasks VALUES(?,?,?,?,?,?)', ('t', 'r', task['source_id'], 'sig', 'succeeded', dump(task)))
    result = latest_search(store, 'default')
    assert result['status'] == 'running'
    assert result['counts']['dispatched'] == 1 and result['counts']['canonical_insertions'] == 2
    assert result['counts']['succeeded'] == 1
