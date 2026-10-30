"""Local build/dependency diagnostics; no network, secrets or filesystem paths."""
from functools import lru_cache
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import platform

BUILD = 'source-recovery-1'


@lru_cache(maxsize=1)
def status():
    root = Path(__file__).parent
    digest = sha256()
    for name in ('automatic.py', 'discovery_run.py', 'sources.py', 'web.py', 'static/automatic.js','evaluation_service.py','pagination.py','static/evaluation.js','static/discovery.js','source_health.py','provider_recovery.py','source_outcomes.py','expanded_sources.py'):
        digest.update(name.encode())
        digest.update((root / name).read_bytes())
    engines = {}
    for name, package in (('jobspy', 'python-jobspy'), ('scrapling', 'scrapling')):
        try:
            engines[name] = {'installed': True, 'version': version(package)}
        except PackageNotFoundError:
            engines[name] = {'installed': False, 'version': None}
    return {'build': BUILD, 'code_fingerprint': digest.hexdigest()[:12],
            'python': platform.python_version(), 'engines': engines,
            'dashboard_profile_search': True, 'shared_evaluation': 'evaluation-service-1', 'pagination_contract': 1,
            'notice': 'Installed versions and code fingerprint, not proof of provider access. Restart the Python server after updating source.'}


def latest_search(store, profile_id):
    """Read-only public status subset; never migrate or expose profile/query values."""
    import json
    with store.connect() as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='search_runs'").fetchone():
            return None
        row = db.execute('SELECT id,status,started_at,finished_at,report FROM search_runs WHERE profile_id=? ORDER BY started_at DESC LIMIT 1', (profile_id,)).fetchone()
        if not row:
            return None
        report = json.loads(row['report'])
        tasks = [json.loads(item['data']) | {'status': item['status']} for item in db.execute('SELECT data,status FROM search_tasks WHERE run_id=? ORDER BY rowid', (row['id'],))]
    counts = report.get('counts') or {
        'planned': len(tasks), 'dispatched': sum(bool(item.get('started_at')) for item in tasks),
        **{state: sum(item['status'] == state for item in tasks) for state in ('succeeded', 'partial', 'failed', 'deferred', 'cancelled')},
        'canonical_insertions': sum(item.get('result', {}).get('inserted', 0) for item in tasks),
        'recognized_source_leads': len({(lead['kind'], lead['identifier']) for item in tasks
            for lead in item.get('result', {}).get('discovery_leads', []) if lead.get('kind')})}
    return {'run_id': row['id'], 'status': row['status'], 'started_at': row['started_at'],
            'finished_at': row['finished_at'], 'counts': counts,
            'tasks': [{'source_id': item['source_id'], 'status': item['status'],
                       'reason': item.get('reason', ''),
                       'error_category': item.get('error_category'),
                       'valid_records': item.get('result', {}).get('valid_records', 0)} for item in tasks],
            'notice': 'Candidate URLs and raw records are not verified unique relevant opportunities. Deferred work still needs eligibility/budget.'}
