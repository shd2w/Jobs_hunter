"""R02/R03: real gated execution, fake external JobSpy boundary only."""
from dataclasses import replace
import pytest
from jobhunter_app.store import Store
from jobhunter_app.sources import register, scan, POLICIES
from jobhunter_app.search_strategy import QuerySpec, plan
from scanners.base import JobPosting
from scanners.jobspy_scanner import JobSpyScanner


def query(**kw):
    return QuerySpec(**{'profile_id':'default','intent_version':'intent-a','text':'Python Developer',
        'region':'Germany','language':'en','provider':'indeed','limit':1,**kw})


def test_runtime_cursors_scope_and_atomic_intake(tmp_path,monkeypatch):
    store=Store(tmp_path/'app.db');source=register(store,'jobspy_indeed','configured',True)
    monkeypatch.setitem(POLICIES['jobspy_indeed'],'cooldown',0)
    calls=[]
    def search(self,params):
        calls.append(params)
        return [JobPosting('Quantum Wizard','https://example.org/jobs/1','Example','Germany',description='Python SQL')]
    monkeypatch.setattr(JobSpyScanner,'_run_search',search)
    a=query(); b=replace(a,text='Backend Engineer')
    assert scan(store,source,request=a,mirror_legacy=False)['inserted']==1
    scan(store,source,request=b,mirror_legacy=False)
    scan(store,source,request=a,mirror_legacy=False)
    assert [x['offset'] for x in calls]==[0,0,1]
    assert calls[0]['search_term'] if 'search_term' in calls[0] else calls[0]['term']=='Python Developer'
    with store.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM search_progress').fetchone()[0]==2
        assert db.execute('SELECT COUNT(*) FROM source_checkpoints').fetchone()[0]==0
    assert len(list(tmp_path.glob('*.pre-autonomy-v1-*')))==1
    assert replace(a,intent_version='new').signature!=a.signature
    assert replace(a,profile_id='other').signature!=a.signature
    # Source-level approval remains authoritative, irrespective of fresh signature.
    register(store,'jobspy_indeed','configured',False)
    with pytest.raises(ValueError,match='approved'): scan(store,source,request=b)


def test_runtime_hard_exclusion_and_no_yaml_change(tmp_path,monkeypatch):
    from jobhunter_app.expanded_sources import CONFIG
    before=CONFIG.read_bytes()
    store=Store(tmp_path/'app.db');source=register(store,'jobspy_indeed','configured',True)
    monkeypatch.setattr(JobSpyScanner,'_run_search',lambda *a:[JobPosting('Senior Engineer','https://example.org/2','Example')])
    result=scan(store,source,request=query(exclusions=('senior',)),mirror_legacy=False)
    assert result['inserted']==0 and result['rejected_title']==1
    assert CONFIG.read_bytes()==before


def test_generated_queries_bounded_localized_and_no_model():
    profile={'skills':['Python','SQL'],'matching':{'preferred_title_terms':['backend']},'excluded_title_terms':['Senior']}
    queries,meta=plan(profile,regions=['Germany'],languages=['en','de','ar','xx'],max_queries=100)
    assert {'Python Developer','Backend Engineer','Python Entwickler','مهندس برمجيات'} <= {q.text for q in queries}
    assert len({q.signature for q in queries})==len(queries)<=100
    assert meta['limitations']==['Unsupported query language: xx']
    assert {q.provider for q in queries}==set(__import__('scanners.jobspy_registry',fromlist=['SITES']).SITES)
    assert all(q.parameters()['sites']==[q.provider] for q in queries)
    assert len(plan(profile,max_queries=3)[0])==3
    assert plan({},max_queries=2)[1]['broad_default']


def test_progress_rolls_back_with_intake(tmp_path,monkeypatch):
    store=Store(tmp_path/'app.db');source=register(store,'jobspy_indeed','configured',True)
    monkeypatch.setattr(JobSpyScanner,'_run_search',lambda *a:[JobPosting('Engineer','https://example.org/2','Example')])
    from jobhunter_app.discovery_state import ensure
    ensure(store)
    with store.connect() as db:
        db.execute("CREATE TRIGGER fail_progress BEFORE INSERT ON search_progress BEGIN SELECT RAISE(FAIL,'injected'); END")
    with pytest.raises(ValueError): scan(store,source,request=query(),mirror_legacy=False)
    with store.connect() as db: assert db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]==0
