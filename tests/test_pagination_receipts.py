"""Source metadata, committed resume, unknown limits and backend/UI contracts."""
import json
from threading import Event
from urllib.parse import parse_qs,urlsplit
import pytest
from jobhunter_app.collection import collect,Collection
from jobhunter_app.sources import Source,scan,register,POLICIES
from jobhunter_app.pagination import state,receipt
from jobhunter_app.source_health import health,batch
from jobhunter_app.store import Store
from tests.test_phase3_sources import jobicy,ar,checkpoint,due,serve

@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):monkeypatch.setattr('jobhunter_app.collection.time.sleep',lambda _:None)

@pytest.mark.parametrize('fields,phrase',[
    ({'has_next_page':True,'continuation_available':True},'Additional pages confirmed'),
    ({'page_limit_reached':True},'configured page limit'),
    ({'result_limit_reached':True},'further results have not been verified'),
    ({'has_next_page':False,'source_exhausted':True},'No additional pages reported'),
    ({},'Continuation information unavailable'),
    ({'failed':True},'Scan failed'),
    ({'cancelled':True},'Scan interrupted'),
    ({'partial':True},'partially completed'),
])
def test_receipt_messages_do_not_turn_limits_into_next_pages(fields,phrase):
    r=state(**fields);assert phrase in r['message']
    if not fields.get('has_next_page'):assert r['has_next_page'] is not True
    if 'source_exhausted' not in fields:assert r['source_exhausted'] is None


def test_jobicy_valid_cursor_resumes_and_explicit_end(monkeypatch,tmp_path):
    store=Store(tmp_path/'app.db');sid=register(store,'jobicy','remote',True)
    def provider(url,kw):
        cursor='cursor' in parse_qs(urlsplit(url).query)
        return {'jobs':[jobicy(2 if cursor else 1)],'hasMore':not cursor,'nextCursor':None if cursor else 'verified-cursor'}
    calls=serve(monkeypatch,provider)
    first=scan(store,sid,mirror_legacy=False)
    assert first['pagination']['has_next_page'] is True and first['pagination']['continuation_available']
    due(store);second=scan(store,sid,mirror_legacy=False)
    assert 'verified-cursor' in calls[1][0]
    assert second['pagination']['has_next_page'] is False and second['pagination']['source_exhausted'] is True
    assert health(store)[0]['pagination']==second['pagination']


def test_failed_next_page_keeps_only_committed_cursor(monkeypatch,tmp_path):
    store=Store(tmp_path/'app.db');sid=register(store,'jobicy','remote',True)
    serve(monkeypatch,lambda u,k:{'jobs':[jobicy()],'hasMore':True,'nextCursor':'verified-cursor'})
    scan(store,sid,mirror_legacy=False);saved=checkpoint(store,sid);due(store)
    def outage(*a,**k):raise TimeoutError('private timeout body')
    monkeypatch.setattr('jobhunter_app.network.get',outage)
    with pytest.raises(ValueError):scan(store,sid,mirror_legacy=False)
    assert checkpoint(store,sid)==saved
    r=health(store)[0]['pagination'];assert r['failed'] and r['has_next_page'] is None and not r['continuation_available']


def test_cancelled_next_page_does_not_advance(monkeypatch,tmp_path):
    store=Store(tmp_path/'app.db');sid=register(store,'jobicy','remote',True)
    serve(monkeypatch,lambda u,k:{'jobs':[jobicy()],'hasMore':True,'nextCursor':'verified-cursor'})
    scan(store,sid,mirror_legacy=False);saved=checkpoint(store,sid);due(store);event=Event()
    def cancelled(source):event.set();return Collection({'jobs':[jobicy(2)]},{'cursor':'wrong'})
    r=scan(store,sid,transport=cancelled,cancel_event=event,mirror_legacy=False)
    assert r['pagination']['cancelled'] and checkpoint(store,sid)==saved
    assert health(store)[0]['pagination']['cancelled']

@pytest.mark.parametrize('links,has_next,exhausted',[(None,None,None),({},None,None),({'next':None},False,True),({'next':'https://example.org/?page=2'},True,False)])
def test_arbeitnow_missing_metadata_is_not_last_page(monkeypatch,links,has_next,exhausted):
    payload={'data':[ar()]}
    if links is not None:payload['links']=links
    serve(monkeypatch,lambda u,k:payload)
    r=collect(Source('arbeitnow','de')).metrics['pagination']
    assert r['has_next_page'] is has_next and r['source_exhausted'] is exhausted


def test_known_total_confirms_more_and_pending_details_not_page(monkeypatch):
    def provider(u,k):
        if '/postings?' in u:return {'content':[{'id':str(i)} for i in range(12)],'totalFound':200}
        return {'id':u.rsplit('/',1)[-1]}
    serve(monkeypatch,provider)
    first=collect(Source('smartrecruiters','fixture'))
    r=first.metrics['pagination'];assert r['has_next_page'] is True and r['pending_details']==2
    second=collect(Source('smartrecruiters','fixture'),first.checkpoint)
    assert second.metrics['pagination']['pages_retrieved']==0 and second.metrics['pagination']['pending_details']==0


def test_jobspy_budget_not_more_pages(monkeypatch,tmp_path):
    from scanners.jobspy_scanner import JobSpyScanner
    from scanners.base import JobPosting
    from tests.test_runtime_queries import query
    store=Store(tmp_path/'app.db');sid=register(store,'jobspy_indeed','configured',True)
    monkeypatch.setitem(POLICIES['jobspy_indeed'],'cooldown',0)
    monkeypatch.setattr(JobSpyScanner,'_run_search',lambda *a:[JobPosting('Engineer','https://example.org/jobs/a','Fixture')])
    first=scan(store,sid,request=query(),mirror_legacy=False)['pagination']
    assert first['has_next_page'] is None and first['continuation_available'] and first['result_limit_reached']
    second=scan(store,sid,request=query(),mirror_legacy=False)['pagination']
    assert second['page_limit_reached'] and second['has_next_page'] is None and second['source_exhausted'] is None
    assert not second['continuation_available'] and 'Additional pages confirmed' not in second['message']


def test_injected_collection_cannot_establish_metadata_from_legacy_bool():
    r=receipt(Source('arbeitnow','de'),Collection({}, {'complete':True},{'coverage_complete':True}))
    assert r['has_next_page'] is None and r['source_exhausted'] is None


def test_batch_partial_failure_not_success(monkeypatch,tmp_path):
    store=Store(tmp_path/'app.db');a=register(store,'arbeitnow','de',True);b=register(store,'jobicy','remote',True)
    def transport(source):
        if source.kind=='arbeitnow':raise TimeoutError('private')
        return Collection({'jobs':[jobicy()]},{'complete':True},{'pagination':state(has_next_page=False,source_exhausted=True)})
    r=batch(store,[a,b],transport=transport)
    assert r['status']=='partial' and r['counts']['failed']==1 and store.summary()['total_jobs']==1
