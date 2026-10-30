from dataclasses import asdict
import json
import pytest
from jobhunter_app.store import Store
from jobhunter_app.source_discovery import discover, recognize
from jobhunter_app.source_catalog import record, activate
from jobhunter_app.sources import scan, register


def test_observed_heldout_source_no_guessing():
    leads=discover([{'url':'https://example.org/job/1','job_url_direct':'https://jobs.lever.co/HeldOut/abc'}])
    lead=next(x for x in leads if x.kind)
    assert (lead.kind,lead.identifier,lead.posting_id)==('lever','HeldOut','abc')
    assert lead.origin_url=='https://example.org/job/1'
    assert recognize('https://example.org/careers') is None
    assert not discover([{'url':'http://localhost/test'}])
    assert recognize('https://jobs.lever.co.evil.org/HeldOut/abc') is None


def test_policy_never_reapproves_paused_source(tmp_path):
    store=Store(tmp_path/'app.db');lead=discover([{'url':'https://jobs.lever.co/HeldOut/a'}])[0]
    record(store,lead)
    assert activate(store,lead)['state']=='needs_access'
    assert activate(store,lead,True)['state']=='needs_access'
    register(store,'lever','HeldOut',True)
    assert activate(store,lead)['state']=='available'
    with store.connect() as db: assert len(json.loads(db.execute('SELECT evidence FROM source_leads').fetchone()[0]))==1


def test_jobspy_metadata_survives_canonical_model(tmp_path,monkeypatch):
    import pandas as pd,sys
    from types import SimpleNamespace
    from jobhunter_app.search_strategy import QuerySpec
    monkeypatch.setitem(sys.modules,'jobspy',SimpleNamespace(scrape_jobs=lambda **k:pd.DataFrame([{
        'job_url':'https://example.org/jobs/1','job_url_direct':'https://jobs.lever.co/HeldOut/abc',
        'title':'Unfamiliar Wizard','company':'Example','description':'Python'}])))
    store=Store(tmp_path/'app.db');sid=register(store,'jobspy_indeed','configured',True)
    result=scan(store,sid,request=QuerySpec('default','v1','Python Developer','Germany','en','indeed'),mirror_legacy=False)
    assert result['inserted']==1
    assert any(x['identifier']=='HeldOut' and x['origin_url']=='https://example.org/jobs/1' for x in result['discovery_leads'])
    assert 'job_url_direct' not in store.jobs()[0]


@pytest.mark.parametrize('detail_status',[200,503])
def test_workday_wrapper_uses_existing_scanner(tmp_path,monkeypatch,detail_status):
    import httpx
    from jobhunter_app.source_catalog import activate
    def handler(request):
        if request.method=='POST': return httpx.Response(200,json={'total':1,'jobPostings':[{'title':'Engineer','externalPath':'/job/Engineer_R1','locationsText':'Germany'}]})
        return httpx.Response(detail_status,json={'jobPostingInfo':{'jobDescription':'<p>Python</p>'}})
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    store=Store(tmp_path/'app.db');lead=discover([{'url':'https://employer.wd1.myworkdayjobs.com/en-US/Careers/job/Engineer_R1'}])[0]
    record(store,lead);binding=activate(store,lead,True)
    result=scan(store,binding['source_id'],mirror_legacy=False)
    assert result['inserted']==1
    assert bool(result['provider_errors']) == (detail_status != 200)
    assert ('Python' in store.jobs()[0]['description']) == (detail_status == 200)


def test_bounded_public_inspection_recognizes_observed_family_not_guessed(monkeypatch):
    from jobhunter_app.source_discovery import SourceLead,inspect_public
    monkeypatch.setattr('time.sleep',lambda *a:None)
    calls=[]
    def getter(url,*a,**kw):
        calls.append(url)
        if url.endswith('robots.txt'): return b'User-agent: *\nAllow: /\n','text/plain'
        return b'<a href="https://jobs.ashbyhq.com/ObservedOnly/job1">Apply</a>','text/html'
    result=inspect_public(SourceLead('https://employer.example/careers/1','https://board.example/job/1','job_url_direct'),getter)
    assert result['requests']==2 and result['leads'][0].identifier=='ObservedOnly'
    assert len(calls)==2 and result['leads'][0].origin_url=='https://employer.example/careers/1'
    def blocked(url,*a,**kw): return b'User-agent: *\nDisallow: /\n','text/plain'
    result=inspect_public(SourceLead('https://employer.example/job','https://board.example/job','job_url_direct'),blocked)
    assert result['requests']==1 and not result['leads']


def test_native_html_links_preserved_before_plain_normalization(tmp_path):
    from jobhunter_app.collection import Collection
    store=Store(tmp_path/'app.db');sid=register(store,'arbeitnow','de',True)
    payload={'data':[{'title':'Engineer','company_name':'Example','url':'https://www.arbeitnow.com/jobs/1',
        'description':'<p>Python</p><a href="https://jobs.ashbyhq.com/ObservedNative/1">Apply</a>'}]}
    result=scan(store,sid,transport=lambda s:Collection(payload),mirror_legacy=False)
    assert result['inserted']==1
    assert any(x['identifier']=='ObservedNative' for x in result['discovery_leads'])
    assert '<a' not in store.jobs()[0]['description']
