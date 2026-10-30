"""Versioned local evaluation and idempotent legacy projection, independent of inserts."""
from .store import dump
import json


def finish(store, profile_id='default', project=True):
    from .discovery_state import ensure
    ensure(store)
    matched=store.evaluate(profile_id, pending_only=True)
    succeeded=filtered=0
    if project:
        from scanners.compat import mirror_to_pipeline
        with store.connect() as db:
            rows=db.execute("SELECT p.job_id,p.fingerprint,j.data FROM search_projection p JOIN jobs j ON j.id=p.job_id WHERE p.status='pending' LIMIT 100").fetchall()
        for row in rows:
            try:
                projection=mirror_to_pipeline(store.path.parent,[json.loads(row['data'])])
            except Exception as exc:
                with store.connect() as db: db.execute('UPDATE search_projection SET error=? WHERE job_id=? AND fingerprint=?',(type(exc).__name__,row['job_id'],row['fingerprint']))
            else:
                rejected=bool(projection.get('rejected_title',0) or projection.get('rejected_location',0))
                with store.connect() as db: db.execute("UPDATE search_projection SET status=?,error='' WHERE job_id=? AND fingerprint=?",('filtered' if rejected else 'done',row['job_id'],row['fingerprint']))
                if rejected: filtered+=1
                else: succeeded+=1
    with store.connect() as db: pending=db.execute("SELECT COUNT(*) FROM search_projection WHERE status='pending'").fetchone()[0]
    return {'local_matching':matched,'projection_completed':succeeded,'projection_filtered':filtered,'projection_pending':pending,
        'notice':'Local lexical matching is not cloud evaluation or legal eligibility. Legacy mirror retains its filters.'}
