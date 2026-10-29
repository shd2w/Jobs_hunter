from threading import Event
import pytest
from filelock import FileLock
from jobhunter_app.sources import Source, register, scan, normalize, plain
from jobhunter_app.store import Store

@pytest.fixture
def store(tmp_path):return Store(tmp_path/'test.sqlite3')

PAYLOAD={'jobs':[{'id':1,'title':'Developer','absolute_url':'https://example.com/jobs/1','content':'<p>Python</p><script>bad()</script>','location':{'name':'Remote'}}]}

@pytest.mark.parametrize('kind,identifier',[('greenhouse','../bad'),('lever','https://evil.com'),('unknown','example'),('lever','x?query'),('lever','')])
def test_registry_rejects_arbitrary_urls(kind,identifier):
    with pytest.raises(ValueError):Source(kind,identifier)


def test_unapproved_never_contacts_network(store):
    sid=register(store,'greenhouse','example')
    def forbidden(source):pytest.fail('Network must not be called')
    with pytest.raises(ValueError):scan(store,sid,transport=forbidden)


def test_scan_normalizes_persists_and_tracks_health(store):
    sid=register(store,'greenhouse','example',True)
    result=scan(store,sid,transport=lambda _:PAYLOAD)
    assert result['inserted']==1
    assert store.jobs()[0]['description']=='Python'
    assert store.summary()['sources'][0]['health']=='success'
    assert store.summary()['recent_runs'][0]['status']=='success'
    with pytest.raises(ValueError,match='cooldown'):scan(store,sid,transport=lambda _:PAYLOAD)


def test_scan_failure_no_data_and_safe_error(store):
    sid=register(store,'lever','example',True)
    def fail(_):raise RuntimeError('secret-provider-body')
    with pytest.raises(ValueError):scan(store,sid,transport=fail)
    s=store.summary()
    assert s['total_jobs']==0 and s['recent_runs'][0]['status']=='failed'
    assert 'secret' not in s['sources'][0]['last_error']


def test_cancellation_before_ingest(store):
    sid=register(store,'greenhouse','example',True)
    event=Event();event.set()
    assert scan(store,sid,transport=lambda _:PAYLOAD,cancel_event=event)['cancelled']
    assert store.summary()['total_jobs']==0


def test_overlap_prevented(store):
    sid=register(store,'greenhouse','example',True)
    with FileLock(str(store.path)+'.scan.lock'):
        with pytest.raises(ValueError,match='active'):scan(store,sid,transport=lambda _:PAYLOAD)


def test_lever_normalization():
    s=Source('lever','example')
    rows=normalize(s,[{'text':'Engineer','hostedUrl':'https://example.com/jobs/2','descriptionPlain':'Python','lists':[{'content':'<li>SQL</li>'}],'categories':{'location':'Berlin'}}])
    assert rows[0]['description']=='Python\nSQL'
    assert s.url.startswith('https://api.lever.co/')


def test_partial_malformed_record(store):
    sid=register(store,'greenhouse','example',True)
    r=scan(store,sid,transport=lambda _:{'jobs':PAYLOAD['jobs']+[None]})
    assert r['invalid']==1 and r['inserted']==1
    assert store.summary()['sources'][0]['health']=='partial'


def test_quota_exhaustion_pauses_source_instead_of_retrying(store):
    from urllib.error import HTTPError
    sid=register(store,'greenhouse','example',True)
    def quota(_):raise HTTPError('https://boards-api.greenhouse.io',429,'rate limited',{'Retry-After':'3600'},None)
    with pytest.raises(ValueError):scan(store,sid,transport=quota)
    source=store.summary()['sources'][0]
    assert source['health']=='rate_limited' and source['approved']==0
    def forbidden(_):pytest.fail('Quota pause must prevent another request')
    with pytest.raises(ValueError):scan(store,sid,transport=forbidden)
