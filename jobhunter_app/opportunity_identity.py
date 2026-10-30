"""Reversible grouping only after matching a validated first-party observation."""
import json
from .search_strategy import fingerprint
from .store import dump
from .source_discovery import recognize


def reconcile(store, leads=()):
    from utils.queue_exporter import canonicalize_url
    with store.connect() as db:
        jobs={row['url']:row['id'] for row in db.execute('SELECT id,url FROM jobs')}
        trusted={}
        for row in db.execute('SELECT j.id,j.url,s.source FROM jobs j JOIN sightings s ON s.job_id=j.id'):
            try: binding=recognize(row['url'])
            except ValueError: continue
            if binding and binding[2] and row['source']==f'{binding[0]}:{binding[1]}':
                trusted[binding]=row['id']
                group=fingerprint(binding)
                db.execute('INSERT OR IGNORE INTO opportunity_members VALUES(?,?,?)',(row['id'],group,dump({'first_party':row['url']})))
        for lead in leads:
            key=(lead.kind,lead.identifier,lead.posting_id)
            job_id=jobs.get(canonicalize_url(lead.origin_url))
            if key in trusted and job_id:
                # Do not overwrite an existing reviewed/group decision on conflicting evidence.
                db.execute('INSERT OR IGNORE INTO opportunity_members VALUES(?,?,?)',
                    (job_id,fingerprint(key),dump({'observed_destination':lead.url,'anchor_job':trusted[key]})))
        counts=db.execute('SELECT COUNT(*) members,COUNT(DISTINCT group_id) groups FROM opportunity_members').fetchone()
    return dict(counts)


def unlink(store, job_id):
    """Grouping is metadata only: removal never rewrites a job/application/alias."""
    with store.connect() as db: db.execute('DELETE FROM opportunity_members WHERE job_id=?',(job_id,))
