"""Primary Scrapling engine contracts; actual parsing, fixture transport, no network."""
import asyncio
import json
from threading import Event
from types import SimpleNamespace
from urllib.error import HTTPError
import pytest
pytest.importorskip('scrapling')
from jobhunter_app import scrapling_engine as engine
from jobhunter_app.sources import Source,register,scan,fetch
from jobhunter_app.store import Store,dump,now
from jobhunter_app.source_health import health,reset
from jobhunter_app.automatic import AutomaticDiscovery,configure,KEY,SEED_KEY,SEED_REVISION

ORIGIN='https://jobicy.com'
DETAILS=[ORIGIN+f'/jobs/{i}-software-engineer' for i in range(1,6)]
LISTING=(''.join(f'<a href="{url}">Job</a>' for url in DETAILS)+'<a rel="next" href="/jobs/page/2">Next</a>').encode()
ROBOTS=b'User-agent: *\nAllow: /\nCrawl-delay: 1\n'

def detail(url):
    data={'@context':'https://schema.org','@type':'JobPosting','title':'Software Engineer',
          'hiringOrganization':{'name':'Example'},'description':'<p>Python required.</p>',
          'url':url,'jobLocationType':'TELECOMMUTE','applicantLocationRequirements':[{'name':'Germany'}],
          'datePosted':'2026-10-29','employmentType':['FULL_TIME'],
          'baseSalary':{'currency':'EUR','value':{'minValue':100,'maxValue':200,'unitText':'DAY'}}}
    return ('<html><script type="application/ld+json">'+json.dumps(data)+'</script></html>').encode()

@pytest.fixture
def getter(monkeypatch):
    calls=[]
    def get(url,accept='text/html',**kwargs):
        calls.append(url)
        if url.endswith('/robots.txt'):return ROBOTS,'text/plain'
        if url==ORIGIN+'/jobs':return LISTING,'text/html'
        if url==ORIGIN+'/jobs/page/2':return b'<a href="/jobs/6-software-engineer">Job</a>','text/html'
        return detail(url),'text/html'
    monkeypatch.setattr('jobhunter_app.scrapling_transport.get',get)
    monkeypatch.setattr(engine.time,'sleep',lambda *_:None)
    return calls,get


def test_actual_scrapling_discovery_fields_and_three_step_continuation(getter):
    calls,get=getter;source=Source('scrapling_jobicy','remote')
    first=engine.collect(source,getter=get)
    assert first.metrics['engine']=='scrapling' and first.metrics['requests']==5
    assert len(first.payload)==3 and len(first.checkpoint['pending'])==2
    assert first.payload[0]['location']=='Remote · Germany'
    assert first.payload[0]['salary']=='EUR 100-200 DAY'
    assert first.payload[0]['employment_type']=='FULL_TIME'
    assert first.payload[0]['description']=='Python required.'
    second=engine.collect(source,first.checkpoint,getter=get)
    assert len(second.payload)==2 and second.metrics['requests']==3
    assert second.checkpoint['page']==ORIGIN+'/jobs/page/2'
    third=engine.collect(source,second.checkpoint,getter=get)
    assert len(third.payload)==1 and third.checkpoint['complete']
    assert not third.metrics['coverage_complete']  # No whole-site claim.
    assert calls.count(ORIGIN+'/jobs')==1
    assert len(set(x for x in calls if '/jobs/' in x and '/page/' not in x))==6


@pytest.mark.parametrize('url',[
 'https://127.0.0.1/jobs/1-test','http://jobicy.com/jobs/1-test',
 'https://jobicy.com.evil.test/jobs/1-test','https://jobicy.com:443/jobs/1-test',
 'https://user:secret@jobicy.com/jobs/1-test','https://jobicy.com/jobs/1-test?token=secret',
 'https://jobicy.com/jobs/1-test#fragment','https://jobicy.com/jobs/%2fprivate',
 'https://jobicy.com/jobs/../account', 'https://jobicy.com/dashboard-page'])
def test_scope_rejects_unsafe_or_account_paths(url):
    with pytest.raises(ValueError):engine.safe_url('scrapling_jobicy',url,True)


def test_bad_next_page_and_unstructured_details_fail_closed():
    with pytest.raises(ValueError):engine.listing('scrapling_jobicy',b'<a rel="next" href="https://127.0.0.1/private">Next</a>',ORIGIN+'/jobs')
    with pytest.raises(ValueError,match='No publisher JobPosting'):engine.postings('scrapling_jobicy',b'<html>Unstructured vacancy</html>',DETAILS[0])
    with pytest.raises(ValueError,match='layout changed'):engine.listing('scrapling_jobicy',b'<html>No recognized jobs</html>',ORIGIN+'/jobs')


def test_robots_disallow_and_challenge_never_imported(getter):
    calls,get=getter
    def denied(url,*args,**kwargs):return (b'User-agent: *\nDisallow: /jobs\n','text/plain') if url.endswith('robots.txt') else get(url,*args,**kwargs)
    with pytest.raises(engine.AccessBlocked):engine.collect(Source('scrapling_jobicy','remote'),getter=denied)
    assert not calls
    with pytest.raises(engine.AccessBlocked):engine.selector(b'<html>Verify you are human</html>')


@pytest.mark.parametrize('state',[{'complete':'invalid'},{'pending':['https://127.0.0.1/private']},{'index':True},{'index':21},{'pending':'invalid'},{'visited':['https://evil.test/jobs']},{'page':'https://jobicy.com/my-account/'}])
def test_corrupt_checkpoint_no_request(getter,state):
    calls,get=getter
    with pytest.raises(ValueError):engine.collect(Source('scrapling_jobicy','remote'),state,getter=get)
    assert not calls


def test_production_intake_saves_checkpoint_and_mirrors_legacy(getter,tmp_path):
    store=Store(tmp_path/'jobhunter.sqlite3');identity=register(store,'scrapling_jobicy','remote',True)
    result=scan(store,identity)
    assert result['inserted']==3 and result['engine']=='scrapling'
    assert result['legacy_pipeline']['passed_filters']==3
    assert store.summary()['total_jobs']==3
    with store.connect() as db:state=json.loads(db.execute('SELECT data FROM source_checkpoints WHERE source_id=?',(identity,)).fetchone()[0])
    assert len(state['pending'])==2
    with pytest.raises(ValueError,match='cooldown'):scan(store,identity)


def test_atomic_failure_retains_existing_jobs_and_checkpoint(getter,monkeypatch,tmp_path):
    calls,get=getter;store=Store(tmp_path/'jobhunter.sqlite3');identity=register(store,'scrapling_jobicy','remote',True)
    old={'page':ORIGIN+'/jobs','pending':[DETAILS[0]],'index':1,'visited':[]}
    with store.connect() as db:db.execute('INSERT INTO source_checkpoints VALUES(?,?,?)',(identity,dump(old),now()))
    store.ingest([{'title':'Keep','company':'Private','url':'https://example.com/keep'}])
    def failed(url,*args,**kwargs):
        if url==DETAILS[0]:raise HTTPError(url,403,'Denied',{},None)
        return get(url,*args,**kwargs)
    monkeypatch.setattr('jobhunter_app.scrapling_transport.get',failed)
    with pytest.raises(ValueError):scan(store,identity)
    with store.connect() as db:
        assert json.loads(db.execute('SELECT data FROM source_checkpoints').fetchone()[0])==old
        assert db.execute('SELECT approved FROM sources').fetchone()[0]==0
    assert store.summary()['total_jobs']==1


@pytest.mark.parametrize('first,second',[('scrapling_jobicy','jobicy'),('jobicy','scrapling_jobicy'),('scrapling_arbeitnow','arbeitnow'),('arbeitnow','scrapling_arbeitnow')])
def test_native_and_scrapling_share_publisher_cooldown(tmp_path,first,second):
    store=Store(tmp_path/'jobhunter.sqlite3');identifier='de' if 'arbeitnow' in first else 'remote'
    a=register(store,first,identifier,True);b=register(store,second,identifier,True)
    with store.connect() as db:db.execute('UPDATE sources SET last_run=? WHERE id=?',(now(),a))
    with pytest.raises(ValueError,match='Provider-wide'):scan(store,b)
    assert all(x['next_allowed_at'] for x in health(store))


def test_429_pauses_shared_publisher_and_reset_cannot_bypass_gate(tmp_path):
    store=Store(tmp_path/'jobhunter.sqlite3');a=register(store,'scrapling_jobicy','remote',True);b=register(store,'jobicy','remote',True)
    def limited(source):raise HTTPError(source.url,429,'Quota',{'Retry-After':'7200'},None)
    with pytest.raises(ValueError):scan(store,a,transport=limited)
    with store.connect() as db:
        assert all(not x[0] for x in db.execute('SELECT approved FROM sources'))
        assert db.execute('SELECT kind FROM provider_gates').fetchone()[0]=='jobicy'
    reset(store,a);register(store,'jobicy','remote',True)
    with pytest.raises(ValueError,match='Retry-After'):scan(store,b)


def test_cancel_never_advances_checkpoint(getter,tmp_path):
    store=Store(tmp_path/'jobhunter.sqlite3');identity=register(store,'scrapling_jobicy','remote',True)
    cancel=Event();cancel.set()
    result=scan(store,identity,cancel_event=cancel)
    assert result['cancelled'] and store.summary()['total_jobs']==0
    with store.connect() as db:assert db.execute('SELECT count(*) FROM source_checkpoints').fetchone()[0]==0


def test_default_scheduler_primary_engine_and_missing_runtime_is_visible(getter,monkeypatch,tmp_path):
    from jobhunter_app.scrapling_transport import ScraplingRuntimeMissing
    monkeypatch.setattr('jobhunter_app.automatic.STARTERS',(('scrapling_jobicy','remote'),))
    store=Store(tmp_path/'jobhunter.sqlite3');automatic=AutomaticDiscovery(store);automatic.cycle()
    assert store.summary()['total_jobs']==3
    assert automatic.status()['sources'][0]['engine']=='scrapling'
    assert 'Scrapling' in automatic.status()['sources'][0]['label']
    missing=Store(tmp_path/'missing'/'jobhunter.sqlite3');identity=register(missing,'scrapling_jobicy','remote',True)
    def absent(*a,**kw):raise ScraplingRuntimeMissing('fixture')
    monkeypatch.setattr('jobhunter_app.scrapling_transport.get',absent)
    with pytest.raises(ValueError,match='runtime missing'):scan(missing,identity)
    assert health(missing)[0]['last_metrics']['failure_code']=='scrapling_runtime_missing'


def test_v2_seed_upgrade_preserves_legacy_sources_and_user_pause(tmp_path):
    store=Store(tmp_path/'jobhunter.sqlite3');store.save_profile({'name':'Keep','skills':[],'facts':[]})
    identity=register(store,'scrapling_jobicy','remote',False)
    with store.connect() as db:
        db.execute('INSERT INTO workflow_settings VALUES(?,?,?)',('default',dump({KEY:{'version':1,'enabled':False},SEED_KEY:2}),now()))
    configure(store)
    with store.connect() as db:
        assert not db.execute('SELECT approved FROM sources WHERE id=?',(identity,)).fetchone()[0]
        settings=json.loads(db.execute('SELECT data FROM workflow_settings').fetchone()[0])
    assert settings[SEED_KEY]==SEED_REVISION and not settings[KEY]['enabled']


def test_legacy_base_scanner_uses_same_production_engine_and_dry_run_is_noop(getter,tmp_path):
    from scanners.scrapling_scanner import ScraplingScanner
    result=asyncio.run(ScraplingScanner({'scrapling_sources':['scrapling_jobicy']},tmp_path).scan())
    assert result.job_count==3 and not result.errors
    assert all(j.source=='scrapling_jobicy:remote' for j in result.jobs)
    calls=getter[0];before=len(calls)
    dry=asyncio.run(ScraplingScanner({},tmp_path/'dry',True).scan())
    assert not dry.jobs and len(calls)==before and not (tmp_path/'dry').exists()


def test_full_cli_merge_owns_legacy_write_once(getter,tmp_path,monkeypatch):
    from scanners.scrapling_scanner import ScraplingScanner
    from scanners.bridge import PipelineBridge
    result=asyncio.run(ScraplingScanner({'scrapling_sources':['scrapling_jobicy']},tmp_path).scan())
    assert not (tmp_path/'pipeline.md').exists()
    summary=PipelineBridge({'title_filter':{'positive':['Software Engineer'],'negative':[]},'location_filter':{'allow':['Germany'],'block':[]}},tmp_path).process([result])
    # Original legacy company/title dedup intentionally collapses these three
    # fixture URLs. They were not already mirrored before this merge.
    assert summary['new_added']==1 and summary['duplicates']==2


def test_scrapling_only_master_cli_preserves_original_merge_without_jobspy(getter,tmp_path,monkeypatch):
    import run_scan
    from scanners.jobspy_scanner import JobSpyScanner
    async def forbidden(self):raise AssertionError('JobSpy must not run in Scrapling-only mode')
    monkeypatch.setattr(JobSpyScanner,'scan',forbidden)
    cfg={'scrapling_sources':['scrapling_jobicy'],'title_filter':{'positive':['Software Engineer'],'negative':[]},'location_filter':{'allow':['Germany'],'block':[]}}
    result=asyncio.run(run_scan.run_scan(config_override=cfg,data_dir=tmp_path,only_scrapling=True))
    assert result['total_found']==3 and result['new_added']==1
