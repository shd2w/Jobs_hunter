"""Browser contracts use fakes; real evidence lives in PHASE_4C_RESULTS.md."""
import json
import sys
import threading
from types import SimpleNamespace as NS
from urllib.error import HTTPError
import pytest
from jobhunter_app import board_browser as bb
from jobhunter_app.authorized_boards import AccessBlocked, collect, parse
from jobhunter_app.sources import Source, register, scan, catalog
from jobhunter_app.store import Store
from jobhunter_app.source_health import health

LISTING='https://wuzzuf.net/a/Jobs-in-Egypt'
DETAIL='https://wuzzuf.net/jobs/p/test-job'

def posting(url=DETAIL):
    return {'@type':'JobPosting','title':'Synthetic role','hiringOrganization':{'name':'Synthetic employer'},'description':'Python','url':url}
def html(x): return '<script type="application/ld+json">'+json.dumps(x)+'</script>'

@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.delenv('JOBHUNTER_AUTHORIZED_BOARD_TRANSPORT',raising=False)
    monkeypatch.delenv('JOBHUNTER_BOARD_BROWSER_CDP',raising=False)
    monkeypatch.setenv('JOBHUNTER_AUTHORIZED_BOARD_ROBOTS','skip')
    monkeypatch.setattr('jobhunter_app.authorized_boards.time.sleep',lambda _:None)

@pytest.mark.parametrize('value',[
 'https://127.0.0.1:9222','http://example.com:9222','http://127.0.0.2:9222',
 'ws://127.0.0.1:9222','http://127.0.0.1:80','http://127.0.0.1',
 'http://user:pass@127.0.0.1:9222','http://127.0.0.1:9222/secret',
 'http://127.0.0.1:9222?key=secret','http://127.0.0.1:9222#x',
 'http://127.0.0.1:99999','http://127.0.0.1:9222\n',
])
def test_endpoint_rejects_remote_or_secret(monkeypatch,value):
    monkeypatch.setenv('JOBHUNTER_BOARD_BROWSER_CDP',value)
    with pytest.raises(bb.BrowserError) as e:bb.endpoint()
    assert e.value.code=='endpoint_invalid' and 'secret' not in str(e.value)

@pytest.mark.parametrize('value',['http://127.0.0.1:9222','http://localhost:9222/','http://[::1]:9222'])
def test_endpoint_loopback(monkeypatch,value):
    monkeypatch.setenv('JOBHUNTER_BOARD_BROWSER_CDP',value);assert bb.endpoint()==value

def test_transport_default_and_invalid(monkeypatch):
    assert bb.transport_mode()=='http'
    monkeypatch.setenv('JOBHUNTER_AUTHORIZED_BOARD_TRANSPORT','auto')
    with pytest.raises(ValueError):bb.transport_mode()

def test_catalog_browser_units(monkeypatch):
    monkeypatch.setenv('JOBHUNTER_AUTHORIZED_BOARD_TRANSPORT','browser')
    rows={p['kind']:p for p in catalog()}
    assert rows['wuzzuf']['transport']=='browser' and rows['wuzzuf']['requests']==5
    assert 'additional requests' in rows['wuzzuf']['request_unit']
    assert 'transport' not in rows['lever']

class FakePage:
    def __init__(self):
        self.url=LISTING;self.main_frame=object();self.closed=False;self.status=200
        self.headers={'content-type':'text/html'};self.ready=True;self.visible='A public job'
        self.document=html(posting());self.callbacks={};self.waits=0;self.fail=None
    def on(self,name,fn):self.callbacks[name]=fn
    def route(self,pattern,fn):self.router=fn
    def goto(self,url,**kw):
        self.url=url
        if self.fail:raise self.fail
        return NS(status=self.status,headers=self.headers)
    def locator(self,_):return NS(inner_text=lambda **kw:self.visible)
    def evaluate(self,script,arg):return self.ready if script==bb.READY else self.document
    def wait_for_timeout(self,_):self.waits+=1;self.ready=True
    def close(self):self.closed=True

def client(page=None):
    b=bb.BrowserHTML('wuzzuf');b.page=page or FakePage();return b

def test_browser_readiness_and_metrics():
    p=FakePage();p.ready=False;b=client(p)
    body,typ=b.get(DETAIL)
    assert body==p.document.encode() and 'html' in typ and p.waits==1
    assert b.metrics()['top_level_navigations']==1
    assert 'additional requests' in b.metrics()['browser_resource_notice']

@pytest.mark.parametrize('status',[301,401,403,429,500])
def test_browser_http_no_fallback(status):
    p=FakePage();p.status=status;p.headers['retry-after']='3600';b=client(p)
    with pytest.raises(HTTPError) as e:b.get(DETAIL)
    assert e.value.code==status and e.value.headers['Retry-After']=='3600' and b.navigations==1

@pytest.mark.parametrize('message',['CAPTCHA','Verify you are human','Just a moment','Access denied'])
def test_browser_challenge_stops(message):
    p=FakePage();p.visible=message
    with pytest.raises(AccessBlocked):client(p).get(DETAIL)

def test_browser_cancel_no_navigation():
    b=client();b.cancel_event=threading.Event();b.cancel_event.set()
    with pytest.raises(InterruptedError):b.get(DETAIL)
    assert b.navigations==0

def test_browser_navigation_cap():
    b=client();b.navigations=6
    with pytest.raises(ValueError,match='budget'):b.get(DETAIL)

def test_browser_oversize():
    p=FakePage();p.document=None
    with pytest.raises(bb.BrowserError) as e:client(p).get(DETAIL)
    assert e.value.code=='response_too_large'

def test_browser_wrong_content():
    p=FakePage();p.headers['content-type']='application/json'
    with pytest.raises(bb.BrowserError) as e:client(p).get(DETAIL)
    assert e.value.code=='content_type'

def test_browser_rules_check():
    p=FakePage();p.headers['content-type']='text/plain';p.visible='User-agent: *\nAllow: /'
    body,typ=client(p).get('https://wuzzuf.net/robots.txt',max_bytes=256*1024)
    assert body.startswith(b'User-agent:') and typ=='text/plain'

def test_browser_readiness_deadline(monkeypatch):
    p=FakePage();p.ready=False;b=client(p);times=iter([0,61])
    monkeypatch.setattr(bb.time,'monotonic',lambda:next(times))
    with pytest.raises(bb.BrowserError) as e:b.get(DETAIL)
    assert e.value.code=='structured_data_timeout'

def test_browser_error_redaction():
    p=FakePage();p.fail=RuntimeError('secret cookie password')
    with pytest.raises(bb.BrowserError) as e:client(p).get(DETAIL)
    assert e.value.code=='navigation_failed' and 'secret' not in str(e.value)

@pytest.mark.parametrize('url,redirect',[(DETAIL,True),('https://evil.example/a/',False),('https://wuzzuf.net/login',False)])
def test_navigation_guard_before_redirect(url,redirect):
    b=client();calls=[]
    r=NS(url=url,frame=b.page.main_frame,redirected_from=object() if redirect else None,is_navigation_request=lambda:True)
    route=NS(request=r,abort=lambda:calls.append('abort'),continue_=lambda:calls.append('continue'))
    b._route(route)
    assert calls==['abort'] and b.violation

def test_browser_cleanup_disconnect_not_browser_close(monkeypatch):
    p=FakePage();actions=[]
    context=NS(new_page=lambda:p)
    browser=NS(contexts=[context],close=lambda:pytest.fail('Never close user browser'))
    driver=NS(stop=lambda:actions.append('disconnect'),chromium=NS(connect_over_cdp=lambda *a,**k:browser))
    monkeypatch.setitem(sys.modules,'playwright.sync_api',NS(sync_playwright=lambda:NS(start=lambda:driver)))
    with bb.BrowserHTML('wuzzuf') as b:assert b.page is p
    assert p.closed and actions==['disconnect']

def test_browser_missing_optional_runtime(monkeypatch):
    monkeypatch.setitem(sys.modules,'playwright.sync_api',None)
    with pytest.raises(bb.BrowserError) as e:bb.BrowserHTML('wuzzuf').__enter__()
    assert e.value.code=='runtime_missing'

def test_browser_connection_failure_sanitized(monkeypatch):
    actions=[]
    def fail(*a,**kw):raise RuntimeError('secret endpoint')
    driver=NS(stop=lambda:actions.append('disconnect'),chromium=NS(connect_over_cdp=fail))
    monkeypatch.setitem(sys.modules,'playwright.sync_api',NS(sync_playwright=lambda:NS(start=lambda:driver)))
    with pytest.raises(bb.BrowserError) as e:bb.BrowserHTML('wuzzuf').__enter__()
    assert e.value.code=='connection_failed' and 'secret' not in str(e.value)
    assert actions==['disconnect']

def test_jsonld_listitem_url_without_anchor():
    body=html({'@type':'ItemList','itemListElement':[{'@type':'ListItem','url':DETAIL}]}).encode()
    rows,links,nxt=parse('wuzzuf',body,LISTING)
    assert not rows and links==[DETAIL] and nxt is None

def test_browser_fetch_persists_continuation_no_http(monkeypatch,tmp_path):
    monkeypatch.setenv('JOBHUNTER_AUTHORIZED_BOARD_TRANSPORT','browser')
    monkeypatch.setattr('jobhunter_app.network.get',lambda *a,**kw:pytest.fail('No HTTP fallback'))
    urls=[DETAIL+str(n) for n in range(6)];calls=[]
    class Browser:
        def __init__(self,*a):pass
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def get(self,url,*a,**kw):
            calls.append(url)
            data={'@type':'ItemList','itemListElement':[{'@type':'ListItem','url':u} for u in urls]} if url==LISTING else posting(url)
            return html(data).encode(),'text/html'
        def metrics(self):return {'transport':'browser','top_level_navigations':len(calls),'browser_resource_requests_observed':len(calls)*10}
    monkeypatch.setattr(bb,'BrowserHTML',Browser)
    store=Store(tmp_path/'jobs.sqlite3');sid=register(store,'wuzzuf',LISTING,True)
    a=scan(store,sid);assert a['inserted']==4 and a['requests']==5 and a['pending_details']==2
    with pytest.raises(ValueError,match='cooldown'):scan(store,sid)
    with store.connect() as db:db.execute('UPDATE sources SET last_run=NULL')
    b=scan(store,sid);assert b['inserted']==2 and b['requests']==2 and calls.count(LISTING)==1
    assert store.summary()['total_jobs']==6
    with store.connect() as db:
        audit=' '.join(str(tuple(r)) for r in db.execute('SELECT * FROM audit'))
    assert 'browser' in audit

def test_browser_runtime_failure_no_commit(monkeypatch,tmp_path):
    monkeypatch.setenv('JOBHUNTER_AUTHORIZED_BOARD_TRANSPORT','browser')
    monkeypatch.setitem(sys.modules,'playwright.sync_api',None)
    store=Store(tmp_path/'jobs.sqlite3');sid=register(store,'wuzzuf',LISTING,True)
    with pytest.raises(ValueError,match='requirements-local-browser'):scan(store,sid)
    assert not store.jobs()
    with store.connect() as db:
        assert not db.execute('SELECT * FROM source_checkpoints').fetchone()
        r=db.execute('SELECT metrics FROM runs').fetchone();assert json.loads(r[0])['failure_code']=='runtime_missing'

def test_health_includes_board_provider_cooldown(tmp_path):
    store=Store(tmp_path/'jobs.sqlite3');a=register(store,'wuzzuf',LISTING,True)
    b=register(store,'wuzzuf','https://wuzzuf.net/a/IT-Jobs-in-Egypt',True)
    with store.connect() as db:db.execute('UPDATE sources SET last_run=? WHERE id=?',('2026-10-29T16:00:00+00:00',a))
    rows={r['id']:r for r in health(store)}
    assert rows[a]['next_allowed_at']==rows[b]['next_allowed_at']=='2026-10-29T17:00:00+00:00'
