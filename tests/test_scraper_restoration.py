"""Additive scraper restoration contracts; all provider calls are fixtures."""
import asyncio
import json
import sys
from types import SimpleNamespace
import pytest
from jobhunter_app.store import Store, dump, now
from jobhunter_app.sources import Source, register, scan, normalize, POLICIES
from jobhunter_app.automatic import configure, STARTERS, KEY, SEED_KEY
from jobhunter_app.expanded_sources import collect
from scanners.jobspy_scanner import JobSpyScanner
from scanners.base import JobPosting, ScanResult
from scanners.compat import mirror_to_pipeline, mirror_to_inbox
from scanners.workday import DirectAPIScanner, APIEndpoint

ROW={'title':'Software Engineer','url':'https://example.com/jobs/1','company':'Example',
     'location':'Cairo, Egypt','description':'Python required.','date_posted':'2026-10-29',
     'salary':'USD 100-200 year','employment_type':'fulltime'}

class Frame:
    def __init__(self, rows=(), errors=None):
        self.rows=list(rows);self.empty=not self.rows;self.attrs={'errors':errors or {}}
    def iterrows(self):return enumerate(self.rows)


def install(monkeypatch, frame):
    calls=[]
    def scrape_jobs(**kw):calls.append(kw);return frame
    monkeypatch.setitem(sys.modules,'jobspy',SimpleNamespace(scrape_jobs=scrape_jobs))
    return calls


def test_original_searches_not_replaced_and_german_added():
    from jobhunter_app.expanded_sources import config
    c=config();searches=JobSpyScanner(c).searches
    assert len(searches)==210
    searches = [s for s in searches if len(s['sites']) == 4]
    assert len(searches)==98
    assert {'Egypt','Oman','United Arab Emirates','Germany','Remote','Austria','Switzerland'} == {s['location'] for s in searches}
    assert all({'linkedin','indeed','google','bayt'}<=set(s['sites']) for s in searches)
    assert {'AI Engineer','Technical Trainer','Softwareentwickler','Datenanalyst'} <= {s['term'] for s in searches}


def test_jobspy_metadata_offset_and_missing_values(monkeypatch):
    row={'job_url':ROW['url'],'title':ROW['title'],'company':'Example','description':'x'*6000,
         'location':'Cairo','date_posted':'NaT','min_amount':100,'max_amount':float('inf'),
         'currency':'USD','interval':'year','job_type':'fulltime','site':'indeed'}
    calls=install(monkeypatch,Frame([row,{'job_url':float('nan'),'title':'missing'}]))
    jobs=JobSpyScanner({})._run_search({'term':'Engineer','location':'Egypt','sites':['indeed'],'offset':30})
    assert len(jobs)==1 and len(jobs[0].description)==6000
    assert jobs[0].date_posted=='' and jobs[0].salary=='USD 100 year' and jobs[0].employment_type=='fulltime'
    assert calls[0]['country_indeed']=='Egypt' and calls[0]['offset']==30 and calls[0]['fetch_description']


def test_provider_failure_not_empty_success_and_google_parameter(monkeypatch):
    calls=install(monkeypatch,Frame(errors={'google':'no job data returned'}))
    with pytest.raises(RuntimeError,match='provider failure'):
        JobSpyScanner({})._run_search({'term':'Softwareentwickler','location':'Germany','sites':['google']})
    assert calls[0]['google_search_term']=='Softwareentwickler jobs in Germany'


def test_partial_provider_results_and_errors_survive(monkeypatch):
    install(monkeypatch,Frame([{'job_url':ROW['url'],'title':ROW['title'],'company':'Example','site':'indeed'}],{'google':'unavailable'}))
    async def no_wait(*a):pass
    monkeypatch.setattr('scanners.jobspy_scanner.asyncio.sleep',no_wait)
    r=asyncio.run(JobSpyScanner({'jobspy_searches':[{'term':'Engineer','location':'Egypt'}]}).scan())
    assert r.job_count==1 and r.error_count==1


def test_upgrade_keeps_existing_pause_jobs_profile_and_new_seed_once(tmp_path):
    store=Store(tmp_path/'app.db');store.save_profile({'name':'Private','skills':['Python'],'facts':[]})
    store.ingest([ROW]);register(store,'jobspy_indeed','configured',False)
    with store.connect() as db:db.execute('INSERT INTO workflow_settings VALUES(?,?,?)',('default',dump({KEY:{'version':1,'enabled':False},'saved_searches':[{'retain':True}]}),now()))
    configure(store);configure(store)
    with store.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM sources').fetchone()[0]==len(STARTERS)
        assert not db.execute("SELECT approved FROM sources WHERE id='jobspy_indeed:configured'").fetchone()[0]
        value=json.loads(db.execute('SELECT data FROM workflow_settings').fetchone()[0])
    assert not value[KEY]['enabled'] and value['saved_searches']==[{'retain':True}]
    assert value[SEED_KEY]==2 and store.summary()['total_jobs']==1 and store.profile()['name']=='Private'


def test_jobspy_checkpoint_rotation_and_pagination(monkeypatch):
    calls=[]
    def search(self,s):calls.append(s);return [JobPosting(**ROW)]*min(50,s['results_wanted'])
    monkeypatch.setattr(JobSpyScanner,'_run_search',search)
    first=collect(Source('jobspy_indeed','configured'))
    second=collect(Source('jobspy_indeed','configured'),first.checkpoint)
    assert calls[0]['offset']==0 and calls[1]['offset']==30
    assert second.checkpoint['search_index']==1 and second.checkpoint['page']==0
    assert first.metrics['configured_queries']==98 and not first.metrics['coverage_complete']


def test_legacy_and_dashboard_connected_without_dropping_duplicate_sightings(tmp_path):
    a=mirror_to_pipeline(tmp_path,[ROW]);b=mirror_to_pipeline(tmp_path,[ROW])
    assert a['new_added']==1 and b['new_added']==0
    assert (tmp_path/'pipeline.md').read_text().count(ROW['url'])==1
    assert json.loads((tmp_path/'jd_cache.json').read_text())[ROW['url']]['description']==ROW['description']
    assert mirror_to_inbox([ROW],tmp_path)['inserted']==1
    assert mirror_to_inbox([{**ROW,'description':''}],tmp_path)['updated']==1
    assert Store(tmp_path/'jobhunter.sqlite3').jobs()[0]['description']==ROW['description']


def test_same_title_company_different_locations_not_collapsed(tmp_path):
    from utils.dedup import DeduplicatorStore
    dedup=DeduplicatorStore(str(tmp_path));dedup.mark_seen(ROW)
    assert not dedup.is_duplicate({**ROW,'url':'https://example.com/jobs/2','location':'Berlin, Germany'})[0]
    assert dedup.is_duplicate({**ROW,'url':'https://example.com/jobs/3'})[0]


@pytest.mark.parametrize('kind',['remoteok','weworkremotely'])
def test_public_feed_collection_and_idempotent_intake(tmp_path,monkeypatch,kind):
    if kind=='remoteok':
        body=json.dumps([{'legal':'attribution required'}, {'id':1,'position':'Engineer','company':'Example','url':ROW['url'],'description':'<p>Python</p>','date':'2026-10-29'}]).encode();typ='application/json'
    else:
        body=b'<rss><channel><item><title>Example: Engineer</title><link>https://example.com/jobs/1</link><description>Python</description><region>Remote</region><type>Full-Time</type><pubDate>Thu, 29 Oct 2026 12:00:00 GMT</pubDate></item></channel></rss>';typ='application/rss+xml'
    monkeypatch.setattr('jobhunter_app.network.get',lambda *a,**kw:(body,typ))
    store=Store(tmp_path/'app.db');sid=register(store,kind,'remote',True)
    result=scan(store,sid);assert result['inserted']==1
    rows=collect(Source(kind,'remote')).payload
    assert store.ingest(rows)['updated']==1 and store.jobs()[0]['attribution']


def test_arbeitnow_actual_300_row_page_contract(monkeypatch):
    body=json.dumps({'data':[{'title':'Engineer'}]*300,'links':{'next':'https://www.arbeitnow.com/api/job-board-api?page=2'}}).encode()
    monkeypatch.setattr('jobhunter_app.network.get',lambda *a,**kw:(body,'application/json'))
    from jobhunter_app.collection import collect as collect_old
    r=collect_old(Source('arbeitnow','de'));assert len(r.payload['data'])==300 and r.checkpoint['page']==2


def test_ats_large_payload_bound_scoped_not_global(monkeypatch):
    calls=[]
    def get(*args,**kwargs):calls.append(kwargs);return b'{"jobs":[]}', 'application/json'
    monkeypatch.setattr('jobhunter_app.network.get',get)
    from jobhunter_app.sources import fetch
    fetch(Source('greenhouse','example'));fetch(Source('remotive','remote'))
    assert calls==[{'max_bytes':32*1024*1024},{}]


def test_smartrecruiters_display_name_account_and_detail(monkeypatch):
    calls=[]
    class Response:
        def __init__(self,data):self.data=data
        def raise_for_status(self):pass
        def json(self):return self.data
    class Client:
        def __init__(self,**kw):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*a):pass
        async def get(self,url,**kw):
            calls.append((url,kw))
            return Response({'content':[{'id':'1'}],'totalFound':1} if url.endswith('/postings') else {'name':'Engineer','applyUrl':ROW['url'],'company':{'name':'Bosch'},'location':{'city':'Berlin','country':'Germany'},'releasedDate':'2026-10-29','typeOfEmployment':{'label':'Full-time'},'jobAd':{'sections':{'jobDescription':{'text':'Python required'}}}})
    monkeypatch.setattr('scanners.workday.httpx.AsyncClient',Client)
    scanner=DirectAPIScanner({'tracked_companies':[{'name':'Bosch','scan_method':'direct-api','search_terms':['Engineer']}]})
    result=asyncio.run(scanner.scan())
    assert result.job_count==1 and not result.errors
    assert all('/BoschGroup/' in url for url,_ in calls)
    assert result.jobs[0].description=='Python required' and result.jobs[0].employment_type=='Full-time'


def test_direct_api_failures_visible(monkeypatch):
    scanner=DirectAPIScanner({'tracked_companies':[{'name':'Bosch','scan_method':'direct-api'}]})
    async def fail(*a):raise RuntimeError('HTTP403')
    monkeypatch.setattr(scanner,'_scan_smartrecruiters',fail)
    result=asyncio.run(scanner.scan());assert result.error_count==1 and not result.jobs


def test_existing_legacy_workspace_restored_once_with_original_bytes(tmp_path):
    from scanners.compat import restore_existing_legacy
    p=tmp_path/'pipeline.md';content='# Job Pipeline\n\n## Pending\n\n- [ ] https://example.com/jobs/1 | Example | Software Engineer [Cairo]\n'
    p.write_text(content)
    store=Store(tmp_path/'app.db');store.save_profile({'name':'','skills':[],'facts':[]})
    first=restore_existing_legacy(store);second=restore_existing_legacy(store)
    assert first['jobs_inserted']==1 and first==second and store.summary()['total_jobs']==1
    assert p.read_text()==content and list((tmp_path/'migration-backups').glob('*/pipeline.md'))


def test_ashby_salary_preserved_and_lever_commitment():
    ashby=normalize(Source('ashby','example'),{'jobs':[{'title':'Engineer','company':'Example','jobUrl':ROW['url'],'isListed':True,'compensation':{'scrapeableCompensationSalarySummary':'$100K - $120K'},'employmentType':'FullTime'}]})[0]
    lever=normalize(Source('lever','example'),[{'text':'Engineer','hostedUrl':ROW['url'],'categories':{'commitment':'Full-time'}}])[0]
    assert ashby['salary']=='$100K - $120K' and lever['employment_type']=='Full-time'


def test_board_structured_salary_and_employment_type():
    from jobhunter_app.authorized_boards import parse
    item={'@type':'JobPosting','title':'Engineer','hiringOrganization':{'name':'Example'},
          'url':'https://wuzzuf.net/jobs/p/example','description':'Python required',
          'employmentType':['FULL_TIME','CONTRACTOR'],
          'baseSalary':{'currency':'EGP','value':{'minValue':20000,'maxValue':30000,'unitText':'MONTH'}}}
    rows,_,_=parse('wuzzuf',('<script type="application/ld+json">'+json.dumps(item)+'</script>').encode(),'https://wuzzuf.net/jobs/p/example')
    assert rows[0]['salary']=='EGP 20000-30000 MONTH' and rows[0]['employment_type']=='FULL_TIME, CONTRACTOR'
