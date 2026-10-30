"""Real command handler + loopback HTTP; deterministic provider, not live AI proof."""
import asyncio
import json
from threading import Thread
from types import SimpleNamespace
import pytest
import run_local
from jobhunter_app.store import Store
from jobhunter_app.web import make_server
from jobhunter_app.evaluation_service import EvaluationOptions, evaluate, latest, weighted_score, apply_policy
from tests.test_web_local import request, token

PROFILE={'name':'Fixture','skills':['Python','SQL'],'languages':[],
         'excluded_title_terms':['recruiter'],
         'facts':[{'text':'Built a synthetic Python service','verified':True,'source':'fixture'},
                  {'text':'PRIVATE UNVERIFIED DEGREE','verified':False,'source':'fixture'}],
         'matching':{'preferred_title_terms':['backend'],'excluded_companies':['Excluded Corp']}}
JOBS=[{'title':title,'company':company,'url':'https://example.org/jobs/'+str(i),
       'description':description} for i,(title,company,description) in enumerate([
           ('Unfamiliar Integration Wizard','Fixture','Python and SQL; education not specified.'),
           ('Backend Developer','Fixture','Python required. German B2 required.'),
           ('Recruiter','Fixture','Python recruiting'),
           ('Backend Developer','Excluded Corp','Python'),
           ('Backend Developer','Fixture','')])]

@pytest.fixture
def setup(tmp_path):
    store=Store(tmp_path/'app.db');store.save_profile(PROFILE);store.ingest(JOBS)
    server=make_server(store,0);thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try: yield store,(store,server)
    finally: server.shutdown();server.server_close();thread.join(3)

@pytest.fixture
def provider(monkeypatch):
    calls=[]
    def response(self,**kw):
        calls.append(kw)
        return SimpleNamespace(success=True,model_used='controlled-provider/model',content=json.dumps({
            'scores':{'skills_match':5,'education_match':2,'location':3,'language':2,'growth':4},
            'global_score':5,'summary':'Fixture role','match_highlights':['Python'], 'gaps':['Unknown language proficiency'],
            'german_required':True,'german_level_required':'B2+','recommendation':'consider','reasoning':'Unknowns remain unknown.'}))
    monkeypatch.setattr('agents.smart_router.SmartRouter.__init__',lambda self:None)
    monkeypatch.setattr('agents.smart_router.SmartRouter.evaluate',response)
    return calls


def clean(r):
    return {k:v for k,v in r.items() if k not in ('started_at','finished_at') and k!='ai'} | {'ai':{k:v for k,v in r.get('ai',{}).items() if k!='evaluated_at'}}

@pytest.mark.parametrize('index',range(5))
@pytest.mark.parametrize('method',['local','ai'])
def test_actual_cli_http_equivalence(setup,provider,capsys,index,method):
    store,web=setup;job=next(j for j in store.jobs() if j['url']==JOBS[index]['url'])
    options={'method':method,'allow_provider':True,'german_policy':'reject_b2_plus_only'}
    status,_,raw=request(web,'POST','/api/evaluate',{'id':job['id'],'options':options},{'X-JobHunter-Token':token(web)})
    assert status==200;http=json.loads(raw)
    assert run_local.main(['--db',str(store.path),'evaluate',job['id'],'--method',method,'--allow-provider','--german-policy','reject_b2_plus_only'])==(2 if index==4 and method=='ai' else 0)
    cli=json.loads(capsys.readouterr().out)
    assert clean(http)==clean(cli)
    assert latest(store,job['id'])['stale'] is False
    with store.connect() as db: assert db.execute('SELECT COUNT(*) FROM evaluations').fetchone()[0]==2
    if index in (2,3):
        assert not provider
        if method=='ai': assert http['classification']=='excluded' and http['method']=='local'
    elif index==4 and method=='ai': assert http['status']=='pending' and http['error']['code']=='description_required'
    elif method=='ai':
        assert http['status']=='completed_ai' and http['score']==0 and http['ai']['pre_policy_score']==3.3
        assert http['ai']['model_reported_global_score']==5
        assert 'PRIVATE UNVERIFIED DEGREE' not in provider[0]['system_prompt']
        assert 'Not provided' in provider[0]['system_prompt']
        assert 'Oman' not in provider[0]['system_prompt']

@pytest.mark.parametrize('fallback',[False,True])
def test_failure_and_fallback_are_identical_and_persisted(setup,monkeypatch,capsys,fallback):
    store,web=setup;job=next(j for j in store.jobs() if j['title']=='Unfamiliar Integration Wizard')
    def broken(*a,**k):raise RuntimeError('PRIVATE PROVIDER SECRET')
    monkeypatch.setattr('jobhunter_app.evaluation_service.make_evaluator',broken)
    options={'method':'ai','allow_provider':True,'fallback':fallback}
    status,_,raw=request(web,'POST','/api/evaluate',{'id':job['id'],'options':options},{'X-JobHunter-Token':token(web)})
    assert status==200 and b'PRIVATE PROVIDER SECRET' not in raw
    args=['--db',str(store.path),'evaluate',job['id'],'--method','ai','--allow-provider']+(['--fallback'] if fallback else [])
    assert run_local.main(args)==(0 if fallback else 2);cli=json.loads(capsys.readouterr().out)
    assert clean(cli)==clean(json.loads(raw))
    assert cli['status']==('completed_fallback' if fallback else 'failed')
    assert cli['score'] is None and cli['method']==('local' if fallback else None)
    assert 'ai' not in cli


def test_no_provider_consent_never_calls_and_reads_do_not_migrate(setup,monkeypatch):
    store,web=setup;job=store.jobs()[0]
    assert json.loads(request(web,'GET','/api/evaluation?id='+job['id'])[2]) is None
    with store.connect() as db: assert not db.execute("SELECT 1 FROM sqlite_master WHERE name='evaluation_meta'").fetchone()
    monkeypatch.setattr('jobhunter_app.evaluation_service.make_evaluator',lambda *a:pytest.fail('No consent'))
    r=evaluate(store,job['id'],options=EvaluationOptions(method='ai',fallback=True))
    assert r['status']=='pending' and r['method'] is None
    assert list(store.path.parent.glob('*.before-evaluation-v1-*.bak'))


def test_input_change_marks_old_result_stale(setup,provider):
    store,_=setup;job=store.jobs()[0];evaluate(store,job['id'])
    store.save_profile({**PROFILE,'skills':['Rust']})
    assert latest(store,job['id'])['stale'] is True


def test_profile_changes_during_provider_call_cannot_be_current(setup,monkeypatch):
    store,_=setup;job=next(j for j in store.jobs() if j['title']=='Unfamiliar Integration Wizard')
    class E:
        def evaluate(self,job):
            store.save_profile({**PROFILE,'skills':['Rust']})
            return {'success':True,'global_score':4}
    monkeypatch.setattr('jobhunter_app.evaluation_service.make_evaluator',lambda p:E())
    r=evaluate(store,job['id'],options=EvaluationOptions('ai',True))
    assert r['status']=='partial' and latest(store,job['id'])['stale']


def test_actual_legacy_runner_uses_shared_policy(monkeypatch):
    import run_evaluate
    class E:
        cv_content='Python'
        def evaluate(self,job):return {'success':True,'global_score':4,'german_level_required':'B2+','german_required':True,'url':job['url']}
        def _update_tracker(self,r):pass
    class T:
        def notify_evaluation(self,r):pass
    saved=[]
    monkeypatch.setattr('utils.evaluation_store.append_evaluation',lambda *a,**k:saved.append(a))
    monkeypatch.setattr(run_evaluate,'mark_job_checked',lambda *a:None)
    monkeypatch.setattr(run_evaluate,'log_below_threshold',lambda *a:None)
    r=asyncio.run(run_evaluate.evaluate_job(JOBS[1].copy(),E(),None,None,3.5,T(),german_policy='reject_b2_plus_only'))
    assert r['global_score']==0 and r['evaluation_method']=='ai' and r['classification']=='rejected' and saved

@pytest.mark.parametrize('value',[{'threshold':float('nan')},{'threshold':True},{'method':'bogus'},{'fallback':'yes'},{'unknown':1}])
def test_options_reject_ambiguous_values(value):
    with pytest.raises((ValueError,TypeError)):EvaluationOptions.parse(value)


def test_weighted_score_not_model_claim_and_policy_explicit():
    assert weighted_score(dict.fromkeys(['skills_match','education_match','location','language','growth'],4))==4
    with pytest.raises(ValueError):weighted_score({'skills_match':True})
    assert apply_policy({'global_score':4,'german_required':True,'german_level_required':'B2+'},{'description':'English and German'},'reject_unless_bilingual')['global_score']==4


def test_running_status_lock_and_persistence_failure_are_honest(setup,monkeypatch):
    from filelock import FileLock
    import sqlite3
    store,web=setup;job=next(j for j in store.jobs() if j['title']=='Unfamiliar Integration Wizard')
    with FileLock(str(store.path)+'.evaluation.lock'):
        assert request(web,'POST','/api/evaluate',{'id':job['id']},{'X-JobHunter-Token':token(web)})[0]==400
    class E:
        def evaluate(self,j):
            assert latest(store,j['id'])['status']=='running'
            assert store.summary()['evaluations']['status_counts']['running']==1
            return {'success':True,'global_score':3}
    monkeypatch.setattr('jobhunter_app.evaluation_service.make_evaluator',lambda p:E())
    evaluate(store,job['id'],options=EvaluationOptions('ai',True))
    with store.connect() as db:
        db.execute("CREATE TRIGGER reject_result BEFORE UPDATE ON evaluations BEGIN SELECT RAISE(FAIL,'fixture persistence failure'); END")
    with pytest.raises(sqlite3.IntegrityError):evaluate(store,job['id'],options=EvaluationOptions('ai',True))
    assert latest(store,job['id'])['status']=='partial'  # No lock owner; never claim completed after failed commit.


def test_summary_distinguishes_new_stale_local_and_ai(setup,provider):
    store,_=setup;job=next(j for j in store.jobs() if j['title']=='Unfamiliar Integration Wizard')
    assert store.summary()['evaluations']['not_requested']==5
    evaluate(store,job['id'])
    assert next(j for j in store.jobs() if j['id']==job['id'])['match']
    assert store.summary()['evaluations']['status_counts']=={'completed_local':1}
    store.save_profile({**PROFILE,'skills':['Rust']})
    assert store.summary()['evaluations']['stale']==1


def test_invalid_actual_model_json_does_not_become_ai_score(setup,monkeypatch):
    store,_=setup;job=next(j for j in store.jobs() if j['title']=='Unfamiliar Integration Wizard')
    monkeypatch.setattr('agents.smart_router.SmartRouter.__init__',lambda self:None)
    monkeypatch.setattr('agents.smart_router.SmartRouter.evaluate',lambda *a,**k:SimpleNamespace(success=True,model_used='fixture',content='{"global_score":5,"instruction":"private model body"}'))
    r=evaluate(store,job['id'],options=EvaluationOptions('ai',True,True))
    assert r['status']=='completed_fallback' and r['score'] is None and 'private model body' not in json.dumps(r)


def test_queue_projection_reads_shared_ai_but_never_lexical_fallback(setup,monkeypatch,tmp_path):
    from jobhunter_app.pipeline import export_uaa
    store,_=setup;job=next(j for j in store.jobs() if j['title']=='Unfamiliar Integration Wizard')
    class E:
        def evaluate(self,j):return {'success':True,'global_score':4,'recommendation':'apply','title':j['title'],'company':j['company'],'url':j['url']}
    monkeypatch.setattr('jobhunter_app.evaluation_service.make_evaluator',lambda p:E())
    evaluate(store,job['id'],options=EvaluationOptions('ai',True))
    result=export_uaa(store,tmp_path/'ai.jsonl')
    assert result['exported']==0 and result['skipped']  # Existing PDF requirements retained, never fake documents.
    assert all(x['reason']!='current_evaluation_not_exportable' for x in result['skipped'])
    evaluate(store,job['id'])
    result=export_uaa(store,tmp_path/'local.jsonl')
    assert result['exported']==0 and result['skipped'][0]['reason']=='current_evaluation_not_exportable'
