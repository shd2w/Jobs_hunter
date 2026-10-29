"""All-platform additive routing and optional Scrapling worker contracts."""
import json
import sys
from types import SimpleNamespace
import pytest
from scanners.jobspy_registry import SITES, SCOPES
from scanners.jobspy_scanner import JobSpyScanner
from jobhunter_app.expanded_sources import JOBSPY, config, collect
from jobhunter_app.automatic import configure, STARTERS, SEED_KEY, SEED_REVISION, KEY
from jobhunter_app.sources import Source, POLICIES, register, scan
from jobhunter_app.store import Store, dump, now

ROW={'title':'Software Engineer','company':'Example','url':'https://example.com/job/1',
     'location':'Remote · India','description':'Python required','date_posted':'2026-10-29'}

class Frame:
    empty=False
    attrs={'errors':{},'warnings':{}}
    def __init__(self,site):self.site=site
    def iterrows(self):return iter([(0,{'title':ROW['title'],'company':'Example','job_url':ROW['url'],
        'location':'India','is_remote':True,'description':'Python','site':self.site})])


def test_all_platforms_registered_without_removing_original_queries():
    searches=JobSpyScanner(config()).searches
    primary=[s for s in searches if len(s['sites'])==4]
    assert len(primary)==98 and len(searches)==210
    assert set(SITES)=={site for s in searches for site in s['sites']}
    assert set(JOBSPY)<={kind for kind,_ in STARTERS}
    assert set(JOBSPY)<=set(POLICIES)
    for site in SCOPES:
        assert SCOPES[site] in POLICIES['jobspy_'+site]['notice']
    for site in ('zip_recruiter','naukri','bdjobs','hellowork'):
        matches=[s for s in searches if s['sites']==[site]]
        assert len(matches)==14 and all(s['is_remote'] for s in matches)
        assert all(s['scope_notice'] for s in matches)


@pytest.mark.parametrize('site',SITES)
def test_every_platform_calls_actual_jobspy_identifier(monkeypatch,site):
    calls=[]
    def scrape_jobs(**kw):calls.append(kw);return Frame(site)
    monkeypatch.setitem(sys.modules,'jobspy',SimpleNamespace(scrape_jobs=scrape_jobs))
    rows=JobSpyScanner({})._run_search({'sites':[site],'term':'Software Engineer','location':'Germany'})
    assert calls[0]['site_name']==[site]
    assert len(rows)==1 and rows[0].source=='jobspy-'+site
    assert rows[0].location=='Remote · India'  # Never turn source country into worldwide eligibility.


@pytest.mark.parametrize('site',SCOPES)
def test_added_provider_checkpoint_and_source_ingest(monkeypatch,tmp_path,site):
    calls=[]
    def search(self,s):calls.append(s);return []
    monkeypatch.setattr(JobSpyScanner,'_run_search',search)
    result=collect(Source('jobspy_'+site,'configured'))
    assert result.checkpoint['search_index']==1 and result.checkpoint['page']==0
    assert calls[0]['sites']==[site] and calls[0]['offset']==0
    assert result.metrics['configured_queries']==(56 if site=='glassdoor' else 14)
    store=Store(tmp_path/'app.db');identity=register(store,'jobspy_'+site,'configured',True)
    result=scan(store,identity)
    assert result['inserted']==0 and result['received']==0


def test_seed_v1_upgrade_keeps_pause_checkpoint_and_quota(tmp_path):
    store=Store(tmp_path/'app.db');store.save_profile({'name':'Keep','skills':[],'facts':[]})
    identity=register(store,'jobspy_indeed','configured',False)
    with store.connect() as db:
        db.execute('INSERT INTO workflow_settings VALUES(?,?,?)',('default',dump({KEY:{'version':1,'enabled':False},SEED_KEY:1}),now()))
        db.execute('INSERT INTO source_checkpoints VALUES(?,?,?)',(identity,dump({'search_index':9,'page':1}),now()))
        db.execute('INSERT INTO provider_gates VALUES(?,?)',('jobspy_indeed','2099-01-01T00:00:00+00:00'))
    configure(store);configure(store)
    with store.connect() as db:
        assert db.execute('SELECT count(*) FROM sources').fetchone()[0]==len(STARTERS)
        row=db.execute('SELECT approved FROM sources WHERE id=?',(identity,)).fetchone()
        assert not row[0]
        assert db.execute('SELECT not_before FROM provider_gates WHERE kind=?',('jobspy_indeed',)).fetchone()[0].startswith('2099')
        assert json.loads(db.execute('SELECT data FROM source_checkpoints WHERE source_id=?',(identity,)).fetchone()[0])=={'search_index':9,'page':1}
        settings=json.loads(db.execute('SELECT data FROM workflow_settings').fetchone()[0])
    assert settings[SEED_KEY]==SEED_REVISION and not settings[KEY]['enabled']


HTML=b'''<html><head><script type="application/ld+json">{"@type":"JobPosting","title":"Software Engineer","hiringOrganization":{"name":"Example"},"description":"Python","url":"https://wuzzuf.net/jobs/p/one","jobLocation":{"address":{"addressCountry":"Egypt"}},"employmentType":"FULL_TIME","datePosted":"2026-10-29","baseSalary":{"currency":"USD","value":{"minValue":10,"maxValue":20,"unitText":"HOUR"}}}</script></head><body><a href="/jobs/p/two">More</a><a rel="next" href="/a/Software-Jobs?start=1">Next</a></body></html>'''


def test_scrapling_and_standard_parser_preserve_same_structured_fields(monkeypatch):
    pytest.importorskip('scrapling')
    from jobhunter_app.authorized_boards import parse
    monkeypatch.setenv('JOBHUNTER_AUTHORIZED_BOARD_PARSER','stdlib')
    original=parse('wuzzuf',HTML,'https://wuzzuf.net/a/Software-Jobs')
    monkeypatch.setenv('JOBHUNTER_AUTHORIZED_BOARD_PARSER','scrapling')
    added=parse('wuzzuf',HTML,'https://wuzzuf.net/a/Software-Jobs')
    assert added==original
    assert added[0][0]['salary']=='USD 10-20 HOUR'


@pytest.mark.parametrize('engine',['stdlib','scrapling'])
def test_parser_stops_challenges_and_unsafe_pagination(monkeypatch,engine):
    if engine=='scrapling':pytest.importorskip('scrapling')
    from jobhunter_app.authorized_boards import parse, AccessBlocked
    monkeypatch.setenv('JOBHUNTER_AUTHORIZED_BOARD_PARSER',engine)
    with pytest.raises(AccessBlocked):parse('wuzzuf',b'<html>Verify you are human</html>','https://wuzzuf.net/a/Jobs')
    with pytest.raises(ValueError,match='Unsafe next-page'):
        parse('wuzzuf',HTML.replace(b'/a/Software-Jobs?start=1',b'https://127.0.0.1/secret'),'https://wuzzuf.net/a/Jobs')


def test_scrapling_is_explicit_and_missing_runtime_is_not_silent(monkeypatch):
    from jobhunter_app.scrapling_parser import parser_mode,parse_page
    monkeypatch.delenv('JOBHUNTER_AUTHORIZED_BOARD_PARSER',raising=False)
    assert parser_mode()=='stdlib'
    monkeypatch.setenv('JOBHUNTER_AUTHORIZED_BOARD_PARSER','unknown')
    with pytest.raises(ValueError):parser_mode()
    monkeypatch.setitem(sys.modules,'scrapling',None)
    with pytest.raises(ImportError,match='requirements-scrapling.txt'):parse_page(HTML)


def test_invalid_provider_configuration_fails_without_network():
    with pytest.raises(ValueError,match='Unsupported JobSpy'):
        JobSpyScanner({'jobspy_providers':{'invented':{'terms':['Engineer'],'locations':['Remote']}}})

@pytest.mark.parametrize('site,expected',[('glassdoor','Germany'),('zip_recruiter','USA'),('naukri','India'),('bdjobs','Bangladesh'),('hellowork','France')])
def test_bounded_cli_defaults_to_native_provider_scope(site,expected):
    from scanners.jobspy_scanner import bounded_search
    search=bounded_search(config(),site,'Software Engineer',None,3)
    assert search['location']==expected and search['sites']==[site]
    assert search['results_wanted']==3
    if site!='glassdoor':assert search['is_remote']


def test_cli_single_site_does_not_expand_to_all_provider_searches(monkeypatch):
    import run_scan
    seen=[]
    async def fake_scan(**kwargs):
        seen.append(kwargs)
        return {'errors':[],'total_found':0}
    monkeypatch.setattr(run_scan,'run_scan',fake_scan)
    monkeypatch.setattr(sys,'argv',['run_scan.py','--site','bdjobs','--limit','2'])
    with pytest.raises(SystemExit) as exit:run_scan.main()
    assert exit.value.code==0
    registry=seen[0]['config_override']
    assert 'jobspy_providers' not in registry
    assert len(JobSpyScanner(registry).searches)==1
    assert registry['jobspy_searches'][0]['location']=='Bangladesh'


def test_repeatable_all_platform_live_runner_is_bounded_and_aggregate_only(monkeypatch,tmp_path):
    from qa import jobspy_platforms_live as runner
    calls=[]
    def child(command,**kwargs):
        calls.append((json.loads(command[-1]),kwargs))
        return SimpleNamespace(stdout='RESULT:'+json.dumps({'received':3,'valid':3,'invalid':0,'errors':{},'warnings':{},'nonempty':{'title':3}}),stderr='',returncode=0)
    monkeypatch.setattr(runner.subprocess,'run',child)
    monkeypatch.setattr(sys,'argv',['jobspy_platforms_live.py','--output',str(tmp_path),'--site','naukri','--site','hellowork'])
    assert runner.main()==0
    result=json.loads((tmp_path/'results.json').read_text())
    assert len(result)==2 and all(r['valid']==3 for r in result)
    assert {c[0]['location'] for c in calls}=={'India','France'}
    assert all(c[1]['timeout']==150 for c in calls)
    assert not any('description' in r for r in result)


def test_live_runner_timeout_is_not_empty_success(monkeypatch,tmp_path):
    from qa import jobspy_platforms_live as runner
    def child(*args,**kwargs):raise runner.subprocess.TimeoutExpired('fixture',150)
    monkeypatch.setattr(runner.subprocess,'run',child)
    monkeypatch.setattr(sys,'argv',['jobspy_platforms_live.py','--output',str(tmp_path),'--site','bdjobs'])
    assert runner.main()==1
    assert json.loads((tmp_path/'results.json').read_text())[0]['failure']=='wall_timeout'
