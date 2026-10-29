"""Synthetic HTML only; never proof of a working live board integration."""
import json
import threading
from urllib.error import HTTPError
import pytest
from jobhunter_app.sources import Source,register,scan,catalog
from jobhunter_app.store import Store
from jobhunter_app.authorized_boards import collect,parse,safe_url,HOSTS

@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr('jobhunter_app.authorized_boards.time.sleep',lambda _:None)
    monkeypatch.setenv('JOBHUNTER_AUTHORIZED_BOARD_ROBOTS','check')

@pytest.fixture
def store(tmp_path): return Store(tmp_path/'test.sqlite3')

def listing(kind): return 'https://'+HOSTS[kind]+('/a/Jobs-in-Egypt' if kind=='wuzzuf' else '/jobs-in-egypt')
def detail(kind,n=1): return 'https://'+HOSTS[kind]+(f'/jobs/p/{n}-Python-Cairo' if kind=='wuzzuf' else f'/python-jobs-in-cairo-{n}-jid-{n}')
def posting(kind,n=1):
    return {'@context':'https://schema.org','@type':'JobPosting','title':'Python Engineer','url':detail(kind,n),'description':'<p>Python and SQL</p><script>evil()</script>','hiringOrganization':{'name':'Fixture Co'},'jobLocation':{'address':{'addressLocality':'Cairo','addressCountry':'EG'}},'datePosted':'2026-10-29'}
def html(value): return ('<html><script type="application/ld+json">'+json.dumps(value).replace('<',chr(92)+'u003c')+'</script></html>').encode()
def serve(monkeypatch, fn, rules=b'User-agent: *\nAllow: /\n'):
    calls=[]
    def get(url,*a,**kw):
        calls.append(url)
        if url.endswith('/robots.txt'): return rules,'text/plain'
        return fn(url),'text/html'
    monkeypatch.setattr('jobhunter_app.network.get',get);return calls

def due(store):
    with store.connect() as db: db.execute('UPDATE sources SET last_run=NULL')
def checkpoint(store,sid):
    with store.connect() as db:
        row=db.execute('SELECT data FROM source_checkpoints WHERE source_id=?',(sid,)).fetchone()
        return json.loads(row[0]) if row else None

@pytest.mark.parametrize('kind',HOSTS)
def test_structured_board_ingest_dedup_provenance(monkeypatch,store,kind):
    sid=register(store,kind,listing(kind),True)
    calls=serve(monkeypatch,lambda url:html({'@graph':[posting(kind),posting(kind)]}))
    result=scan(store,sid)
    assert result['inserted']==1 and result['requests']==2
    assert not result['coverage_complete'] and result['bounded_selection']
    assert result['listing_pass_exhausted'] and len(calls)==2
    job=store.jobs()[0]
    assert 'evil()' not in job['description'] and job['location']=='Cairo, EG' and job['attribution']
    due(store);assert scan(store,sid)['updated']==1 and store.summary()['total_jobs']==1

@pytest.mark.parametrize('kind',HOSTS)
def test_pending_detail_resume_and_next_page(monkeypatch,store,kind):
    sid=register(store,kind,listing(kind),True)
    next_url=listing(kind)+('?'+'start=1' if kind=='wuzzuf' else '?page=2')
    def response(url):
        if url==listing(kind):
            return (''.join(f'<a href="{detail(kind,n)}">job</a>' for n in range(1,7))+f'<a rel="next" href="{next_url}">Next</a>').encode()
        if url==next_url: return html(posting(kind,7))
        return html(posting(kind,int(url.rsplit('/',1)[1].split('-')[0]) if kind=='wuzzuf' else int(url.rsplit('-',1)[1])))
    calls=serve(monkeypatch,response)
    a=scan(store,sid);assert a['inserted']==4 and a['requests']==6
    assert len(checkpoint(store,sid)['pending'])==2
    due(store);b=scan(store,sid);assert b['inserted']==2 and b['requests']==3
    assert checkpoint(store,sid)['page']==next_url and calls.count(listing(kind))==1
    due(store);c=scan(store,sid);assert c['inserted']==1 and c['listing_pass_exhausted']
    assert store.summary()['total_jobs']==7

@pytest.mark.parametrize('url',[
 'http://wuzzuf.net/a/Jobs','https://evil.example/a/Jobs','https://wuzzuf.net:443/a/Jobs',
 'https://user@wuzzuf.net/a/Jobs','https://wuzzuf.net/login','https://wuzzuf.net/a/Jobs?q=python',
 'https://wuzzuf.net/a/Jobs?start=1&start=2','https://wuzzuf.net/a/../login',
 'https://wuzzuf.net/a/%2e%2e','https://wuzzuf.net/a/Jobs#section',
 'https://wuzzuf.net/a/Jobs?token=secret','https://wuzzuf.net/a/Jobs?start=99999'])
def test_reject_unsafe_configuration(url):
    with pytest.raises(ValueError): Source('wuzzuf',url)

def test_unapproved_no_network(monkeypatch,store):
    sid=register(store,'wuzzuf',listing('wuzzuf'));calls=serve(monkeypatch,lambda u:pytest.fail('no request'))
    with pytest.raises(ValueError,match='approved'):scan(store,sid)
    assert not calls

@pytest.mark.parametrize('rules',[b'User-agent: *\nDisallow: /\n',b'User-agent: JobHunter-Local\nDisallow: /\n'])
def test_robots_disallow(monkeypatch,store,rules):
    sid=register(store,'wuzzuf',listing('wuzzuf'),True);calls=serve(monkeypatch,lambda u:pytest.fail('no listing'),rules)
    with pytest.raises(ValueError):scan(store,sid)
    assert len(calls)==1 and not checkpoint(store,sid) and not store.jobs()

@pytest.mark.parametrize('body',[b'<h1>Verify you are human</h1>',b'<h1>CAPTCHA</h1>',b'<h1>Just a moment</h1>',b'<h1>Log in</h1>',b'<div>Changed layout</div>'])
def test_challenge_or_unknown_format_no_success(monkeypatch,store,body):
    sid=register(store,'wuzzuf',listing('wuzzuf'),True);serve(monkeypatch,lambda u:body)
    with pytest.raises(ValueError):scan(store,sid)
    assert not checkpoint(store,sid) and not store.jobs()

@pytest.mark.parametrize('code',[301,302,401,403,429,500])
def test_http_stop_no_retry_redacted(monkeypatch,store,code):
    sid=register(store,'wuzzuf',listing('wuzzuf'),True)
    def fail(url): raise HTTPError(url,code,'SENSITIVE BODY',{},None)
    calls=serve(monkeypatch,fail)
    with pytest.raises(ValueError):scan(store,sid)
    assert len(calls)==2 and not checkpoint(store,sid)
    with store.connect() as db: assert 'SENSITIVE' not in str([tuple(x) for x in db.execute('SELECT * FROM runs')])

@pytest.mark.parametrize('kind',HOSTS)
def test_evil_next_fails_transactionally(monkeypatch,store,kind):
    sid=register(store,kind,listing(kind),True)
    calls=serve(monkeypatch,lambda url:html(posting(kind))+b'<a rel="next" href="https://127.0.0.1/secret">next</a>')
    with pytest.raises(ValueError):scan(store,sid)
    assert len(calls)==2 and not store.jobs() and not checkpoint(store,sid)

def test_cancel_no_request(monkeypatch):
    event=threading.Event();event.set();calls=serve(monkeypatch,lambda u:pytest.fail('no request'))
    with pytest.raises(InterruptedError):collect(Source('wuzzuf',listing('wuzzuf')),cancel_event=event)
    assert not calls

def test_provider_cooldown_across_listings(monkeypatch,store):
    first=register(store,'wuzzuf',listing('wuzzuf'),True);second=register(store,'wuzzuf','https://wuzzuf.net/a/IT-Jobs-in-Egypt',True)
    calls=serve(monkeypatch,lambda u:html(posting('wuzzuf')));scan(store,first)
    with pytest.raises(ValueError,match='Provider-wide'):scan(store,second)
    assert len(calls)==2

def test_malformed_structured_row_reported(monkeypatch,store):
    sid=register(store,'wuzzuf',listing('wuzzuf'),True)
    bad=posting('wuzzuf',2);bad['title']=None
    serve(monkeypatch,lambda u:html([posting('wuzzuf'),bad]));r=scan(store,sid)
    assert r['inserted']==1 and r['invalid']==1

def test_detail_failure_preserves_committed_checkpoint(monkeypatch,store):
    sid=register(store,'wuzzuf',listing('wuzzuf'),True)
    old={'pending':[detail('wuzzuf',5)],'page':listing('wuzzuf'),'index':1,'next_page':None,'visited':[listing('wuzzuf')]}
    with store.connect() as db: db.execute('INSERT INTO source_checkpoints VALUES(?,?,?)',(sid,json.dumps(old),'2026-10-29'))
    serve(monkeypatch,lambda u:b'<div>changed page</div>')
    with pytest.raises(ValueError):scan(store,sid)
    assert checkpoint(store,sid)==old and not store.jobs()

@pytest.mark.parametrize('rules',[b'',b'<html>CAPTCHA</html>',b'User-agent: *\nRequest-rate: 1/60\nAllow: /\n',b'User-agent: *\nCrawl-delay: 60\nAllow: /\n'])
def test_unusable_or_slow_robots_fail_closed(monkeypatch,store,rules):
    sid=register(store,'wuzzuf',listing('wuzzuf'),True);calls=serve(monkeypatch,lambda u:pytest.fail('no listing'),rules)
    with pytest.raises(ValueError):scan(store,sid)
    assert len(calls)==1 and not checkpoint(store,sid)

def test_access_block_pauses_all_provider_sources(monkeypatch,store):
    sid=register(store,'wuzzuf',listing('wuzzuf'),True);register(store,'wuzzuf','https://wuzzuf.net/a/IT-Jobs-in-Egypt',True)
    serve(monkeypatch,lambda u:b'<h1>Verify you are human</h1>')
    with pytest.raises(ValueError,match='unapproved'):scan(store,sid)
    with store.connect() as db:
        assert all(not r['approved'] and r['health']=='access_blocked' for r in db.execute("SELECT * FROM sources WHERE kind='wuzzuf'"))

def test_transaction_failure_leaves_no_job_or_progress(monkeypatch,store):
    sid=register(store,'wuzzuf',listing('wuzzuf'),True);serve(monkeypatch,lambda u:html(posting('wuzzuf')))
    with store.connect() as db:db.execute("CREATE TRIGGER reject_board_completion BEFORE UPDATE ON runs WHEN NEW.status='partial' BEGIN SELECT RAISE(ABORT,'fixture'); END")
    with pytest.raises(ValueError):scan(store,sid)
    assert not store.jobs() and not checkpoint(store,sid)

def test_repeated_next_page_rejected(monkeypatch,store):
    sid=register(store,'wuzzuf',listing('wuzzuf'),True)
    serve(monkeypatch,lambda u:html(posting('wuzzuf'))+f'<a rel="next" href="{listing("wuzzuf")}">Next</a>'.encode())
    with pytest.raises(ValueError):scan(store,sid)
    assert not store.jobs() and not checkpoint(store,sid)


@pytest.mark.parametrize('kind',HOSTS)
def test_requested_default_skip_never_fetches_robots(monkeypatch,store,kind):
    monkeypatch.delenv('JOBHUNTER_AUTHORIZED_BOARD_ROBOTS',raising=False)
    sid=register(store,kind,listing(kind),True)
    calls=serve(monkeypatch,lambda u:html(posting(kind)),b'User-agent: *\nDisallow: /\n')
    r=scan(store,sid)
    assert calls==[listing(kind)] and r['inserted']==1
    assert r['robots_mode']=='skip' and r['robots_requests']==0 and r['requests']==1
    with store.connect() as db:
        audit=db.execute("SELECT details FROM audit WHERE event='authorized_board_robots_mode'").fetchone()
        assert json.loads(audit[0])['robots_mode']=='skip'

@pytest.mark.parametrize('code',[401,403,429])
def test_skip_retains_access_and_quota_pauses(monkeypatch,store,code):
    monkeypatch.setenv('JOBHUNTER_AUTHORIZED_BOARD_ROBOTS','skip')
    sid=register(store,'wuzzuf',listing('wuzzuf'),True)
    def fail(url):raise HTTPError(url,code,'Rejected',{},None)
    calls=serve(monkeypatch,fail)
    with pytest.raises(ValueError):scan(store,sid)
    assert calls==[listing('wuzzuf')]
    with store.connect() as db:assert not db.execute('SELECT approved FROM sources WHERE id=?',(sid,)).fetchone()[0]

def test_skip_does_not_skip_source_approval(monkeypatch,store):
    monkeypatch.setenv('JOBHUNTER_AUTHORIZED_BOARD_ROBOTS','skip')
    sid=register(store,'wuzzuf',listing('wuzzuf'),False)
    calls=serve(monkeypatch,lambda u:pytest.fail('Unapproved source'))
    with pytest.raises(ValueError):scan(store,sid)
    assert not calls

def test_invalid_mode_fails_without_network(monkeypatch):
    monkeypatch.setenv('JOBHUNTER_AUTHORIZED_BOARD_ROBOTS','maybe')
    calls=serve(monkeypatch,lambda u:pytest.fail('Invalid configuration'))
    with pytest.raises(ValueError):collect(Source('wuzzuf',listing('wuzzuf')))
    assert not calls

def test_skip_mode_retains_detail_budget(monkeypatch,store):
    monkeypatch.setenv('JOBHUNTER_AUTHORIZED_BOARD_ROBOTS','skip')
    sid=register(store,'wuzzuf',listing('wuzzuf'),True)
    def response(url):
        if url==listing('wuzzuf'):return ''.join(f'<a href="{detail("wuzzuf",n)}">job</a>' for n in range(1,7)).encode()
        return html(posting('wuzzuf',int(url.rsplit('/',1)[1].split('-')[0])))
    calls=serve(monkeypatch,response);r=scan(store,sid)
    assert len(calls)==5 and r['inserted']==4 and r['pending_details']==2
