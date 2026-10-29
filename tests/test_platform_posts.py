"""Synthetic official-API contracts. No genuine platform API calls in this suite."""
import json
from urllib.parse import urlsplit,parse_qs
from urllib.error import HTTPError
import pytest
from jobhunter_app import platform_posts as pp
from jobhunter_app.sources import Source,register,scan,catalog
from jobhunter_app.store import Store

BODY='We are hiring!\nRole: Python Engineer\nCompany: QA Employer\nApply: https://example.org/jobs/python\nPython required'
IDS={'linkedin':'12345','x':'12345','reddit':'careers','telegram':'channels','discord':'111-222'}

@pytest.fixture
def configured(monkeypatch):
    values={'JOBHUNTER_LINKEDIN_TOKEN':'secret-linkedin','JOBHUNTER_LINKEDIN_VERSION':'202610','JOBHUNTER_LINKEDIN_ACCESS_APPROVED':'1',
      'JOBHUNTER_X_BEARER':'secret-x','JOBHUNTER_X_ACCESS_APPROVED':'1','JOBHUNTER_X_COST_APPROVED':'1',
      'JOBHUNTER_REDDIT_TOKEN':'secret-reddit','JOBHUNTER_REDDIT_USER_AGENT':'JobHunter local test (authorized)','JOBHUNTER_REDDIT_API_APPROVED':'1',
      'JOBHUNTER_DISCORD_BOT_TOKEN':'secret-discord','JOBHUNTER_DISCORD_ACCESS_APPROVED':'1',
      'JOBHUNTER_TELEGRAM_READ_BOT_TOKEN':'123456:'+('a'*30),'JOBHUNTER_TELEGRAM_CHANNELS':'approvedjobs','JOBHUNTER_TELEGRAM_DEDICATED_BOT':'1'}
    for k,v in values.items():monkeypatch.setenv(k,v)
    monkeypatch.setenv('JOBHUNTER_POST_MODE','auto')
    return values

def payload(kind,body=BODY):
    if kind=='linkedin':return {'elements':[{'author':'urn:li:organization:12345','id':'urn:li:share:123456','commentary':body,'visibility':'PUBLIC','lifecycleState':'PUBLISHED'}],'paging':{'links':[]}}
    if kind=='x':return {'data':[{'id':'123456','text':body}],'meta':{'result_count':1}}
    if kind=='reddit':return {'data':{'children':[{'kind':'t3','data':{'id':'abc123','subreddit':'careers','title':body.splitlines()[0] if body else '', 'selftext':body}}],'after':None}}
    if kind=='discord':return [{'id':'123456','channel_id':'222','content':body}]
    return {'ok':True,'result':[{'update_id':100,'channel_post':{'chat':{'type':'channel','username':'approvedjobs'},'message_id':123,'text':body}}]}

def serve(monkeypatch,kind,fn=None):
    calls=[]
    def get(url,*args,**kwargs):
        pp.validate_request_scope(kind,url,kwargs['credentials']);calls.append((url,kwargs))
        return json.dumps(fn(url) if fn else payload(kind)).encode(),'application/json'
    monkeypatch.setattr('jobhunter_app.network.get',get);return calls

@pytest.mark.parametrize('kind',pp.KINDS)
def test_setup_missing_no_network_no_run(monkeypatch,tmp_path,kind):
    for k in pp.REQUIRED[kind]:monkeypatch.delenv(k,raising=False)
    monkeypatch.setattr('jobhunter_app.network.get',lambda *a,**k:pytest.fail('No provider request'))
    s=Store(tmp_path/'a.db');sid=register(s,kind,IDS[kind],True)
    with pytest.raises(pp.SetupRequired,match='Configure'):scan(s,sid)
    with s.connect() as db:
        assert not db.execute('SELECT * FROM runs').fetchone()
        assert db.execute('SELECT last_run FROM sources').fetchone()[0] is None
    c=next(x for x in catalog() if x['kind']==kind);assert c['state']=='setup_required' and not c['live_verified']

@pytest.mark.parametrize('kind',pp.KINDS)
def test_official_api_to_jobs_match_checkpoint(configured,monkeypatch,tmp_path,kind):
    calls=serve(monkeypatch,kind);s=Store(tmp_path/'a.db');s.save_profile({'name':'QA','skills':['Python'],'facts':[]})
    sid=register(s,kind,IDS[kind],True);r=scan(s,sid)
    assert r['auto_added']==1 and r['evaluated']==1 and r['new_unique_jobs']==1 and r['requests']==1
    assert len(calls)==1 and s.summary()['matched_jobs']==1 and not r['live_verified']
    with s.connect() as db:
        o=db.execute('SELECT review_data FROM job_origins').fetchone();assert json.loads(o[0])['human_confirmed'] is False
        assert db.execute('SELECT data FROM source_checkpoints').fetchone()
        saved=' '.join(str(tuple(row)) for table in ('sources','source_checkpoints','runs','audit','discovery_items','jobs','job_origins') for row in db.execute('SELECT * FROM '+table))
        assert 'secret-' not in saved and configured['JOBHUNTER_TELEGRAM_READ_BOT_TOKEN'] not in saved
    with pytest.raises(ValueError,match='cooldown'):scan(s,sid)
    assert len(calls)==1

@pytest.mark.parametrize('kind,bad',[
 ('linkedin','urn:li:organization:123'),('linkedin','123/secret'),('x','@someone'),('x','0'),
 ('reddit','r/careers'),('reddit','careers+other'),('telegram','everybody'),('discord','@me-222'),('discord','111/222')])
def test_identifier_scope_rejection(kind,bad):
    with pytest.raises(ValueError):Source(kind,bad)

@pytest.mark.parametrize('kind',pp.KINDS)
def test_unapproved_never_fetches(configured,monkeypatch,tmp_path,kind):
    monkeypatch.setattr('jobhunter_app.network.get',lambda *a,**k:pytest.fail('Unapproved'))
    s=Store(tmp_path/'a.db');sid=register(s,kind,IDS[kind])
    with pytest.raises(ValueError,match='approved'):scan(s,sid)

@pytest.mark.parametrize('kind',pp.KINDS)
def test_credentials_never_forwarded_to_other_hosts(configured,monkeypatch,kind):
    calls=serve(monkeypatch,kind);pp.collect(Source(kind,IDS[kind]))
    u,k=calls[0]
    with pytest.raises(ValueError):pp.validate_request_scope(kind,u.replace(urlsplit(u).netloc,'evil.example'),k['credentials'])
    with pytest.raises(ValueError):pp.validate_request_scope(kind,u.replace(urlsplit(u).path,'/sendMessage'),k['credentials'])
    with pytest.raises(ValueError):pp.validate_request_scope(kind,u,{**k['credentials'],'X-Unknown':'not allowed'})

@pytest.mark.parametrize('kind',pp.KINDS)
@pytest.mark.parametrize('status',[401,403,429])
def test_api_gate_atomic_redacted(configured,monkeypatch,tmp_path,kind,status):
    s=Store(tmp_path/'a.db');sid=register(s,kind,IDS[kind],True)
    def get(url,**kwargs):raise HTTPError(url,status,'SECRET PROVIDER ERROR',{'Retry-After':'7200'},None)
    monkeypatch.setattr('jobhunter_app.network.get',get)
    with pytest.raises(ValueError):scan(s,sid)
    with s.connect() as db:
        assert db.execute('SELECT approved FROM sources').fetchone()[0]==0
        assert not db.execute('SELECT * FROM source_checkpoints').fetchone()
        assert not db.execute('SELECT * FROM jobs').fetchone()
        contents=str([tuple(x) for x in db.execute('SELECT * FROM runs')]);assert 'SECRET' not in contents and '/bot123456:' not in contents
        if status==429:assert db.execute('SELECT * FROM provider_gates').fetchone()

@pytest.mark.parametrize('kind',pp.KINDS)
def test_non_jobs_filtered_without_invented_roles(configured,monkeypatch,tmp_path,kind):
    serve(monkeypatch,kind,lambda _:payload(kind,'Lunch with the team today.'))
    s=Store(tmp_path/'a.db');sid=register(s,kind,IDS[kind],True);r=scan(s,sid)
    assert r['skipped']==1 and not s.jobs()

def test_x_explicit_cost_gate(configured,monkeypatch):
    monkeypatch.delenv('JOBHUNTER_X_COST_APPROVED');monkeypatch.setattr('jobhunter_app.network.get',lambda *a,**k:pytest.fail('No paid call'))
    with pytest.raises(pp.SetupRequired,match='COST_APPROVED'):pp.collect(Source('x','12345'))

def test_telegram_dedicated_queue_allowlist_and_offset(configured,monkeypatch):
    def page(url):
        d=payload('telegram');d['result'].append({'update_id':101,'channel_post':{'chat':{'type':'channel','username':'otherjobs'},'message_id':124,'text':BODY}})
        return d
    calls=serve(monkeypatch,'telegram',lambda url: {'ok':True,'result':[]} if 'offset=102' in url else page(url));r=pp.collect(Source('telegram','channels'))
    assert len(r.payload)==1 and r.checkpoint['cursor']=='102' and r.metrics['filtered_out_of_scope_or_removed']==1
    assert r.metrics['page_exhausted'] and not r.metrics['bounded_selection']
    pp.collect(Source('telegram','channels'),r.checkpoint)
    assert parse_qs(urlsplit(calls[-1][0]).query)['offset']==['102']
    assert 'channel_post' in parse_qs(urlsplit(calls[0][0]).query)['allowed_updates'][0]

def test_telegram_shared_bot_not_allowed(configured,monkeypatch):
    monkeypatch.setenv('JOBHUNTER_TELEGRAM_DEDICATED_BOT','0')
    with pytest.raises(pp.SetupRequired):pp.collect(Source('telegram','channels'))

def test_discord_non_text_preserved_for_review(configured,monkeypatch,tmp_path):
    serve(monkeypatch,'discord',lambda _:payload('discord',''))
    s=Store(tmp_path/'a.db');sid=register(s,'discord','111-222',True);r=scan(s,sid)
    assert r['needs_review']==1 and r['non_text_or_unavailable']==1 and not s.jobs()
    with s.connect() as db:assert db.execute('SELECT status FROM discovery_items').fetchone()[0]=='pending'

def test_linkedin_unapproved_visibility_filtered(configured,monkeypatch):
    d=payload('linkedin');d['elements'][0]['visibility']='CONNECTIONS';serve(monkeypatch,'linkedin',lambda _:d)
    r=pp.collect(Source('linkedin','12345'));assert not r.payload and r.metrics['filtered_out_of_scope_or_removed']==1

def test_linkedin_pagination_verified_author(configured,monkeypatch):
    d=payload('linkedin');d['paging']['links']=[{'rel':'next','href':'https://api.linkedin.com/rest/posts?author=urn%3Ali%3Aorganization%3A12345&start=50&q=author'}]
    calls=serve(monkeypatch,'linkedin',lambda url:payload('linkedin') if 'start=50' in url else d);r=pp.collect(Source('linkedin','12345'));assert r.checkpoint['cursor']=='50'
    pp.collect(Source('linkedin','12345'),r.checkpoint)
    assert parse_qs(urlsplit(calls[1][0]).query)['start']==['50']

@pytest.mark.parametrize('kind',('x','reddit'))
def test_cursor_resume(configured,monkeypatch,kind):
    d=payload(kind)
    if kind=='x':d['meta']['next_token']='next_50'
    else:d['data']['after']='t3_abc123'
    calls=serve(monkeypatch,kind,lambda _:d);r=pp.collect(Source(kind,IDS[kind]));assert r.checkpoint['cursor']
    # Return an exhausted second page to avoid repeating a supplied cursor.
    serve(monkeypatch,kind);pp.collect(Source(kind,IDS[kind]),r.checkpoint)

@pytest.mark.parametrize('kind',pp.KINDS)
def test_malformed_page_no_commit(configured,monkeypatch,tmp_path,kind):
    serve(monkeypatch,kind,lambda _:['unexpected'] if kind!='discord' else {'unexpected':True})
    s=Store(tmp_path/'a.db');sid=register(s,kind,IDS[kind],True)
    with pytest.raises(ValueError):scan(s,sid)
    assert not s.jobs()
    with s.connect() as db:assert not db.execute('SELECT * FROM source_checkpoints').fetchone()

def test_telegram_http_errors_redact_token_before_propagation(configured,monkeypatch):
    from jobhunter_app import network
    class Response:
        status=403
        def getheader(self,k,default=''):return default
    class Connection:
        def __init__(self,*a):pass
        def request(self,*a,**k):pass
        def getresponse(self):return Response()
        def close(self):pass
    monkeypatch.setattr(network,'public_addresses',lambda _:['8.8.8.8'])
    monkeypatch.setattr(network,'PinnedHTTPS',Connection)
    token=configured['JOBHUNTER_TELEGRAM_READ_BOT_TOKEN']
    with pytest.raises(HTTPError) as e:network.get('https://api.telegram.org/bot'+token+'/getUpdates',credentials={},credential_scope='telegram')
    assert token not in str(e.value) and token not in e.value.url and e.value.code==403

@pytest.mark.parametrize('kind',pp.KINDS)
def test_untrusted_credential_scope_fails_before_dns(monkeypatch,kind):
    from jobhunter_app import network
    monkeypatch.setattr(network,'public_addresses',lambda _:pytest.fail('No DNS for a forbidden target'))
    with pytest.raises(ValueError):network.get('https://evil.example/collect',credentials={'Authorization':'Bearer secret'},credential_scope=kind)

def test_cancellation_prevents_posts_and_checkpoint(configured,monkeypatch,tmp_path):
    import threading
    event=threading.Event()
    def get(*a,**k):event.set();return json.dumps(payload('x')).encode(),'application/json'
    monkeypatch.setattr('jobhunter_app.network.get',get)
    s=Store(tmp_path/'a.db');sid=register(s,'x','12345',True);r=scan(s,sid,cancel_event=event)
    assert r['cancelled'] and not s.jobs()
    with s.connect() as db:
        assert not db.execute('SELECT * FROM discovery_items').fetchone()
        assert not db.execute('SELECT * FROM source_checkpoints').fetchone()

def test_post_job_match_checkpoint_transaction_rolls_back(configured,monkeypatch,tmp_path):
    serve(monkeypatch,'x');s=Store(tmp_path/'a.db');s.save_profile({'name':'QA','skills':['Python'],'facts':[]})
    sid=register(s,'x','12345',True)
    with s.connect() as db:db.execute("CREATE TRIGGER reject_checkpoint BEFORE INSERT ON source_checkpoints BEGIN SELECT RAISE(FAIL,'synthetic checkpoint failure'); END")
    with pytest.raises(ValueError):scan(s,sid)
    with s.connect() as db:
        for t in ('jobs','matches','discovery_items','job_origins','source_checkpoints'):assert db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0]==0
        assert db.execute('SELECT status FROM runs').fetchone()[0]=='failed'
