import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from agents.cv_tailor import CVTailor
from utils.pdf_generator import generate_cv_pdf,_md_to_html_cv,_md_to_html_cover_letter,_deny_external_resource
from utils.evaluation_store import append_evaluation,load_evaluations
from agents.evaluator import Evaluator
import run_evaluate


def test_retired_cv_entry_points_never_write(tmp_path):
    path=tmp_path/'cv.pdf'
    with pytest.raises(RuntimeError):CVTailor(output_dir=str(tmp_path))
    assert not generate_cv_pdf('content',str(path))['success']
    with pytest.raises(RuntimeError):_md_to_html_cv('content')
    assert not path.exists()


def test_cover_renderer_escapes_and_blocks_resources():
    html=_md_to_html_cover_letter('<script>alert(1)</script>', '<img src=x>', '<b>company</b>', '<i>role</i>')
    assert '<script>' not in html and '<img src=x>' not in html
    assert '&lt;script&gt;' in html and '&lt;b&gt;' in html
    with pytest.raises(ValueError):_deny_external_resource('file:///etc/passwd')


def test_concurrent_json_updates_never_lost(tmp_path):
    p=tmp_path/'evaluations.json'
    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(lambda i:append_evaluation({'url':f'https://example.com/{i}'},p),range(30)))
    assert len(load_evaluations(p))==30
    assert not list(tmp_path.glob('*.tmp'))


def test_json_rejects_malformed_array_and_nan(tmp_path):
    p=tmp_path/'eval.json';p.write_text('[null]')
    with pytest.raises(ValueError):append_evaluation({'url':'https://example.com'},p)
    assert p.read_text()=='[null]'
    with pytest.raises(ValueError):append_evaluation({'score':float('nan')},tmp_path/'new.json')


def test_profile_summary_no_fabricated_languages_or_degrees():
    evaluator=object.__new__(Evaluator);evaluator.profile={}
    summary=evaluator._make_profile_summary()
    for invented in ['Nile University','Artificial Intelligence','Arabic (Native)','German (C1)','English (C2)']:
        assert invented not in summary


class FakeEvaluator:
    cv_content='Python'
    def __init__(self,success=True):self.success=success;self.tracked=False
    def evaluate(self,job):return {'success':self.success,'global_score':2,'url':job['url'],'company':job['company'],'title':job['title']}
    def _update_tracker(self,result):self.tracked=True

class Telegram:
    def notify_evaluation(self,e):return True

JOB={'url':'https://example.com/jobs/1','company':'Example','title':'Developer','description':'Python'}


def test_failed_eval_remains_pending(monkeypatch):
    def forbidden(*a):pytest.fail('Failed evaluation must remain pending')
    monkeypatch.setattr(run_evaluate,'mark_job_checked',forbidden)
    result=asyncio.run(run_evaluate.evaluate_job(JOB.copy(),FakeEvaluator(False),None,None,3.5,Telegram()))
    assert result['success'] is False


def test_persistence_failure_does_not_mark_processed(monkeypatch):
    import utils.evaluation_store as persistence
    import sys, types
    monkeypatch.setitem(sys.modules, 'utils.excel_export', types.SimpleNamespace(update_job_entry=lambda *a: None))
    def fail(*a):raise OSError('disk full')
    def forbidden(*a):pytest.fail('Not durably stored; cannot mark processed')
    monkeypatch.setattr(persistence,'append_evaluation',fail)
    monkeypatch.setattr(run_evaluate,'mark_job_checked',forbidden)
    monkeypatch.setattr(run_evaluate,'log_below_threshold',lambda *a:None)
    evaluator=FakeEvaluator()
    with pytest.raises(OSError):asyncio.run(run_evaluate.evaluate_job(JOB.copy(),evaluator,None,None,3.5,Telegram()))
    assert not evaluator.tracked


def test_legacy_create_cv_cannot_override_policy():
    with pytest.raises(ValueError):asyncio.run(run_evaluate.evaluate_job(JOB.copy(),None,None,None,3.5,None,create_cv=True))


def test_short_jd_is_not_falsely_closed():
    from utils.jd_fetcher import _check_expired
    assert not _check_expired('Python engineer needed. Apply today.','https://example.com/1')
    assert _check_expired('This job has expired','https://example.com/1')


def test_access_denial_never_triggers_browser_or_fabricated_evaluation(monkeypatch):
    from utils.jd_fetcher import FetchResult
    async def blocked(url):return FetchResult(url=url,success=False,error='HTTP 403')
    async def forbidden(*a):pytest.fail('Access restriction must not trigger browser fallback')
    def no_evaluation(*a):pytest.fail('No description means no evaluation')
    evaluator=FakeEvaluator();evaluator.evaluate=no_evaluation
    monkeypatch.setattr(run_evaluate,'fetch_jd',blocked)
    monkeypatch.setattr(run_evaluate,'fetch_jd_playwright',forbidden)
    job={k:v for k,v in JOB.items() if k!='description'}
    assert not asyncio.run(run_evaluate.evaluate_job(job,evaluator,None,None,3.5,Telegram()))['success']


def test_evaluator_refuses_missing_description_before_provider_call():
    e=object.__new__(Evaluator)
    result=e.evaluate({'company':'Example','title':'Developer','url':'https://example.com/1'})
    assert not result['success']


def test_alternate_provider_stops_immediately_on_quota():
    from agents.openrouter_client import OpenRouterClient,ChatResponse
    client=OpenRouterClient(api_key='synthetic-test-key',models=['first','second']);calls=[]
    def fake(**kwargs):calls.append(kwargs['model']);return ChatResponse(content='',model_used='first',success=False,error='Rate limited (429)')
    client._request=fake
    assert not client.chat('system','user').success
    assert calls==['first']


def test_numbered_accounts_ignored(monkeypatch):
    from agents.smart_router import SmartRouter
    monkeypatch.delenv('OPENROUTER_API_KEY',raising=False);monkeypatch.setenv('OpenRouter','sk-or-synthetic-primary')
    monkeypatch.setenv('OpenRouter2','sk-or-synthetic-second');router=object.__new__(SmartRouter)
    assert router._load_openrouter_keys()==['sk-or-synthetic-primary']
