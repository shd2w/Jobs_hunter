"""Controlled A01–A14 scenarios. Actual external boundaries replaced, never live proof."""
import json,sys
from types import SimpleNamespace
from dataclasses import replace
import pandas as pd
from jobhunter_app.store import Store
from jobhunter_app.discovery_run import run, report
from jobhunter_app.sources import POLICIES


def fixture_network(monkeypatch):
    calls=[]
    def scrape(**kw):
        calls.append(('board',kw))
        return pd.DataFrame([{'job_url':'https://example.org/syndicated/1','job_url_direct':'https://jobs.lever.co/HeldOutNative/req1',
            'title':'Quantum Wizard','company':'Example','description':'Python SQL','location':'Germany'}])
    def get(url,*a,**kw):
        calls.append(('http',url))
        if 'api.lever.co/v0/postings/HeldOutNative' not in url: raise OSError('unavailable fixture source')
        return json.dumps([{'id':'req1','text':'Backend Engineer','hostedUrl':'https://jobs.lever.co/HeldOutNative/req1',
            'descriptionPlain':'Python SQL','categories':{'location':'Germany'},'sections':[]}]).encode(),'application/json'
    monkeypatch.setitem(sys.modules,'jobspy',SimpleNamespace(scrape_jobs=scrape))
    monkeypatch.setattr('jobhunter_app.network.get',get)
    return calls


def test_no_urls_to_unknown_source_actual_intake_identity_and_report(tmp_path,monkeypatch):
    """A01–A08/A10/A12–A14 with real app paths; not real external discovery."""
    calls=fixture_network(monkeypatch)
    store=Store(tmp_path/'app.db');store.save_profile({'skills':['Python','SQL'],'matching':{'preferred_title_terms':['backend']}})
    from jobhunter_app.expanded_sources import CONFIG
    before=CONFIG.read_bytes()
    result=run(store,regions=['Germany'],max_attempts=2,approve_public_ats=True,providers=['indeed'],project=False)
    assert result['counts']['dispatched']==2
    assert any('HeldOutNative' in str(x) for x in result['leads'])
    assert any(kind=='http' for kind,_ in calls)
    assert any(t.get('assessment',{}).get('state')=='active' for t in result['tasks'])
    assert result['counts']['canonical_insertions']==2
    assert result['identity']=={'members':2,'groups':1}
    assert result['processing']['local_matching']['evaluated']==2
    assert all(j.get('match') or 'description' in j for j in store.jobs())
    assert CONFIG.read_bytes()==before
    assert sum(result['counts'][x] for x in ('succeeded','partial','failed','deferred','cancelled'))==result['counts']['planned']
    persisted=report(store,result['run_id'])
    assert len(persisted['persisted_tasks'])==len(result['tasks'])
    assert any('Backend Engineer'==x['query'] and x['gap'] for x in result['coverage'])
    assert any(t.get('query',{}).get('text')=='Backend Engineer' and t['status']=='deferred' for t in result['tasks'] if t.get('query'))
    again=run(store,regions=['Germany'],max_attempts=2,approve_public_ats=True,providers=['indeed'],project=False)
    assert again['counts']['canonical_insertions']==0
    assert sum(kind=='board' for kind,_ in calls)==1
    assert sum(kind=='http' and 'api.lever.co' in value for kind,value in calls)==1
    # Other previously deferred native sources may now be explored; old requests are not repeated.
    assert any(t['status']=='deferred' for t in again['tasks'])
    with store.connect() as db: assert db.execute("SELECT approved FROM sources WHERE id='lever:HeldOutNative'").fetchone()[0]==1


def test_one_failed_provider_does_not_block_other_and_queries_are_dispatched(tmp_path,monkeypatch):
    calls=fixture_network(monkeypatch)
    def scraper(**kw):
        calls.append(('query',kw))
        if kw['site_name']==['linkedin']: raise RuntimeError('fixture outage')
        return pd.DataFrame([{'job_url':'https://example.org/job/2','title':'Python Developer','company':'Example'}])
    monkeypatch.setitem(sys.modules,'jobspy',SimpleNamespace(scrape_jobs=scraper))
    store=Store(tmp_path/'app.db');store.save_profile({'skills':['Python']})
    result=run(store,regions=['Germany'],max_attempts=2,providers=['linkedin','indeed'],project=False)
    assert result['counts']['failed']==1 and result['counts']['succeeded']==1
    assert result['status']=='partial' and len(store.jobs())==1
    assert {x[1]['search_term'] for x in calls if x[0]=='query'}=={'Python Developer'}


def test_quality_comparable_errors_vs_valid_empty(tmp_path):
    from jobhunter_app.discovery_state import ensure
    from jobhunter_app.search_coverage import observe
    store=Store(tmp_path/'app.db');ensure(store)
    for i in range(3): empty=observe(store,'s','query-a',{'valid_records':0,'invalid':0})
    assert empty['state']=='observed' and empty['outcome']=='valid_empty'
    for i in range(3): broken=observe(store,'s','query-b',{'valid_records':0,'invalid':2})
    assert broken['state']=='degraded'
    assert observe(store,'s','query-c',error='ValueError')['state']=='observed'


def test_cancelled_and_budgeted_work_persist_without_network(tmp_path):
    import threading
    store=Store(tmp_path/'app.db');store.save_profile({'skills':['Python']})
    cancel=threading.Event();cancel.set()
    result=run(store,cancel_event=cancel,project=False)
    assert result['status']=='cancelled' and result['counts']['dispatched']==0
    assert result['counts']['cancelled']==result['counts']['planned']


def test_gap_dispatches_next_variant_after_valid_empty(tmp_path,monkeypatch):
    from jobhunter_app.sources import POLICIES
    calls=[]
    monkeypatch.setitem(POLICIES['jobspy_indeed'],'cooldown',0)
    def scrape(**kw):
        calls.append(kw['search_term'])
        return pd.DataFrame([]) if kw['search_term']=='Python Developer' else pd.DataFrame([{'title':'Backend Engineer','company':'Example','job_url':'https://example.org/gap','description':'Python'}])
    monkeypatch.setitem(sys.modules,'jobspy',SimpleNamespace(scrape_jobs=scrape))
    store=Store(tmp_path/'app.db');store.save_profile({'skills':['Python']})
    result=run(store,max_attempts=2,providers=['indeed'],project=False)
    assert calls==['Python Developer','Backend Engineer']
    assert result['coverage'][0]['gap'] and not result['coverage'][1]['gap']
    assert result['counts']['canonical_insertions']==1


def test_search_api_explicit_setup_and_scoped_credentials(monkeypatch):
    import pytest
    from jobhunter_app.search_provider import BraveSearch,validate_scope
    with pytest.raises(ValueError): BraveSearch()
    with pytest.raises(ValueError): validate_scope('https://evil.example/search',{'X-Subscription-Token':'synthetic'})
    for key in ('JOBHUNTER_SEARCH_ACCESS_APPROVED','JOBHUNTER_SEARCH_COST_APPROVED'): monkeypatch.setenv(key,'1')
    monkeypatch.setenv('BRAVE_SEARCH_API_KEY','synthetic-not-a-real-key')
    def get(url,**kw):
        assert kw['credential_scope']=='brave_search' and 'q=' in url
        return json.dumps({'web':{'results':[{'url':'https://jobs.lever.co/Unseeded/1'}]}}).encode(),'application/json'
    monkeypatch.setattr('jobhunter_app.network.get',get)
    from jobhunter_app.search_strategy import plan
    assert BraveSearch().search(plan({'skills':['Python']})[0][0])[0]['url'].endswith('/Unseeded/1')


def test_confirmed_group_yield_changes_priority_but_cold_start_explores():
    from jobhunter_app.search_coverage import priority
    task={'id':'a','source_id':'s','order':0}
    baseline=priority(task,[{'source_id':'s','result':{'inserted':100,'new_confirmed_relevant_groups':0}}])
    useful=priority(task,[{'source_id':'s','result':{'inserted':1,'new_confirmed_relevant_groups':1}}])
    assert useful<baseline
    assert priority({'id':'b','source_id':'unseen','order':1},[])<baseline


import pytest
@pytest.mark.parametrize('language,term',[('de','Python Entwickler'),('ar','مطور بايثون')])
def test_localized_query_is_really_dispatched_and_retained(tmp_path,monkeypatch,language,term):
    calls=[]
    def scrape(**kw):
        calls.append(kw)
        return pd.DataFrame([{'title':term,'job_url':'https://example.org/localized/1','company':'Example','description':'Python'}])
    monkeypatch.setitem(sys.modules,'jobspy',SimpleNamespace(scrape_jobs=scrape))
    store=Store(tmp_path/'app.db');store.save_profile({'skills':['Python']})
    result=run(store,languages=[language],regions=['Germany'],providers=['indeed'],max_attempts=1,project=False)
    assert calls[0]['search_term']==term and calls[0]['country_indeed']=='Germany'
    assert result['counts']['canonical_insertions']==1 and store.jobs()[0]['title']==term


def test_restart_marks_interrupted_tasks_and_preserves_intent(tmp_path,monkeypatch):
    import threading
    store=Store(tmp_path/'app.db');store.save_profile({'skills':['Python']})
    def crash(*a,**kw): raise KeyboardInterrupt('simulated process stop')
    monkeypatch.setattr('jobhunter_app.sources.scan',crash)
    with pytest.raises(KeyboardInterrupt): run(store,providers=['indeed'],max_attempts=1,project=False)
    with store.connect() as db: old=db.execute('SELECT id FROM search_runs').fetchone()[0]
    reopened=Store(tmp_path/'app.db');cancel=threading.Event();cancel.set()
    run(reopened,providers=['indeed'],cancel_event=cancel,project=False)
    prior=report(reopened,old)
    assert prior['status']=='interrupted'
    assert all(x['status']=='deferred' for x in prior['persisted_tasks'])
    assert reopened.profile()['skills']==['Python']
