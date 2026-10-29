"""Local named filters: persistence, namespace isolation and no side effects."""
import json
from concurrent.futures import ThreadPoolExecutor
import pytest
from jobhunter_app.store import Store
from jobhunter_app.saved_searches import listing,save,delete,run
from jobhunter_app.workflow import settings,DEFAULTS
from tests.test_local_store import JOB,PROFILE
from tests.test_web_local import web,request,token

@pytest.fixture
def store(tmp_path):
 s=Store(tmp_path/'searches.sqlite3');s.save_profile(PROFILE);s.ingest([JOB]);s.evaluate();return s

def value(**kw):return dict(name='Python review',query='Python',status='',**kw) if not kw else {**value(),**kw}

def test_empty_no_writes(store):
 with store.connect() as db:before=db.total_changes;assert db.execute('SELECT COUNT(*) FROM workflow_settings').fetchone()[0]==0
 assert listing(store)==[]
 with store.connect() as db:assert db.execute('SELECT COUNT(*) FROM workflow_settings').fetchone()[0]==0

def test_crud_reopen_live_results(store):
 a=save(store,value());assert listing(Store(store.path))==[a];assert len(run(store,a['id'])['jobs'])==1
 b=save(store,value(name='Renamed',query='no such keyword'),search_id=a['id']);assert b['id']==a['id'];assert run(store,a['id'])['jobs']==[]
 assert delete(store,a['id'])=={'deleted':True};assert listing(store)==[]

def test_saved_run_equals_inbox(store):
 job=store.jobs()[0];store.set_status(job['id'],'saved','PRIVATE NOTE');a=save(store,value(status='saved'))
 assert run(store,a['id'])['jobs']==store.jobs('Python','saved')
 store.set_status(job['id'],'applied');assert run(store,a['id'])['jobs']==[]

@pytest.mark.parametrize('patch',[{'name':''},{'name':' '*5},{'name':'a'*81},{'name':None},{'name':True},{'name':'x\ny'},{'query':None},{'query':False},{'query':'a'*1001},{'query':'x\x00y'},{'status':'bogus'},{'status':[]},{'status':None}])
def test_bad_fields_atomic(store,patch):
 with pytest.raises(ValueError):save(store,value(**patch))
 assert listing(store)==[]

@pytest.mark.parametrize('bad',[None,[],{}, {'name':'x'}, {**value(),'schedule':True}])
def test_strict_object(store,bad):
 with pytest.raises(ValueError):save(store,bad)

@pytest.mark.parametrize('bad',['','abc','A'*32,123,None,'../x'])
def test_invalid_ids(store,bad):
 for fn in (delete,run):
  with pytest.raises(ValueError):fn(store,bad)

def test_missing_valid_id(store):
 for fn in (delete,run):
  with pytest.raises(ValueError,match='not found'):fn(store,'a'*32)
 with pytest.raises(ValueError):save(store,value(),search_id='a'*32)

def test_names_unicode_trim_duplicates_and_literal_queries(store):
 a=save(store,value(name='  Développeur وظيفة  ',query="%' OR 1=1 --"));assert a['name']=='Développeur وظيفة';assert run(store,a['id'])['jobs']==[]
 with pytest.raises(ValueError,match='already exists'):save(store,value(name='DÉVELOPPEUR وظيفة'))
 assert len(listing(store))==1

def test_maximum_and_edit_at_cap(store):
 items=[save(store,value(name=str(i))) for i in range(20)]
 with pytest.raises(ValueError,match='20'):save(store,value(name='over'))
 save(store,value(name='edit'),search_id=items[0]['id']);delete(store,items[1]['id']);save(store,value(name='replacement'));assert len(listing(store))==20

def test_profile_isolation(store):
 store.save_profile(PROFILE,'other');a=save(store,value())
 assert listing(store,'other')==[]
 for fn in (run,delete):
  with pytest.raises(ValueError):fn(store,a['id'],'other')
 with pytest.raises(ValueError):save(store,value(),'other',a['id'])
 assert listing(store)==[a]

def test_unconfigured_profile(store):
 for fn,args in [(listing,()),(save,(value(),)),(run,('a'*32,)),(delete,('a'*32,))]:
  with pytest.raises(ValueError,match='profile'):fn(store,*args,profile_id='missing')

def test_digest_settings_preserved_both_directions(store):
 config={**DEFAULTS,'enabled':True,'threshold':42};settings(store,value=config)
 a=save(store,value());assert settings(store)==config
 settings(store,value={'days':12});assert listing(store)==[a];assert settings(store)=={**DEFAULTS,'days':12}
 delete(store,a['id']);assert settings(store)['days']==12

def test_search_first_digest_defaults(store):
 a=save(store,value());assert settings(store)==DEFAULTS
 settings(store,value={'max_items':2});assert listing(store)==[a]

def test_no_profile_match_state_or_private_audit_changes(store):
 before=(store.profile(),store.jobs(),store.summary())
 a=save(store,value(name='PRIVATE SEARCH',query='SECRET KEYWORD'));run(store,a['id']);delete(store,a['id'])
 assert before==(store.profile(),store.jobs(),store.summary())
 with store.connect() as db:
  text=' '.join(r[0] for r in db.execute("SELECT details FROM audit WHERE event LIKE 'saved_search_%'"))
 assert 'PRIVATE SEARCH' not in text and 'SECRET KEYWORD' not in text

def test_backup_preserves(store,tmp_path):
 a=save(store,value());p=tmp_path/'backup.sqlite3';store.backup(p);assert listing(Store(p))==[a]

def test_concurrent_independent_writes_not_lost(store):
 def add(i):return save(store,value(name=str(i)))
 with ThreadPoolExecutor(max_workers=5) as pool:list(pool.map(add,range(15)))
 assert len(listing(store))==15

def test_concurrent_digest_and_search_writes(store):
 def worker(i):
  if i%2:settings(store,value={'days':i})
  else:save(store,value(name=str(i)))
 with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(worker,range(10)))
 assert len(listing(store))==5;assert settings(store)['days'] in (1,3,5,7,9)

@pytest.mark.parametrize('offset',[-1,True,'1',None])
def test_bad_offset(store,offset):
 a=save(store,value())
 with pytest.raises(ValueError):run(store,a['id'],offset=offset)

def test_http(web):
 t={'X-JobHunter-Token':token(web)};s=web[0];s.ingest([JOB])
 assert request(web,'GET','/searches.js')[0]==200
 assert request(web,'GET','/api/saved-searches')[0]==200
 assert request(web,'POST','/api/saved-search',{'search':value()})[0]==403
 status,_,raw=request(web,'POST','/api/saved-search',{'search':value()},t);assert status==200;a=json.loads(raw)
 assert request(web,'GET','/api/saved-search-run?id='+a['id'])[0]==200
 assert request(web,'POST','/api/saved-search',{'id':a['id'],'search':value(name='Changed')},t)[0]==200
 assert request(web,'POST','/api/saved-search-delete',{'id':a['id']},t)[0]==400
 assert request(web,'POST','/api/saved-search-delete',{'id':a['id'],'confirmed':True},t)[0]==200
 assert request(web,'GET','/api/saved-search-run?id='+a['id'])[0]==400
 assert request(web,'GET','/api/saved-searches',headers={'Host':'evil.example'})[0]==403

def test_all_jobs_default_and_pagination(store):
 store.ingest([{**JOB,'url':f'https://example.org/page/{i}','title':f'Python role {i}'} for i in range(201)])
 a=save(store,value(query=''));first=run(store,a['id']);second=run(store,a['id'],offset=200)
 assert len(first['jobs'])==200 and len(second['jobs'])==2
 assert not ({x['id'] for x in first['jobs']}&{x['id'] for x in second['jobs']})

def test_reads_and_runs_do_not_write_or_connect(store,monkeypatch):
 import socket
 a=save(store,value())
 def denied(*args,**kwargs):raise AssertionError('Network forbidden')
 monkeypatch.setattr(socket,'create_connection',denied)
 with store.connect() as db:before=[tuple(r) for r in db.execute('SELECT * FROM audit')]
 listing(store);run(store,a['id'])
 with store.connect() as db:assert before==[tuple(r) for r in db.execute('SELECT * FROM audit')]

def test_saved_search_namespace_cannot_be_set_via_digest_settings(store):
 a=save(store,value())
 with pytest.raises(ValueError):settings(store,value={'saved_searches':[]})
 assert listing(store)==[a]

def test_profile_edits_do_not_delete_filters(store):
 a=save(store,value());store.save_profile({**PROFILE,'name':'Changed'})
 assert listing(store)==[a]
