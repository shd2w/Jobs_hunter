"""Manual health reports, reset and batch orchestration. Never schedules a worker."""
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import json
from filelock import FileLock, Timeout
from .store import now, dump

def provider_family(kind):
    # Native API and Scrapling HTML paths share one publisher request gate.
    return {'scrapling_jobicy':'jobicy','scrapling_arbeitnow':'arbeitnow'}.get(kind,kind)

def provider_kinds(kind):
    family=provider_family(kind)
    return (family,'scrapling_'+family) if family in ('jobicy','arbeitnow') else (kind,)


def retry_gate(db,kind,value,cooldown):
    value=str(value).strip()
    current=datetime.now(timezone.utc);until=current+timedelta(seconds=cooldown)
    try:
        candidate=current+timedelta(seconds=int(value)) if str(value).isdigit() else parsedate_to_datetime(value)
        if candidate.tzinfo is None: candidate=candidate.replace(tzinfo=timezone.utc)
        until=max(until,candidate)
    except (ValueError,TypeError,OverflowError): pass
    prior=db.execute('SELECT not_before FROM provider_gates WHERE kind=?',(kind,)).fetchone()
    if prior: until=max(until,datetime.fromisoformat(prior[0]))
    db.execute('INSERT INTO provider_gates VALUES(?,?) ON CONFLICT(kind) DO UPDATE SET not_before=excluded.not_before',(kind,until.isoformat()))

def health(store):
    from .sources import POLICIES, POST_PLATFORMS
    result=[]
    with store.connect() as db:
        for row in db.execute('SELECT * FROM sources ORDER BY id'):
            item=dict(row)
            if row['kind'] in POST_PLATFORMS:
                from .platform_posts import setup
                item['platform_setup']=setup(row['kind'])
            last=db.execute('SELECT * FROM runs WHERE source=? ORDER BY id DESC LIMIT 1',(row['id'],)).fetchone()
            success=db.execute("SELECT finished_at FROM runs WHERE source=? AND status IN ('success','partial') ORDER BY id DESC LIMIT 1",(row['id'],)).fetchone()
            family=provider_family(row['kind']);family_kinds=provider_kinds(row['kind'])
            gate=db.execute('SELECT not_before FROM provider_gates WHERE kind=?',(family,)).fetchone()
            due=datetime.fromisoformat(row['last_run'])+timedelta(seconds=POLICIES[row['kind']]['cooldown']) if row['last_run'] else datetime.min.replace(tzinfo=timezone.utc)
            if row['kind'] in ('structured_html','jobicy','arbeitnow','hn','usajobs','wuzzuf','naukrigulf','scrapling_jobicy','scrapling_arbeitnow')+POST_PLATFORMS:
                latest=db.execute('SELECT MAX(last_run) FROM sources WHERE kind IN ('+','.join('?' for _ in family_kinds)+')',family_kinds).fetchone()[0]
                if latest: due=max(due,datetime.fromisoformat(latest)+timedelta(seconds=POLICIES[row['kind']]['cooldown']))
            wait_reason = 'Source refresh cooldown' if row['last_run'] else None
            if due > (datetime.fromisoformat(row['last_run'])+timedelta(seconds=POLICIES[row['kind']]['cooldown']) if row['last_run'] else datetime.min.replace(tzinfo=timezone.utc)):
                wait_reason = 'Shared publisher cooldown: native API and HTML use the same request budget'
            if gate and datetime.fromisoformat(gate[0]) >= due:
                due=max(due,datetime.fromisoformat(gate[0]))
                wait_reason = 'Provider retry/backoff gate; scan/reset/reapproval cannot bypass it'
            item['wait_reason'] = wait_reason if due > datetime.now(timezone.utc) else None
            checkpoint=db.execute('SELECT updated_at FROM source_checkpoints WHERE source_id=?',(row['id'],)).fetchone()
            item.update(engine='scrapling' if row['kind'].startswith('scrapling_') else 'jobspy' if row['kind'].startswith('jobspy_') else 'native',provider_family=family,last_completed_at=success[0] if success else None,next_allowed_at=due.isoformat() if due!=datetime.min.replace(tzinfo=timezone.utc) else None,checkpoint_saved_at=checkpoint[0] if checkpoint else None,last_metrics=json.loads(last['metrics']) if last else {},coverage_warning='Observed snapshots only. Absence is not evidence of vacancy closure. Discovery does not score relevance.')
            from .pagination import state as pagination
            item['pagination'] = item['last_metrics'].get('pagination') or pagination(evidence='historical receipt unavailable')
            item['last_attempt_status'] = last['status'] if last else None
            from .source_outcomes import outcome
            item['outcome'] = outcome(item['last_metrics'])
            item['observations_older_than_30_days']=db.execute("SELECT COUNT(*) FROM sightings WHERE source=? AND datetime(last_seen)<datetime('now','-30 days')",(row['id'],)).fetchone()[0]
            item['manual_priority_hint']='Review failures/permissions first' if row['health'] in ('failed','rate_limited','interrupted','access_blocked') else 'Resume incomplete pass when due' if item['last_metrics'].get('bounded_selection') else 'Compare unique contribution before another manual pass'
            result.append(item)
    return result

def reset(store,source_id):
    try:
        with FileLock(str(store.path)+'.scan.lock',timeout=0),store.connect() as db:
            if not db.execute('SELECT 1 FROM sources WHERE id=?',(source_id,)).fetchone(): raise ValueError('Unknown source')
            db.execute('DELETE FROM source_checkpoints WHERE source_id=?',(source_id,));store.audit(db,'source_checkpoint_reset',{'source':source_id})
    except Timeout as exc: raise ValueError('Another source scan is active') from exc
    return {'reset':source_id,'notice':'Checkpoint only; approvals, provider gates, cooldowns and stored jobs are unchanged.'}

def batch(store,source_ids,cancel_event=None,transport=None,profile_id='default'):
    from .sources import _scan_locked,fetch
    if not isinstance(source_ids,list) or not 1<=len(source_ids)<=10 or any(not isinstance(x,str) for x in source_ids) or len(set(source_ids))!=len(source_ids): raise ValueError('Supply 1–10 distinct source IDs')
    results=[]
    try:
        with FileLock(str(store.path)+'.scan.lock',timeout=0):
            for identity in source_ids:
                if cancel_event and cancel_event.is_set(): break
                try: results.append({'source':identity,'result':_scan_locked(store,identity,transport or fetch,cancel_event,profile_id)})
                except ValueError as exc: results.append({'source':identity,'error':str(exc)})
    except Timeout as exc: raise ValueError('Another source scan is active') from exc
    cancelled=bool(cancel_event and cancel_event.is_set())
    failed=sum('error' in r or r.get('result',{}).get('pagination',{}).get('failed',False) for r in results)
    partial=sum(bool(r.get('result',{}).get('pagination',{}).get('partial') or r.get('result',{}).get('invalid') or r.get('result',{}).get('bounded_selection')) for r in results)
    return {'results':results,'cancelled':cancelled,'manual':True,
            'status':'cancelled' if cancelled else 'failed' if failed==len(source_ids) else 'partial' if failed or partial else 'success',
            'counts':{'requested':len(source_ids),'attempted':len(results),'failed':failed,'partial':partial,'deferred':len(source_ids)-len(results)}}
