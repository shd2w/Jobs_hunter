"""Finite local discover -> supported retrieval -> existing intake -> report runner."""
from dataclasses import asdict
from datetime import datetime, timezone
import json
import time
from uuid import uuid4
from filelock import FileLock
from .store import dump, now
from .search_strategy import plan, fingerprint
from .discovery_state import ensure
from .source_discovery import SourceLead


def run(store, profile_id='default', regions=(), languages=(), max_attempts=12,
        seconds=120, approve_public_ats=False, cancel_event=None, project=True,
        providers=None, search_provider=None, inspect_links=False):
    if type(max_attempts) is not int or not 1<=max_attempts<=100 or not 1<=seconds<=1800:
        raise ValueError('Invalid finite run budget')
    with FileLock(str(store.path)+'.discovery.lock',timeout=0):
        return _run(store,profile_id,regions,languages,max_attempts,seconds,approve_public_ats,
                    cancel_event,project,providers,search_provider,inspect_links)


def _run(store,pid,regions,languages,max_attempts,seconds,approve,cancel,project,providers,search_provider,inspect_links):
    from .automatic import configure
    from .sources import scan
    from .source_catalog import record,activate,assessed
    from .search_coverage import coverage,observe,priority
    from .source_health import health
    from .opportunity_identity import reconcile
    from .discovery_processing import finish
    configure(store,pid)  # insert-only seeds; never reapprove an existing pause
    ensure(store)
    queries,metadata=plan(store.profile(pid),pid,regions,languages,max_queries=100)
    if providers is not None:
        from scanners.jobspy_registry import SITES
        if not providers or set(providers)-set(SITES): raise ValueError('Unsupported provider scope')
        queries=[q for q in queries if q.provider in providers]
    with store.connect() as db:
        prior_groups={r[0] for r in db.execute('SELECT DISTINCT group_id FROM opportunity_members')}
    run_id=uuid4().hex;started=now();deadline=time.monotonic()+seconds
    tasks=[];leads=[];seen_leads=set();queued=set();attempts=0
    with store.connect() as db:
        db.execute("UPDATE search_runs SET status='interrupted',finished_at=? WHERE status='running'",(started,))
        db.execute("UPDATE search_tasks SET status='deferred' WHERE status IN ('dispatched','planned')")
        db.execute('INSERT INTO search_runs VALUES(?,?,?,?,?,?,?)',(run_id,pid,metadata['intent_version'],started,None,'running','{}'))
        history=[{'source_id':r['source_id'],**json.loads(r['data'])} for r in db.execute("SELECT source_id,data FROM search_tasks WHERE status IN ('succeeded','partial') ORDER BY rowid DESC LIMIT 200")]

    def save(task):
        with store.connect() as db:
            db.execute('INSERT INTO search_tasks VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status,data=excluded.data',
                (task['id'],run_id,task['source_id'],task['signature'],task['status'],dump(task)))

    def add(source_id,query=None,lead_id=None):
        signature=query.signature if query else fingerprint([source_id,'snapshot-1'])
        if signature in queued: return
        queued.add(signature)
        task={'id':run_id+':'+signature,'source_id':source_id,'signature':signature,
              'status':'planned','order':len(tasks),'query':asdict(query) if query else None,
              'lead_id':lead_id,'started_at':None,'finished_at':None}
        tasks.append(task);save(task)

    query_objects={q.signature:q for q in queries}
    for query in queries: add('jobspy_'+query.provider+':configured',query)
    with store.connect() as db:
        for row in db.execute("SELECT id FROM sources WHERE kind NOT LIKE 'jobspy_%' ORDER BY id"):
            add(row['id'])
    # Persist all work before dispatch: an interrupted run is diagnosable/resumable.
    if search_provider and queries:
        try:
            observed=search_provider.search(queries[0])
            from .source_discovery import discover
            initial=discover(observed)
            metadata['search_provider']={'status':'succeeded','requests':1,'leads':len(initial)}
        except Exception as exc:
            initial=[];metadata['search_provider']={'status':'failed','error_category':type(exc).__name__}
    else:
        initial=[];metadata['search_provider']={'status':'not_configured','requests':0}

    metadata['public_inspection']={'enabled':bool(inspect_links),'attempts':0,'requests':0,'outcomes':[]}
    def ingest_leads(new_leads):
        for lead in new_leads[:200]:
            record(store,lead)
            if (lead.id,lead.origin_url) not in seen_leads:
                leads.append(lead);seen_leads.add((lead.id,lead.origin_url))
            if inspect_links and not lead.kind and lead.field=='job_url_direct' and metadata['public_inspection']['attempts']<2 and time.monotonic()<deadline:
                signature=fingerprint(['public-inspection-1',lead.url])
                with store.connect() as db: prior=db.execute('SELECT updated_at FROM search_progress WHERE signature=?',(signature,)).fetchone()
                if not prior or (datetime.now(timezone.utc)-datetime.fromisoformat(prior[0])).total_seconds()>86400:
                    from .source_discovery import inspect_public
                    inspection=inspect_public(lead)
                    metadata['public_inspection']['attempts']+=1
                    metadata['public_inspection']['requests']+=inspection['requests']
                    metadata['public_inspection']['outcomes'].append({'url':lead.url,**{k:v for k,v in inspection.items() if k!='leads'}})
                    with store.connect() as db: db.execute('INSERT INTO search_progress VALUES(?,?,?) ON CONFLICT(signature) DO UPDATE SET data=excluded.data,updated_at=excluded.updated_at',(signature,dump({'complete':True,'status':inspection['status']}),now()))
                    ingest_leads(inspection['leads'])
            binding=activate(store,lead,approve)
            if binding.get('source_id'):
                add(binding['source_id'],lead_id=lead.id)
    with store.connect() as db:
        saved=db.execute("SELECT evidence FROM source_leads WHERE state IN ('recognized','available','under_assessment') ORDER BY updated_at LIMIT 100").fetchall()
    resumed=[]
    for row in saved:
        values=json.loads(row['evidence'])
        if values: resumed.append(SourceLead(**values[-1]))
    ingest_leads(initial+resumed)
    while any(task['status']=='planned' for task in tasks):
        candidates=[task for task in tasks if task['status']=='planned']
        # Every fifth choice reserves source-wide exploration, even if provider history is strong.
        native=[t for t in candidates if not t['query'] and not t['lead_id']]
        task=min(native,key=lambda t:t['order']) if native and attempts%5==4 else min(candidates,key=lambda t:priority(t,history))
        if cancel and cancel.is_set():
            task.update(status='cancelled',reason='User cancellation');save(task);continue
        if attempts>=max_attempts or time.monotonic()>=deadline:
            task.update(status='deferred',reason='Local execution budget exhausted');save(task);continue
        readiness={item['id']:item for item in health(store)}.get(task['source_id'])
        if not readiness or not readiness['approved']:
            task.update(status='deferred',reason='Source needs explicit access approval');save(task);continue
        if readiness['next_allowed_at'] and datetime.fromisoformat(readiness['next_allowed_at'])>datetime.now(timezone.utc):
            task.update(status='deferred',reason='Source/provider gate or cooldown',next_allowed_at=readiness['next_allowed_at']);save(task);continue
        with store.connect() as db:
            progress=db.execute('SELECT data,updated_at FROM search_progress WHERE signature=?',(task['signature'],)).fetchone()
            prior=db.execute("SELECT data FROM search_tasks WHERE signature=? AND status IN ('succeeded','partial') AND run_id!=? ORDER BY rowid DESC LIMIT 1",(task['signature'],run_id)).fetchone()
        # A completed query snapshot has a bounded cache lifetime; incomplete query pages resume.
        cached=json.loads(progress['data']).get('complete') if progress else not task['query'] and bool(prior)
        timestamp=progress['updated_at'] if progress else json.loads(prior['data']).get('finished_at') if prior else None
        if cached and timestamp and (datetime.now(timezone.utc)-datetime.fromisoformat(timestamp)).total_seconds()<3600:
            task.update(status='deferred',reason='Compatible completed snapshot still fresh');save(task);continue
        if cached and progress:
            with store.connect() as db: db.execute('DELETE FROM search_progress WHERE signature=?',(task['signature'],))
        attempts+=1;task.update(status='dispatched',started_at=now());save(task)
        try:
            result=scan(store,task['source_id'],profile_id=pid,mirror_legacy=False,
                        request=query_objects.get(task['signature']),cancel_event=cancel)
        except Exception as exc:
            task.update(status='failed',error_category=type(exc).__name__,reason=str(exc)[:500])
            task['quality']=observe(store,task['source_id'],task['signature'],error=type(exc).__name__)
        else:
            task.update(status='cancelled' if result.get('cancelled') else 'partial' if result.get('invalid') or result.get('provider_errors') else 'succeeded',result=result)
            task['quality']=observe(store,task['source_id'],task['signature'],result=result)
            found=[SourceLead(**item) for item in result.get('discovery_leads',[])]
            ingest_leads(found)
            if task['lead_id']: task['assessment']=assessed(store,task['lead_id'],result,pid)
        task['finished_at']=now();save(task)
    identity=reconcile(store,leads)
    processing=finish(store,pid,project)
    # Source contributions overlap: never sum these as global opportunity novelty.
    for task in tasks:
        if 'result' not in task: continue
        with store.connect() as db:
            observations=db.execute('SELECT DISTINCT o.group_id,m.data FROM opportunity_members o JOIN sightings s ON s.job_id=o.job_id JOIN matches m ON m.job_id=o.job_id WHERE s.source=? AND m.profile_id=?',(task['source_id'],pid)).fetchall()
        relevant={row['group_id'] for row in observations if json.loads(row['data']).get('matched_profile_skills') and json.loads(row['data']).get('eligibility')!='excluded_by_config'}
        task['result']['new_confirmed_relevant_groups']=len(relevant-prior_groups)
        save(task)
    failed=any(t['status'] in ('failed','partial') for t in tasks)
    succeeded=any(t['status']=='succeeded' for t in tasks)
    status='cancelled' if cancel and cancel.is_set() else 'partial' if failed or any(t['status']=='deferred' for t in tasks) or processing['projection_pending'] else 'succeeded'
    if failed and not succeeded: status='failed'
    report={'run_id':run_id,'status':status,'started_at':started,'finished_at':now(),
        'plan':metadata,'budget':{'attempts':attempts,'max_attempts':max_attempts,'dispatch_seconds':seconds,
            'notice':'Deadline stops new dispatch, not an in-flight provider call. JobSpy calls include vendor-managed requests.'},
        'tasks':tasks,'coverage':coverage(tasks),'leads':[asdict(lead) for lead in leads],
        'identity':identity,'processing':processing,'counts':{
            'planned':len(tasks),'dispatched':sum(bool(t['started_at']) for t in tasks),
            **{state:sum(t['status']==state for t in tasks) for state in ('succeeded','partial','failed','deferred','cancelled')},
            'candidate_urls':len({lead.url for lead in leads}),
            'recognized_source_leads':len({lead.id for lead in leads if lead.kind}),
            'successfully_collected_sources':len({t['source_id'] for t in tasks if t.get('result',{}).get('valid_records',0)>0}),
            'canonical_insertions':sum(t.get('result',{}).get('inserted',0) for t in tasks)},
        'limits':['No global recall or legal eligibility claim.','Live coverage gain requires adjudicated baseline comparison.', 'At most 100 planned query requests; extraction bounded to 1000 observations and 200 processed leads per collection. Individual unknown job URLs are candidate URLs, not discovered reusable sources.']}
    with store.connect() as db: db.execute('UPDATE search_runs SET finished_at=?,status=?,report=? WHERE id=?',(report['finished_at'],status,dump(report),run_id))
    return report


def report(store,run_id=None):
    ensure(store)
    with store.connect() as db:
        row=db.execute('SELECT * FROM search_runs WHERE id=?',(run_id,)).fetchone() if run_id else db.execute('SELECT * FROM search_runs ORDER BY started_at DESC LIMIT 1').fetchone()
        if not row: raise ValueError('No discovery run found')
        value=json.loads(row['report']);value['status']=row['status']
        value['persisted_tasks']=[json.loads(t['data'])|{'status':t['status']} for t in db.execute('SELECT status,data FROM search_tasks WHERE run_id=? ORDER BY rowid',(row['id'],))]
    return value
