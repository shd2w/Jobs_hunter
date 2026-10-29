"""Offline policy, collection, transaction and contribution acceptance evidence."""
from datetime import datetime, timezone, timedelta
import json
import sqlite3
import threading
from urllib.error import HTTPError
from urllib.parse import urlsplit, parse_qs
import pytest
from jobhunter_app.store import Store,SCHEMA,DISCOVERY_SCHEMA,HISTORY_SCHEMA
from jobhunter_app.sources import Source,register,scan,normalize,catalog
from jobhunter_app.collection import collect,Collection
from jobhunter_app.source_health import health,reset,batch
from jobhunter_app.source_directory import directory

@pytest.fixture
def store(tmp_path): return Store(tmp_path/'test.sqlite3')

@pytest.fixture(autouse=True)
def no_sleep(monkeypatch): monkeypatch.setattr('jobhunter_app.collection.time.sleep',lambda _:None)

def serve(monkeypatch,fn):
    calls=[]
    def get(url,*args,**kwargs):
        calls.append((url,kwargs));return json.dumps(fn(url,kwargs)).encode(),'application/json'
    monkeypatch.setattr('jobhunter_app.network.get',get);return calls

def due(store):
    with store.connect() as db: db.execute('UPDATE sources SET last_run=NULL')

def checkpoint(store,sid):
    with store.connect() as db:
        r=db.execute('SELECT data FROM source_checkpoints WHERE source_id=?',(sid,)).fetchone()
        return json.loads(r[0]) if r else None

def jobicy(n=1): return {'id':n,'url':f'https://example.com/jobs/{n}','jobTitle':'Python Engineer','companyName':'Example','jobGeo':'Europe','jobDescription':'<p>Python</p><script>bad()</script>','jobType':['full-time'],'salaryMin':1,'salaryMax':2,'salaryCurrency':'EUR','salaryPeriod':'year'}
def ar(n=1):return {'title':'Python Engineer','company_name':'Example','url':f'https://example.com/jobs/{n}','description':'Python','remote':True,'created_at':1700000000}

@pytest.mark.parametrize('kind,identifier',[('jobicy','other'),('arbeitnow','us'),('hn','0'),('hn','https://evil.example'),('usajobs',''),('usajobs','a\nb')])
def test_source_configuration_rejects(kind,identifier):
    with pytest.raises(ValueError): Source(kind,identifier)

def test_directory_complete_honest_safe():
    rows=directory('Python & Cairo');assert set('ABCDEFGHIJKL')=={x['category'] for x in rows}
    assert {'Wuzzuf','Naukrigulf','Workday employer careers'}<={x['name'] for x in rows}
    assert {x['kind'] for x in catalog()} >= {'greenhouse','lever','ashby','smartrecruiters','remotive','feed','jobicy','arbeitnow','hn','usajobs','wuzzuf','naukrigulf','linkedin','x','reddit','telegram','discord','jobspy_indeed','jobspy_linkedin','jobspy_google','jobspy_bayt','remoteok','weworkremotely'} and all(x['live_verified']==(x['name'] == 'Naukrigulf') for x in rows)
    for x in rows:
        assert x['evidence'].startswith('https://') and x['limitations'] and x['auth_configuration']
        assert 'Python & Cairo' in parse_qs(urlsplit(x['search_url']).query)['q'][0]
    assert next(x for x in rows if x['name']=='Naukrigulf')['status']=='authorized_browser_sample_verified'
    with pytest.raises(ValueError): directory('x'*201)

@pytest.mark.parametrize('version',[1,2,3])
def test_prior_schemas_snapshot_and_preserve(version,tmp_path):
    file=tmp_path/f'v{version}.sqlite3'
    with sqlite3.connect(file) as db:
        db.executescript(SCHEMA+(DISCOVERY_SCHEMA if version>=2 else '')+(HISTORY_SCHEMA if version>=3 else '')+f'PRAGMA user_version={version};')
        db.execute("INSERT INTO profiles VALUES('keep','{}','2020-01-01')")
    store=Store(file)
    with store.connect() as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==5
        assert db.execute('SELECT id FROM profiles').fetchone()[0]=='keep'
        assert db.execute('SELECT COUNT(*) FROM source_checkpoints').fetchone()[0]==0
    snapshots=list(tmp_path.glob('*.bak'));assert len(snapshots)==1
    with sqlite3.connect(snapshots[0]) as db:assert db.execute('PRAGMA user_version').fetchone()[0]==version

def test_jobicy_resume_dedup_and_credit(monkeypatch,store):
    sid=register(store,'jobicy','remote',True)
    def provider(url,kwargs):
        q=parse_qs(urlsplit(url).query);assert not kwargs
        return {'jobs':[jobicy(1),jobicy(2)] if 'cursor' not in q else [jobicy(2),jobicy(3)],'hasMore':'cursor' not in q,'nextCursor':'cursor +/?' if 'cursor' not in q else None}
    calls=serve(monkeypatch,provider)
    first=scan(store,sid);assert first['new_unique_jobs']==2 and not first['coverage_complete']
    due(store);second=scan(store,sid);assert second['inserted']==1 and second['updated']==1 and second['coverage_complete']
    assert parse_qs(urlsplit(calls[1][0]).query)['cursor']==['cursor +/?']
    assert store.summary()['total_jobs']==3
    row=store.jobs()[0];assert row['attribution']=='Jobicy' and row['salary']=='1 2 EUR year' and 'bad()' not in row['description']
    h=health(store)[0];assert h['last_completed_at'] and h['checkpoint_saved_at'] and h['last_metrics']['new_unique_jobs']==1

def test_jobicy_cursor_expiry_no_network(monkeypatch,store):
    sid=register(store,'jobicy','remote',True)
    with store.connect() as db:db.execute('INSERT INTO source_checkpoints VALUES(?,?,?)',(sid,json.dumps({'cursor':'old','started':0}), '2020-01-01'))
    calls=serve(monkeypatch,lambda u,k:pytest.fail('No expired cursor request'))
    with pytest.raises(ValueError):scan(store,sid)
    assert not calls and checkpoint(store,sid)['cursor']=='old'
    reset(store,sid);assert checkpoint(store,sid) is None
    with pytest.raises(ValueError,match='cooldown'):scan(store,sid)

@pytest.mark.parametrize('domain,identifier',[('www.arbeitnow.com','de'),('www.arbeitnow.co.uk','uk')])
def test_arbeitnow_pages_derive_fixed_host(monkeypatch,store,domain,identifier):
    sid=register(store,'arbeitnow',identifier,True)
    def provider(url,kwargs):
        assert urlsplit(url).hostname==domain
        page=int(parse_qs(urlsplit(url).query)['page'][0]);return {'data':[ar(page)],'links':{'next':'https://evil.example/private?page=2' if page==1 else None}}
    calls=serve(monkeypatch,provider)
    assert scan(store,sid)['inserted']==1;due(store);assert scan(store,sid)['coverage_complete']
    assert len(calls)==2 and store.summary()['total_jobs']==2
    assert 'remote flag: True' in store.jobs()[0]['description']

def test_arbeitnow_bad_next_rolls_back(monkeypatch,store):
    sid=register(store,'arbeitnow','de',True);serve(monkeypatch,lambda u,k:{'data':[ar()],'links':{'next':'https://example.com/?page=1'}})
    with pytest.raises(ValueError):scan(store,sid)
    assert not checkpoint(store,sid) and not store.jobs()

def test_usajobs_missing_auth_fails_without_request(monkeypatch,store):
    monkeypatch.delenv('USAJOBS_API_KEY',raising=False);monkeypatch.delenv('USAJOBS_USER_AGENT',raising=False)
    sid=register(store,'usajobs','data science',True);calls=serve(monkeypatch,lambda u,k:pytest.fail('Must not request'))
    with pytest.raises(ValueError):scan(store,sid)
    assert not calls and not checkpoint(store,sid)

def test_usajobs_auth_paging_sanitization(monkeypatch,store):
    monkeypatch.setenv('USAJOBS_API_KEY','private-key');monkeypatch.setenv('USAJOBS_USER_AGENT','owner@example.org')
    sid=register(store,'usajobs','data science',True)
    def provider(url,kwargs):
        assert urlsplit(url).hostname=='data.usajobs.gov';assert kwargs['credentials']['Authorization-Key']=='private-key'
        q=parse_qs(urlsplit(url).query);page=int(q['Page'][0]);assert q['Keyword']==['data science']
        return {'SearchResult':{'SearchResultCountAll':51,'SearchResultItems':[{'MatchedObjectDescriptor':{'PositionTitle':'Analyst','OrganizationName':'Agency','PositionURI':f'https://example.com/jobs/{page}','ApplicationCloseDate':'2026-11-01','UserArea':{'Details':{'Requirements':'Citizenship required'}}}}]}}
    serve(monkeypatch,provider);assert scan(store,sid)['bounded_selection'];due(store);assert scan(store,sid)['coverage_complete']
    assert 'Citizenship required' in store.jobs()[0]['description']
    with store.connect() as db:
        payload='\n'.join(str(tuple(x)) for table in ('runs','audit','source_checkpoints','sources') for x in db.execute(f'SELECT * FROM {table}'))
    assert 'private-key' not in payload and 'owner@example.org' not in payload

def hn_root():return {'type':'story','title':'Ask HN: Who is hiring? (October 2026)','kids':list(range(101,113))}

def test_hn_review_only_resume_no_people(monkeypatch,store):
    sid=register(store,'hn','100',True)
    def provider(url,kwargs):
        n=int(url.rsplit('/',1)[1].split('.')[0]);assert '/user/' not in url
        return hn_root() if n==100 else {'type':'comment','parent':100,'by':'DO_NOT_PERSIST_AUTHOR','text':'Example | Python Engineer | Remote<p>Apply at https://example.com/jobs/1</p>','time':1700000000}
    calls=serve(monkeypatch,provider);a=scan(store,sid);assert a['staged']==10 and a['new_unique_jobs']==0
    assert a['bounded_selection'] and store.summary()['total_jobs']==0
    due(store);b=scan(store,sid);assert b['staged']==2 and b['coverage_complete'] and len(calls)==14
    with store.connect() as db:
        records=db.execute('SELECT * FROM discovery_items').fetchall();assert len(records)==12
        assert all('DO_NOT_PERSIST_AUTHOR' not in str(tuple(x)) for x in records)
        assert all(json.loads(x['extracted'])['classification']=='ambiguous' for x in records)
        assert all('we are hiring' not in x['body'] for x in records)

@pytest.mark.parametrize('title',['Ask HN: Who wants to be hired?','Other thread','Ask HN: Freelance?'])
def test_hn_reject_wrong_thread(monkeypatch,store,title):
    sid=register(store,'hn','100',True);serve(monkeypatch,lambda u,k:{'type':'story','title':title,'kids':[]})
    with pytest.raises(ValueError):scan(store,sid)
    assert not checkpoint(store,sid)

def test_hn_skips_deleted_and_jobseekers(monkeypatch,store):
    sid=register(store,'hn','100',True)
    def provider(url,kwargs):
        n=int(url.rsplit('/',1)[1].split('.')[0])
        return {'type':'story','title':'Ask HN: Who is hiring?','kids':[101,102]} if n==100 else {'deleted':True} if n==101 else {'type':'comment','parent':100,'text':'Looking for a job. Python engineer'}
    serve(monkeypatch,provider);result=scan(store,sid);assert result['skipped']==1 and not result['staged'] and checkpoint(store,sid)['seen']==[101,102]

def smart_root(n=12):return {'content':[{'id':str(i)} for i in range(1,n+1)],'totalFound':n}
def smart_detail(n):return {'name':'Engineer','applyUrl':f'https://example.com/jobs/{n}','company':{'name':'Example'}}

def test_smart_resume_without_refetching_first_details(monkeypatch,store):
    sid=register(store,'smartrecruiters','example',True)
    calls=serve(monkeypatch,lambda u,k:smart_root() if '?' in u else smart_detail(u.rsplit('/',1)[1]))
    assert scan(store,sid)['inserted']==10;due(store);r=scan(store,sid)
    assert r['inserted']==2 and r['coverage_complete'] and len(calls)==13
    assert checkpoint(store,sid)['pending']==[]

def test_smart_next_list_page(monkeypatch,store):
    sid=register(store,'smartrecruiters','example',True)
    with store.connect() as db:db.execute('INSERT INTO source_checkpoints VALUES(?,?,?)',(sid,json.dumps({'offset':100,'pending':[],'total':101}), '2020'))
    def provider(u,k):
        if '?' in u:
            assert parse_qs(urlsplit(u).query)['offset']==['100'];return {'content':[{'id':'101'}],'totalFound':101}
        return smart_detail(101)
    calls=serve(monkeypatch,provider);r=scan(store,sid);assert r['coverage_complete'] and len(calls)==2

@pytest.mark.parametrize('kind,identifier',[('jobicy','remote'),('arbeitnow','de'),('hn','100'),('smartrecruiters','example')])
def test_failed_completion_rolls_back_jobs_posts_checkpoint(monkeypatch,store,kind,identifier):
    sid=register(store,kind,identifier,True)
    with store.connect() as db:db.executescript("CREATE TRIGGER fail_run BEFORE UPDATE ON runs WHEN NEW.status IN ('success','partial') BEGIN SELECT RAISE(ABORT,'fixture'); END;")
    row={'body':'Role: Engineer\nCompany: Example','origin_url':'https://example.com/post','source_label':sid}
    payload=Collection([row],{'seen':[1]},{},True) if kind=='hn' else Collection({'jobs':[jobicy()]} if kind=='jobicy' else {'data':[ar()]} if kind=='arbeitnow' else {'content':[smart_detail(1)],'totalFound':1},{'page':2},{'coverage_complete':False,'bounded_selection':True})
    with pytest.raises(ValueError):scan(store,sid,transport=lambda s:payload)
    assert not store.jobs() and not checkpoint(store,sid)
    with store.connect() as db:assert db.execute('SELECT COUNT(*) FROM discovery_items').fetchone()[0]==0

def test_cancellation_keeps_checkpoint(monkeypatch,store):
    sid=register(store,'smartrecruiters','example',True);event=threading.Event()
    def provider(u,k):
        if '?' in u:return smart_root()
        event.set();return smart_detail(1)
    calls=serve(monkeypatch,provider);r=scan(store,sid,cancel_event=event)
    assert r['cancelled'] and len(calls)==2 and not checkpoint(store,sid) and not store.jobs()

@pytest.mark.parametrize('retry',['7200','Thu, 29 Oct 2099 00:00:00 GMT','invalid'])
def test_retry_gate_cannot_be_bypassed_by_reapproval(store,retry):
    a=register(store,'arbeitnow','de',True);register(store,'arbeitnow','uk',True)
    def fail(source): raise HTTPError(source.url,429,'do not persist',{'Retry-After':retry},None)
    with pytest.raises(ValueError):scan(store,a,transport=fail)
    b=register(store,'arbeitnow','uk',True)
    with pytest.raises(ValueError,match='Retry-After'):scan(store,b,transport=lambda s:pytest.fail('No quota bypass'))
    reset(store,b)
    with pytest.raises(ValueError,match='Retry-After'):scan(store,b,transport=lambda s:None)

def test_provider_wide_local_cooldown(store):
    a=register(store,'arbeitnow','de',True);b=register(store,'arbeitnow','uk',True)
    scan(store,a,transport=lambda s:{'data':[ar()]})
    with pytest.raises(ValueError,match='Provider-wide'):scan(store,b,transport=lambda s:None)
    assert health(store)[1]['next_allowed_at']

def test_batch_isolates_failure_and_measures_unique_contribution(store):
    a=register(store,'greenhouse','a',True);b=register(store,'lever','b',True);c=register(store,'ashby','c',True)
    def provider(source):
        if source.id==a:return {'jobs':[{'title':'Engineer','absolute_url':'https://example.com/same'}]}
        if source.id==b:raise RuntimeError('private header')
        return {'jobs':[{'isListed':True,'title':'Engineer','jobUrl':'https://example.com/same'},{'isListed':True,'title':'Other','jobUrl':'https://example.com/new'}]}
    results=batch(store,[a,b,c],transport=provider)['results']
    assert results[0]['result']['new_unique_jobs']==1 and 'error' in results[1]
    assert results[2]['result']['new_unique_jobs']==1 and results[2]['result']['existing_job_observations']==1
    assert store.summary()['total_jobs']==2 and 'private header' not in str(results)

@pytest.mark.parametrize('ids',[[],['a']*2,['a']*11,'all',[1]])
def test_batch_invalid_selection(store,ids):
    with pytest.raises(ValueError):batch(store,ids)

def test_batch_pre_cancel_no_calls(store):
    event=threading.Event();event.set()
    r=batch(store,['unknown'],event,transport=lambda s:pytest.fail('Cancelled'))
    assert r['cancelled'] and not r['results']

def test_reset_preserves_stored_jobs_and_approval(store):
    sid=register(store,'jobicy','remote',True);scan(store,sid,transport=lambda s:Collection({'jobs':[jobicy()]},{'cursor':'x'},{'bounded_selection':True}))
    before=health(store)[0];reset(store,sid);after=health(store)[0]
    assert before['approved']==after['approved'] and before['next_allowed_at']==after['next_allowed_at'] and len(store.jobs())==1

@pytest.mark.parametrize('url',['https://evil.example/api/Search','https://data.usajobs.gov/other','https://data.usajobs.gov.evil.example/api/Search'])
def test_credential_fixed_host_boundary(url):
    from jobhunter_app.network import get
    with pytest.raises(ValueError,match='restricted'):get(url,credentials={'User-Agent':'a','Authorization-Key':'b'})

@pytest.mark.parametrize('value',['x\r\nInjected: yes','é','x'*1001,''])
def test_credential_header_validation(value):
    from jobhunter_app.network import get
    with pytest.raises(ValueError,match='credential'):get('https://data.usajobs.gov/api/Search',credentials={'User-Agent':'a','Authorization-Key':value})

@pytest.mark.parametrize('kind,payload',[('jobicy',{'jobs':'bad','hasMore':False}),('jobicy',{'jobs':[],'hasMore':True,'nextCursor':None}),('arbeitnow',{'data':'bad'}),('smartrecruiters',{'content':'bad'}),('hn',{'type':'story','title':'Ask HN: Who is hiring?','kids':['bad']})])
def test_malformed_pages_no_checkpoint(monkeypatch,store,kind,payload):
    sid=register(store,kind,{'jobicy':'remote','arbeitnow':'de','smartrecruiters':'example','hn':'100'}[kind],True)
    serve(monkeypatch,lambda u,k:payload)
    with pytest.raises(ValueError):scan(store,sid)
    assert not checkpoint(store,sid) and not store.jobs()

def test_feed_completion_failure_rolls_back_review(store):
    sid=register(store,'feed','https://example.org/jobs.rss',True)
    with store.connect() as db:db.executescript("CREATE TRIGGER fail_feed BEFORE UPDATE ON runs WHEN NEW.status IN ('success','partial') BEGIN SELECT RAISE(ABORT,'fixture'); END;")
    content=b'<rss><channel><item><description>Role: Analyst\nCompany: Example</description></item></channel></rss>'
    with pytest.raises(ValueError):scan(store,sid,transport=lambda s:content)
    with store.connect() as db:assert db.execute('SELECT COUNT(*) FROM discovery_items').fetchone()[0]==0

def test_failed_authenticated_transport_redacts(store,monkeypatch):
    monkeypatch.setenv('USAJOBS_API_KEY','SENSITIVE_KEY');monkeypatch.setenv('USAJOBS_USER_AGENT','private@example.org')
    sid=register(store,'usajobs','engineer',True)
    def fail(*a,**kw):raise RuntimeError('SENSITIVE_KEY private@example.org')
    monkeypatch.setattr('jobhunter_app.network.get',fail)
    with pytest.raises(ValueError) as e:scan(store,sid)
    assert 'SENSITIVE' not in str(e.value)
    with store.connect() as db:
        assert 'SENSITIVE' not in '\n'.join(str(tuple(x)) for table in ('runs','audit','sources') for x in db.execute(f'SELECT * FROM {table}'))

def test_health_advisory_staleness_not_closure(store):
    sid=register(store,'greenhouse','example',True)
    scan(store,sid,transport=lambda s:{'jobs':[{'title':'Engineer','absolute_url':'https://example.com/job'}]})
    with store.connect() as db:db.execute("UPDATE sightings SET last_seen='2020-01-01'")
    row=health(store)[0];assert row['observations_older_than_30_days']==1
    assert 'not evidence' in row['coverage_warning'] and store.jobs()

def test_new_http_routes_security_and_no_implicit_collection(tmp_path):
    import http.client
    from threading import Thread
    from jobhunter_app.web import make_server
    store=Store(tmp_path/'web.db');server=make_server(store,0);thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    def request(method,path,data=None,headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=10)
        conn.request(method,path,body=json.dumps(data).encode() if data is not None else None,headers=headers or {})
        response=conn.getresponse();body=response.read();status=response.status;conn.close();return status,body
    try:
        assert request('GET','/api/source-directory?q=Python')[0]==200
        assert request('GET','/api/source-health')==(200,b'[]')
        assert request('POST','/api/source-reset',{'source_id':'unknown'})[0]==403
        html=request('GET','/')[1].decode();import re
        token=re.search(r'name="csrf-token" content="([^"]+)"',html).group(1)
        headers={'X-JobHunter-Token':token,'Content-Type':'application/json'}
        assert request('POST','/api/scan-batch',{'source_ids':[]},headers)[0]==400
        assert request('POST','/api/source-reset',{'source_id':'unknown'},headers)[0]==400
        assert not store.summary()['sources']
    finally:server.shutdown();server.server_close();thread.join(5)
