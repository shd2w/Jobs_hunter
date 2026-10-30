"""Disposable, offline failure recovery and truthful dashboard receipts."""
import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace
import pytest
from jobhunter_app.automatic import AutomaticDiscovery
from jobhunter_app.collection import Collection
from jobhunter_app.pagination import receipt
from jobhunter_app.provider_recovery import policy, http_status
from jobhunter_app.source_health import health, reset
from jobhunter_app.source_outcomes import outcome
from jobhunter_app.sources import Source, register, scan
from jobhunter_app.store import Store
from scanners.jobspy_scanner import JobSpyScanner, ProviderFailure
from tests.test_phase3_sources import due, serve

ROW={'title':'Software Engineer','company':'Example','url':'https://example.com/jobs/repair',
     'description':'Python','location':'Remote'}

@pytest.mark.parametrize('text,expected',[('HTTP 403',403),('status code: 401',401),
    ('HTTP:429',429),('status code 429',429),('private error',None),('403 jobs',None)])
def test_status_evidence_not_arbitrary_digits(text,expected):
    assert http_status(text)==expected

@pytest.mark.parametrize('code,category,delay',[(403,'access_denied',21600),
    (401,'access_denied',21600),(429,'rate_limited',3600),(None,'provider_failure',3600)])
def test_provider_policy(code,category,delay):
    assert policy('jobspy_bayt',code)['recovery_category']==category
    assert policy('jobspy_bayt',code)['retry_delay_seconds']==delay
    assert policy('jobspy_bayt',code,99)['retry_delay_seconds']==min(86400,delay*16)
    assert policy('jobspy_google',code)['recovery_category']=='upstream_unavailable'

@pytest.mark.parametrize('code', [401,403,429])
def test_jobspy_failure_gates_repeats_without_deleting_progress_or_approval(tmp_path,code):
    store=Store(tmp_path/'app.db');sid=register(store,'jobspy_bayt','configured',True)
    with store.connect() as db:
        db.execute('INSERT INTO source_checkpoints VALUES(?,?,?)',(sid,json.dumps({'search_index':7,'page':1}),'2026-01-01T00:00:00+00:00'))
    calls=[]
    def denied(source):calls.append(source.id);raise ProviderFailure({'bayt':f'HTTP {code}'})
    for consecutive in range(1,7):
        with pytest.raises(ValueError):scan(store,sid,transport=denied,mirror_legacy=False)
        item=health(store)[0];m=item['last_metrics']
        assert item['approved'] and m['http_status']==code and m['pagination']['failed']
        assert m['consecutive_failures']==consecutive
        assert datetime.fromisoformat(item['next_allowed_at'])>datetime.now(timezone.utc)
        assert 'Provider retry/backoff' in item['wait_reason']
        assert m['retry_delay_seconds']==policy('jobspy_bayt',code,consecutive)['retry_delay_seconds']
        with store.connect() as db:
            assert json.loads(db.execute('SELECT data FROM source_checkpoints').fetchone()[0])['page']==1
        before=len(calls)
        with pytest.raises(ValueError,match='gate'):scan(store,sid,transport=denied,mirror_legacy=False)
        assert len(calls)==before
        # Expire test gates only. Real users cannot bypass them with reset.
        with store.connect() as db:db.execute('DELETE FROM provider_gates');db.execute('UPDATE sources SET last_run=NULL')
    reset(store,sid)
    assert health(store)[0]['approved']


def test_prior_longer_gate_is_never_shortened(tmp_path):
    from jobhunter_app.source_health import retry_gate
    store=Store(tmp_path/'app.db')
    with store.connect() as db:
        db.execute('INSERT INTO provider_gates VALUES(?,?)',('jobspy_bayt','2099-01-01T00:00:00+00:00'))
        retry_gate(db,'jobspy_bayt','',21600)
        assert db.execute('SELECT not_before FROM provider_gates').fetchone()[0].startswith('2099')

@pytest.mark.parametrize('metrics,code',[
    ({'received':0,'new_unique_jobs':0,'existing_job_observations':0},'empty_response'),
    ({'received':12,'new_unique_jobs':0,'existing_job_observations':12},'existing_only'),
    ({'received':10,'raw_received':15,'new_unique_jobs':2,'existing_job_observations':8,'rejected_title':5},'new_records'),
    ({'received':0,'raw_received':15,'new_unique_jobs':0,'existing_job_observations':0,'rejected_title':15},'filtered'),
    ({'received':1,'new_unique_jobs':0,'existing_job_observations':0,'invalid':1},'invalid_records'),
    ({},'unknown'),({'error':'denied'},'failed')])
def test_exact_response_classification(metrics,code):assert outcome(metrics)['code']==code

@pytest.mark.parametrize('kind', ['remoteok','weworkremotely'])
def test_snapshot_does_not_claim_whole_source_exhausted(kind):
    p=receipt(Source(kind,'remote'),Collection([],{'complete':True},{'coverage_complete':True}))
    assert p['response_mode']=='snapshot' and 'Current feed response processed' in p['message']
    assert p['source_exhausted'] is None and p['has_next_page'] is None
    assert not p['continuation_available'] and p['continuation_unknown']


def test_remotive_actual_fetch_duplicates_receipt_persisted_and_dashboard(tmp_path,monkeypatch):
    store=Store(tmp_path/'app.db');sid=register(store,'remotive','remote',True)
    monkeypatch.setattr('jobhunter_app.automatic.STARTERS',(('remotive','remote'),))
    serve(monkeypatch,lambda u,k:{'jobs':[{'title':ROW['title'],'company_name':'Example',
          'url':ROW['url'],'description':'Python','candidate_required_location':'Worldwide'}]})
    first=scan(store,sid,mirror_legacy=False);due(store)
    second=scan(store,sid,mirror_legacy=False)
    assert first['outcome']['code']=='new_records'
    assert second['outcome']['code']=='existing_only' and second['outcome']['existing']==1
    assert second['pagination']['response_mode']=='snapshot'
    assert health(store)[0]['last_metrics']['outcome']==second['outcome']
    a=AutomaticDiscovery(store);source=next(s for s in a.status()['sources'] if s['id']==sid)
    assert source['outcome']==second['outcome'] and source['last_attempt_status']=='success'


def test_invalid_snapshot_not_recorded_as_empty_success(tmp_path,monkeypatch):
    store=Store(tmp_path/'app.db');sid=register(store,'remotive','remote',True)
    serve(monkeypatch,lambda u,k:{'error':'not jobs'})
    with pytest.raises(ValueError):scan(store,sid,mirror_legacy=False)
    assert health(store)[0]['last_attempt_status']=='failed'


def test_partial_provider_errors_stay_partial(tmp_path):
    store=Store(tmp_path/'app.db');sid=register(store,'jobspy_indeed','configured',True)
    result=scan(store,sid,transport=lambda s:Collection([ROW],{},
        {'provider_errors':{'indeed':'detail failure'},'bounded_selection':False}),mirror_legacy=False)
    assert result['status']=='partial' and health(store)[0]['health']=='partial'


def test_shared_publisher_cooldown_is_not_an_html_failure(tmp_path):
    store=Store(tmp_path/'app.db');native=register(store,'arbeitnow','de',True)
    html=register(store,'scrapling_arbeitnow','de',True)
    scan(store,native,transport=lambda s:Collection({'data':[],'links':{'next':None}}, {},{}),mirror_legacy=False)
    item=next(s for s in health(store) if s['id']==html)
    assert 'Shared publisher' in item['wait_reason'] and item['last_attempt_status'] is None

@pytest.mark.parametrize('code', [401,403,429])
def test_legacy_stops_denied_provider_only_and_keeps_other_queries(monkeypatch,code):
    scanner=JobSpyScanner({});scanner.searches=[{'sites':['bayt','indeed'],'term':str(i),'location':'Germany'} for i in range(3)]
    calls=[]
    def search(search):
        calls.append(search);scanner.last_errors={'bayt':f'HTTP {code}'} if 'bayt' in search['sites'] else {}
        return [SimpleNamespace()]  # Jobs only collected here; not persisted.
    async def no_sleep(*a):pass
    monkeypatch.setattr(scanner,'_run_search',search);monkeypatch.setattr('scanners.jobspy_scanner.asyncio.sleep',no_sleep)
    result=asyncio.run(scanner.scan())
    assert calls[0]['sites']==['bayt','indeed'] and all(s['sites']==['indeed'] for s in calls[1:])
    assert len(result.jobs)==3 and result.errors and result.attempts[1]['deferred_providers']['bayt']
    assert len(scanner.searches)==3  # Registry never changed.


def test_all_failed_legacy_query_is_deferred_not_empty_success(monkeypatch):
    scanner=JobSpyScanner({});scanner.searches=[{'sites':['bayt'],'term':str(i)} for i in range(3)]
    calls=[]
    def fail(search):
        calls.append(search);scanner.last_errors={'bayt':'HTTP 403'};raise ProviderFailure(scanner.last_errors)
    async def no_sleep(*a):pass
    monkeypatch.setattr(scanner,'_run_search',fail);monkeypatch.setattr('scanners.jobspy_scanner.asyncio.sleep',no_sleep)
    result=asyncio.run(scanner.scan())
    assert len(calls)==1 and [a['status'] for a in result.attempts]==['failed','deferred','deferred']
    assert result.errors and not result.jobs


def test_cli_and_http_snapshot_outcomes_are_identical(tmp_path,monkeypatch,capsys):
    import time
    from threading import Thread
    import run_local
    from jobhunter_app.web import make_server
    from tests.test_web_local import request,token
    stores=[Store(tmp_path/(x+'.db')) for x in ('cli','http')]
    ids=[register(s,'remotive','remote',True) for s in stores]
    serve(monkeypatch,lambda u,k:{'jobs':[{'title':ROW['title'],'company_name':'Example',
          'url':ROW['url'],'description':'Python','candidate_required_location':'Worldwide'}]})
    server=make_server(stores[1],0);thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    web=(stores[1],server)
    try:
        for expected in ('new_records','existing_only'):
            assert run_local.main(['--db',str(stores[0].path),'scan',ids[0]])==0
            cli=json.loads(capsys.readouterr().out)
            assert request(web,'POST','/api/scan',{'source_id':ids[1]},{'X-JobHunter-Token':token(web)})[0]==200
            for _ in range(200):
                task=json.loads(request(web,'GET','/api/task')[2])
                if not task['running']:break
                time.sleep(.01)
            assert not task['running'] and not task['error'] and task['status']=='success'
            http=task['result']
            assert cli['outcome']==http['outcome'] and cli['outcome']['code']==expected
            assert cli['pagination']==http['pagination']
            for s in stores:due(s)
    finally:
        server.shutdown();server.server_close();thread.join(3)
