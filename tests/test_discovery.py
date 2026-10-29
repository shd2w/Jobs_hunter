"""Synthetic discovery fixtures. No provider traffic and no candidate-data mutation."""
import json
import socket
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError
import pytest
from jobhunter_app.store import Store, SCHEMA
from jobhunter_app.posts import extract, stage, listing, detail, accept, dismiss, origins
from jobhunter_app.feeds import parse, ingest
from jobhunter_app.sources import Source, normalize, register, scan, fetch, POLICIES
from jobhunter_app.network import feed_url, public_addresses
from jobhunter_app.intake import export_jobs
from jobhunter_app.documents import prepare_pack
from tests.test_local_store import JOB, PROFILE
from tests.test_web_local import web, request, token

BODY='We are hiring!\nRole: Python Engineer\nCompany: Example Labs\nLocation: Cairo\nApply: https://example.com/jobs/python\nRequired: Python and SQL\nPreferred: Docker'
POST={'body':BODY,'origin_url':'https://example.org/posts/1','source_label':'Authorized fixture'}
RSS=b'''<rss version="2.0"><channel><title>Example jobs</title><item><title>We are hiring</title><link>https://example.org/post/1</link><description><![CDATA[<p>Role: Python Engineer</p><p>Company: Example Labs</p><p>Apply: https://example.com/jobs/python</p><script>bad()</script>]]></description><pubDate>Thu, 29 Oct 2026 13:00:00 GMT</pubDate></item><item><title>Lunch menu</title><description>Soup today</description></item></channel></rss>'''

@pytest.fixture
def store(tmp_path):
    s=Store(tmp_path/'app.sqlite3');s.save_profile(PROFILE);return s

def test_v1_upgrade_preserves_rows_and_backups(tmp_path):
    path=tmp_path/'v1.db'
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA+'PRAGMA user_version=1;')
        db.execute('INSERT INTO profiles VALUES(?,?,?)',('default',json.dumps(PROFILE),'prior'))
        db.execute('INSERT INTO audit(event,details,created_at) VALUES(?,?,?)',('prior','{}','prior'))
    s=Store(path)
    assert s.profile()==PROFILE
    with s.connect() as db:
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert db.execute('SELECT event FROM audit').fetchone()[0]=='prior'
        assert db.execute('PRAGMA user_version').fetchone()[0]==5
    backups=list(tmp_path.glob('*.bak'));assert len(backups)==1
    with sqlite3.connect(backups[0]) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==1
        assert db.execute('SELECT COUNT(*) FROM profiles').fetchone()[0]==1
    Store(path);assert len(list(tmp_path.glob('*.bak')))==1

def test_concurrent_schema_init(tmp_path):
    with ThreadPoolExecutor(4) as pool: list(pool.map(lambda _:Store(tmp_path/'same.db'),range(8)))
    with Store(tmp_path/'same.db').connect() as db:assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'

def test_extraction_offsets_and_no_network():
    x=extract(BODY)
    assert x['fields']['title']=='Python Engineer' and x['fields']['company']=='Example Labs'
    for e in list(x['evidence'].values())+x['requirements']:
        assert BODY[e['start']:e['end']]==e['quote']
    assert x['requirements'][-1]['category']=='preferred'
    assert x['fields']['url']=='https://example.com/jobs/python'

@pytest.mark.parametrize('body,title,company',[
 ('Stelle: Datenanalyst\nUnternehmen: Beispiel GmbH\nStandort: Berlin\nBewerbungslink: https://example.com/1','Datenanalyst','Beispiel GmbH'),
 ('الوظيفة: مهندس بيانات\nالشركة: مثال\nالموقع: القاهرة\nالتقديم: https://example.com/1','مهندس بيانات','مثال'),
 ("We're hiring Data Analyst at Example Research.",'Data Analyst','Example Research'),
])
def test_multilingual_labels(body,title,company):
    x=extract(body);assert x['fields']['title']==title and x['fields']['company']==company

@pytest.mark.parametrize('body',['Open to work, looking for a job in Python','أبحث عن وظيفة','Today we had lunch'])
def test_non_vacancies_not_saved(store,body):
    r=stage(store,[{'body':body}],True);assert r['skipped']==1 and listing(store)==[]

def test_ambiguous_and_untrusted_content(store):
    body=BODY+'\nI am open to work.\n<script>alert(1)</script>'
    r=stage(store,[{**POST,'body':body}],True)
    assert r['items'][0]['classification']=='ambiguous'
    assert detail(store,r['items'][0]['id'])['body']==body
    assert store.jobs()==[]

@pytest.mark.parametrize('bad',[None,'',123,'x'*100001,'a\x00b'])
def test_post_bounds(bad):
    with pytest.raises(ValueError):extract(bad)

def test_multiple_roles_urls_and_expired_warning():
    x=extract('Role: A\nRole: B\nCompany: Example\nApply: https://example.com/a https://example.com/b\nDeadline: 2000-01-01')
    assert x['classification']=='possible_vacancy' and 'title' not in x['fields'] and 'url' not in x['fields']
    assert any('past' in w for w in x['warnings'])

def test_rights_preview_partial_and_batch_duplicates(store):
    with pytest.raises(ValueError):stage(store,[POST])
    r=stage(store,[POST,POST],dry_run=True);assert (r['staged'],r['duplicates'])==(1,1) and listing(store)==[]
    r=stage(store,[POST,{},None],True);assert r['staged']==1 and r['invalid']==2
    assert stage(store,[POST],True)['duplicates']==1
    assert store.jobs()==[]

def test_changed_content_keeps_revision(store):
    first=stage(store,[POST],True)['items'][0]['id']
    second=stage(store,[{**POST,'body':BODY+'\nRevision'}],True)['items'][0]['id']
    assert first!=second and len(listing(store))==2

def test_review_confirmation_invalid_fields_no_partial_job(store):
    id=stage(store,[POST],True)['items'][0]['id']
    with pytest.raises(ValueError):accept(store,id,JOB)
    with pytest.raises(ValueError):accept(store,id,{**JOB,'url':'javascript:alert(1)'},True)
    with pytest.raises(ValueError):accept(store,'missing',JOB,True)
    assert store.jobs()==[] and detail(store,id)['status']=='pending'

def test_accept_idempotence_and_multiple_post_provenance(store,tmp_path):
    id=stage(store,[POST],True)['items'][0]['id'];fields=detail(store,id)['extracted']['fields']
    job_id=accept(store,id,{**fields,'description':BODY},True)['job_id']
    store.set_status(job_id,'saved','Do not erase')
    accept(store,id,{**fields,'company':'Human reviewed alias'},True)
    other=stage(store,[{**POST,'origin_url':'https://example.org/posts/2'}],True)['items'][0]['id']
    assert accept(store,other,{**fields,'url':fields['url']+'?utm_source=other'},True)['linked_existing']
    assert len(origins(store,job_id))==2 and store.jobs()[0]['notes']=='Do not erase'
    assert store.jobs()[0]['company']=='Example Labs' and len(store.jobs())==1
    assert len(json.loads(export_jobs(store))[0]['post_origins'])==2
    assert b'post_origins' in export_jobs(store,'csv')
    pack=prepare_pack(store,job_id,tmp_path/'packs')
    assert len(json.loads((__import__('pathlib').Path(pack['directory'])/'preparation.json').read_text())['post_origins'])==2

def test_review_transaction_rolls_back(store,monkeypatch):
    id=stage(store,[POST],True)['items'][0]['id']
    original=store.audit
    def fail(db,event,details):
        if event=='post_reviewed':raise RuntimeError('simulated commit failure')
        original(db,event,details)
    monkeypatch.setattr(store,'audit',fail)
    with pytest.raises(RuntimeError):accept(store,id,JOB,True)
    assert not store.jobs() and detail(store,id)['status']=='pending' and not origins(store,'missing')

def test_duplicate_link_preserves_target_and_rejects_conflicting_url(store):
    store.ingest([JOB,{**JOB,'url':'https://example.com/other'}]);target=store.jobs()[0]['id'];other=store.jobs()[1]
    id=stage(store,[POST],True)['items'][0]['id']
    with pytest.raises(ValueError,match='different job'):accept(store,id,other,True,target)
    assert accept(store,id,{**JOB,'url':'https://example.net/syndicated'},True,target)['job_id']==target
    assert len(store.jobs())==2 and len(origins(store,target))==1
    store.ingest([{**JOB,'url':'https://example.net/syndicated','company':'Do not replace'}],source='later-feed')
    assert len(store.jobs())==2 and store.job(target)['company']=='Example'
    assert accept(store,id,{**JOB,'url':'https://example.net/syndicated'},True)['job_id']==target

def test_dismiss_and_status_filter(store):
    id=stage(store,[POST],True)['items'][0]['id'];dismiss(store,id)
    assert not listing(store) and listing(store,'dismissed')[0]['id']==id
    accept(store,id,JOB,True)
    with pytest.raises(ValueError):dismiss(store,id)
    with pytest.raises(ValueError):listing(store,'garbage')
    with pytest.raises(ValueError):listing(store,offset=-1)

def test_feed_rss_and_no_script_or_author_employer(store):
    parsed=parse(RSS);assert len(parsed['posts'])==2 and 'bad()' not in parsed['posts'][0]['body']
    r=ingest(store,RSS,True);assert r['staged']==1 and r['skipped']==1 and not store.jobs()
    x=detail(store,r['items'][0]['id'])['extracted'];assert 'Thu,' in x['published_raw']
    atom=b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Hiring now</title><author><name>Not Employer</name></author><link href="/posts/one"/><content type="html">Required: Python</content></entry></feed>'
    post=parse(atom,base_url='https://example.org/feed')['posts'][0]
    assert post['origin_url']=='https://example.org/posts/one' and 'company' not in extract(post['body'])['fields']

@pytest.mark.parametrize('payload',[b'<html>not feed</html>', b'<!DOCTYPE rss [<!ENTITY x SYSTEM "file:///etc/passwd">]><rss><channel><item><title>&x;</title></item></channel></rss>', b'<!DOCTYPE rss><rss/>', b'<rss', b'x'*(5*1024*1024+1)])
def test_feed_rejects_unsafe_xml(payload):
    with pytest.raises(ValueError):parse(payload)

def test_feed_truncation_and_bad_link():
    payload=('<rss><channel>'+('<item><title>Hiring</title><description>Role: Analyst</description></item>'*301)+'</channel></rss>').encode()
    parsed=parse(payload);assert parsed['truncated'] and len(parsed['posts'])==300
    parsed=parse(b'<rss><channel><item><title>Hiring</title><link>http://127.0.0.1/x</link></item></channel></rss>');assert len(parsed['errors'])==1

@pytest.mark.parametrize('url',['http://example.com/feed','https://localhost/feed','https://127.0.0.1/feed','https://example.com:80/feed','https://example.com/f#x','https://example.com/f?api_key=secret','https://www.reddit.com/jobs.rss','https://t.me/channel','https://x.com/feed'])
def test_feed_network_policy(url):
    with pytest.raises(ValueError):feed_url(url)

@pytest.mark.parametrize('ip',['127.0.0.1','10.1.2.3','169.254.169.254','::1','::ffff:127.0.0.1','100.64.0.1'])
def test_dns_private_addresses_rejected(monkeypatch,ip):
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**kw:[(socket.AF_INET,socket.SOCK_STREAM,6,'',(ip,443))])
    with pytest.raises(ValueError):public_addresses('example.com')

def test_dns_all_addresses_must_be_public(monkeypatch):
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**kw:[(2,1,6,'',(x,443)) for x in ('93.184.216.34','127.0.0.1')])
    with pytest.raises(ValueError):public_addresses('example.com')

def test_tls_connect_uses_pinned_address_and_original_sni(monkeypatch):
    from jobhunter_app.network import PinnedHTTPS
    calls=[];fake=object()
    monkeypatch.setattr(socket,'create_connection',lambda endpoint,timeout:(calls.append(endpoint) or fake))
    class Context:
        def wrap_socket(self,sock,server_hostname):calls.append(server_hostname);return fake
    conn=PinnedHTTPS('example.org','93.184.216.34');conn._context=Context();conn.connect()
    assert calls==[('93.184.216.34',443),'example.org']

def test_ashby_lists_only_public_jobs(store):
    payload={'jobs':[{'title':'Engineer','jobUrl':'https://example.com/a','descriptionPlain':'Python','isListed':True},{'title':'Hidden','isListed':False},{'title':'Unknown visibility'}]}
    sid=register(store,'ashby','example',True);r=scan(store,sid,lambda _:payload)
    assert r['inserted']==1 and store.jobs()[0]['company']=='example'
    with pytest.raises(ValueError,match='600'):scan(store,sid,lambda _:payload)

def test_remotive_attribution_location_and_global_cooldown(store):
    payload={'jobs':[{'id':7,'title':'Engineer','url':'https://remotive.com/remote-jobs/software-dev/example-7','company_name':'Example','description':'<p>Python</p>','candidate_required_location':'Europe','publication_date':'2026-10-28','salary':'EUR 50k'}]}
    sid=register(store,'remotive','remote',True);scan(store,sid,lambda _:payload)
    job=store.jobs()[0];assert job['attribution']=='Remotive' and job['location']=='Europe'
    assert '24 hours' in job['source_notice'] and b'Remotive' in export_jobs(store,'csv')
    register(store,'remotive','remote',True)
    with pytest.raises(ValueError,match='21600'):scan(store,sid,lambda _:payload)
    with pytest.raises(ValueError):register(store,'remotive','other',True)

def test_smartrecruiters_bounded_details_and_safe_ref(monkeypatch,store):
    from jobhunter_app import network
    calls=[]
    def transport(url,*args,**kwargs):
        calls.append(url)
        if len(calls)==1:return json.dumps({'totalFound':200,'content':[{'id':str(i),'ref':'https://127.0.0.1/internal'} for i in range(100)]}).encode(),'application/json'
        return json.dumps({'id':str(len(calls)),'name':'Engineer','active':True,'company':{'name':'Example'},'applyUrl':f'https://example.com/job/{len(calls)}','location':{'city':'Cairo','country':'EG'},'jobAd':{'sections':{'jobDescription':{'text':'<p>Python</p>'}}}}).encode(),'application/json'
    monkeypatch.setattr(network,'get',transport);monkeypatch.setattr('time.sleep',lambda _:None)
    sid=register(store,'smartrecruiters','example',True)
    r=scan(store,sid);assert len(calls)==11 and r['inserted']==10 and r['bounded_selection']
    assert all(u.startswith('https://api.smartrecruiters.com/') for u in calls)
    assert store.summary()['sources'][0]['health']=='partial'

def test_feed_source_requires_approval_then_auto_adds_complete_vacancy(store):
    sid=register(store,'feed','https://example.org/jobs.rss')
    with pytest.raises(ValueError):scan(store,sid,lambda _:RSS)
    register(store,'feed','https://example.org/jobs.rss',True)
    r=scan(store,sid,lambda _:RSS);assert r['staged']==1 and r['auto_added']==1 and len(store.jobs())==1
    assert len(sid)<100

@pytest.mark.parametrize('kind',['ashby','smartrecruiters','remotive','feed'])
def test_new_sources_429_pause(store,kind):
    identifier={'remotive':'remote','feed':'https://example.org/f'}.get(kind,'example')
    sid=register(store,kind,identifier,True)
    def fail(_):raise HTTPError('https://example.org',429,'limited',{},None)
    with pytest.raises(ValueError):scan(store,sid,fail)
    assert store.summary()['sources'][0]['approved']==0

def test_discovery_http_full_workflow(web):
    headers={'X-JobHunter-Token':token(web)}
    def post(path,data):
        status,_,body=request(web,'POST',path,data,headers);return status,json.loads(body)
    assert request(web,'GET','/discovery.js')[0]==200
    assert request(web,'GET','/api/source-catalog')[0]==200
    assert post('/api/posts/stage',{'posts':[POST]})[0]==400
    status,r=post('/api/posts/preview',{'posts':[POST]});assert status==200 and not listing(web[0])
    status,r=post('/api/posts/stage',{'posts':[POST],'rights_attested':True});assert status==200
    id=r['items'][0]['id'];assert request(web,'GET','/api/post?id='+id)[0]==200
    assert post('/api/posts/accept',{'id':id,'fields':JOB})[0]==400
    status,r=post('/api/posts/accept',{'id':id,'fields':JOB,'confirmed':True});assert status==200
    assert json.loads(request(web,'GET','/api/origins?id='+r['job_id'])[2])[0]['body']==BODY
    assert post('/api/feed-import',{'content':'<html/>','rights_attested':True})[0]==400
    assert post('/api/source',{'kind':'ashby','identifier':'example'})[0]==200
    assert web[0].summary()['sources'][0]['approved']==0
    assert post('/api/source',{'kind':'feed','identifier':'https://t.me/jobs','approved':True})[0]==400

@pytest.mark.parametrize('mode',['redirect','too_big_header','too_big_stream','compressed','timeout'])
def test_network_boundaries(monkeypatch,mode):
    from jobhunter_app import network
    monkeypatch.setattr(network,'public_addresses',lambda _:['93.184.216.34'])
    class Response:
        status=302 if mode=='redirect' else 200
        def getheader(self,name,default=None):
            return {'Content-Type':'application/json','Content-Length':str(network.MAX_BYTES+1) if mode=='too_big_header' else None,'Content-Encoding':'gzip' if mode=='compressed' else 'identity'}.get(name,default)
        def read1(self,n):
            if mode=='timeout':raise TimeoutError('simulated')
            return b'x'*n
    class Connection:
        sock=None
        def __init__(self,*args,**kw):pass
        def request(self,*args,**kw):pass
        def getresponse(self):return Response()
        def close(self):pass
    monkeypatch.setattr(network,'PinnedHTTPS',Connection)
    with pytest.raises((ValueError,HTTPError,TimeoutError)):network.get('https://example.org/feed')

def test_network_single_dns_validation_and_identity_headers(monkeypatch):
    from jobhunter_app import network
    calls=[]
    monkeypatch.setattr(network,'public_addresses',lambda host:(calls.append(('dns',host)) or ['93.184.216.34']))
    class Response:
        status=200
        done=False
        def getheader(self,name,default=None):return {'Content-Type':'application/json','Content-Encoding':'identity'}.get(name,default)
        def read1(self,n):
            if self.done:return b''
            self.done=True;return b'{"jobs":[]}'
    class Connection:
        sock=None
        def __init__(self,host,address):calls.append(('connect',host,address))
        def request(self,*args,**kw):calls.append(('request',args,kw))
        def getresponse(self):return Response()
        def close(self):calls.append(('closed',))
    monkeypatch.setattr(network,'PinnedHTTPS',Connection)
    content,typ=network.get('https://example.org/feed?q=one')
    assert content==b'{"jobs":[]}' and typ=='application/json'
    assert calls[0]==('dns','example.org') and calls[1]==('connect','example.org','93.184.216.34')
    assert calls[2][1]==('GET','/feed?q=one') and 'Authorization' not in calls[2][2]['headers']
    assert calls[-1]==('closed',)

def test_smartrecruiters_cancellation_between_details(monkeypatch,store):
    from threading import Event
    from jobhunter_app import network
    event=Event();calls=[]
    def fake(url,*a,**kw):
        calls.append(url)
        if len(calls)==1:return json.dumps({'content':[{'id':'one'},{'id':'two'}]}).encode(),'application/json'
        event.set();return json.dumps({'name':'Engineer','applyUrl':'https://example.org/1','company':{'name':'Example'}}).encode(),'application/json'
    monkeypatch.setattr(network,'get',fake);monkeypatch.setattr('time.sleep',lambda _:None)
    sid=register(store,'smartrecruiters','example',True)
    assert scan(store,sid,cancel_event=event)['cancelled'] and len(calls)==2 and not store.jobs()

def test_same_title_different_urls_need_human_duplicate_decision(store):
    fields=extract(BODY)['fields']
    first=stage(store,[POST],True)['items'][0]['id'];one=accept(store,first,fields,True)['job_id']
    second=stage(store,[{**POST,'body':BODY.replace('/jobs/python','/jobs/different'),'origin_url':'https://example.org/posts/2'}],True)['items'][0]['id']
    d=detail(store,second);assert d['possible_duplicates'][0]['id']==one
    two=accept(store,second,d['extracted']['fields'],True)['job_id']
    assert two!=one and len(store.jobs())==2
