"""Non-destructive connection between original Markdown pipeline and SQLite.

The old scanner API and files remain supported. Mirrors never delete records,
rewrite applications, or modify CVs. Each side is idempotent; failures surface.
"""
from dataclasses import fields
from pathlib import Path
from filelock import FileLock
from .base import JobPosting, ScanResult


def mirror_to_pipeline(data_dir, rows):
    from .bridge import PipelineBridge
    from jobhunter_app.expanded_sources import config
    allowed = {f.name for f in fields(JobPosting)}
    directory = Path(data_dir)
    with FileLock(str(directory / '.pipeline.lock'), timeout=30):
        bridge = PipelineBridge(config(), str(directory))
        report = bridge.process([ScanResult('dashboard-collector',
            jobs=[JobPosting(**{k: v for k, v in row.items() if k in allowed}) for row in rows])])
        return {k: v for k, v in report.items() if k != 'new_jobs'}


def mirror_to_inbox(rows, data_dir='data'):
    from jobhunter_app.store import Store
    store = Store(Path(data_dir) / 'jobhunter.sqlite3')
    return store.ingest(rows, source='legacy-scanner')


def restore_existing_legacy(store, profile_id='default'):
    """Recover a legacy workspace once, with full archival and byte backups.

    Conflicting historical identities remain archived/unlinked, not silently
    overwritten or discarded. The audit summary explicitly counts these rows.
    Only the selected database's sibling legacy directory is considered.
    """
    from jobhunter_app.migration import FILES, migrate
    directory = store.path.parent
    with FileLock(str(store.path) + '.legacy-bootstrap.lock', timeout=30):
        with store.connect() as db:
            prior = db.execute("SELECT details FROM audit WHERE event='legacy_workspace_restored' AND json_extract(details,'$.profile_id')=? ORDER BY id DESC LIMIT 1", (profile_id,)).fetchone()
            if prior:
                import json
                return json.loads(prior[0])
        if not any((directory / name).is_file() for name in FILES): return None
        result = migrate(store, directory, dry_run=False, profile_id=profile_id, allow_partial=True)
        report = {'profile_id': profile_id, 'jobs_inserted': result['result']['inserted'],
            'history_archived': result['new_history_records'], 'conflicting_rows': len(result['conflicts']),
            'invalid_rows': len(result['invalid_records']), 'file_errors': len(result['file_errors']),
            'warning_rows': len(result['warnings']), 'batch_id': result['batch_id'],
            'notice': 'Legacy files backed up and unchanged. Conflicting identities are archived without automatic job links; inspect migration preview. Historical states are not asserted as current applications.'}
        with store.connect() as db:store.audit(db, 'legacy_workspace_restored', report)
        return report
