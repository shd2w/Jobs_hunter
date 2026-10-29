"""Private manual self-records: atomicity, snapshots, namespaces, privacy and HTTP."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import json
import socket
import pytest
from jobhunter_app.store import Store
from jobhunter_app import learning_progress as lp,learning_resources as lr
from jobhunter_app.workflow import settings,DEFAULTS
from jobhunter_app.saved_searches import listing as searches,save as save_search
from tests.test_contextual_learning import snapshot,edit
from tests.test_local_store import JOB,PROFILE
from tests.test_web_local import web,request,token

@pytest.fixture
def s(tmp_path):
 st=Store(tmp_path/'progress.sqlite3');st.save_profile({'name':'Synthetic Learner','skills':['Python'],'facts':[]});st.ingest([{**JOB,'description':'SQL required. Docker preferred. Git not required. We use Excel.'}]);st.evaluate();return st

def priority(s,skill='SQL',profile='default'):
 return next(p for p in s.learning(profile)['priorities'] if p['skill']==skill)

def make(s,skill='SQL',profile='default'):
 p=priority(s,skill,profile);return lp.create(s,skill,p['learning_options']['plan_fingerprint'],profile)

def change(s,item,status='in_progress',notes='PRIVATE PRACTICE NOTES',attested=False,profile='default'):
 return lp.update(s,item['id'],{'status':status,'notes':notes,'completed_attested':attested},item['revision'],profile)

def ns_edit(s,fn):
 with s.connect() as db:
  raw=json.loads(db.execute("SELECT data FROM workflow_settings WHERE profile_id='default'").fetchone()[0]);fn(raw)
  db.execute("UPDATE workflow_settings SET data=? WHERE profile_id='default'",(json.dumps(raw),))


def test_listing_empty_readonly_and_no_auto_assignments(s):
 before=snapshot(s);assert lp.listing(s)['items']==[] and s.learning()['capabilities']['learning_progress']
 assert snapshot(s)==before


def test_crud_explicit_completion_reopen_and_backup(s,tmp_path):
 item=make(s);assert item['revision']==1 and item['status']=='planned' and item['completed_at']==''
 started=change(s,item);assert started['revision']==2 and started['completed_at']==''
 done=change(s,started,'completed',attested=True);assert done['revision']==3 and done['completed_at']
 again=change(s,done,'completed','updated note',True);assert again['completed_at']==done['completed_at']
 reopened=change(s,again,'in_progress','reopened');assert not reopened['completed_at']
 finished=change(s,reopened,'completed','done again',True);assert finished['completed_at']>=done['completed_at']
 destination=tmp_path/'backup.sqlite3';s.backup(destination);assert lp.listing(Store(destination))['items']==[finished]
 assert lp.delete(s,finished['id'],finished['revision'],True)=={'deleted':True} and lp.listing(s)['items']==[]
 assert lp.listing(Store(destination))['items']==[finished]

@pytest.mark.parametrize('state',lp.STATES)
def test_all_current_states_are_self_recorded(s,state):
 item=make(s);updated=change(s,item,state,attested=state=='completed')
 assert updated['status']==state and bool(updated['completed_at'])==(state=='completed')
 assert s.profile()['facts']==[] and s.profile()['skills']==['Python']


def test_noop_and_duplicate_save_do_not_reset_or_write(s):
 item=make(s);item=change(s,item,'completed','PRIVATE',True);before=snapshot(s)
 assert make(s)==item and change(s,item,'completed','PRIVATE',True)==item
 assert snapshot(s)==before


def test_snapshot_detached_immutable_and_survives_guidance_disappearing(s):
 item=make(s);saved=deepcopy(item);item['snapshot']['steps'].clear();assert lp.listing(s)['items']==[saved]
 s.save_profile({'name':'Changed','skills':['SQL','Python'],'facts':[]});s.evaluate()
 assert all(p['skill']!='SQL' for p in s.learning()['priorities'])
 assert lp.listing(s)['items']==[saved]
 assert change(s,saved,'paused')['snapshot']==saved['snapshot']


def test_catalog_new_content_creates_separate_version_without_overwriting(s,tmp_path,monkeypatch):
 first=make(s);first=change(s,first,'completed','OLD PRIVATE',True);d=lr.load();d['version']='free-reading-practice-2';d['resources'][1]['exercise']['title']='New SQL practice revision'
 f=tmp_path/'catalog.json';f.write_text(json.dumps(d));monkeypatch.setattr(lr,'CATALOG',f)
 second=make(s);assert second['id']!=first['id'] and second['snapshot_hash']!=first['snapshot_hash']
 assert second['status']=='planned' and lp.listing(s)['items'][0]==first
 monkeypatch.setattr(lr,'CATALOG',tmp_path/'missing.json');assert not s.learning()['resource_catalog']['available']
 assert len(lp.listing(s)['items'])==2 and change(s,second,'in_progress')['snapshot']==second['snapshot']


def test_stale_preview_rejected_after_listing_change(s):
 p=priority(s);before=snapshot(s);f=p['learning_options']['plan_fingerprint'];s.ingest([{**JOB,'description':'SQL preferred.'}]);s.evaluate()
 with pytest.raises(ValueError,match='preview changed'):lp.create(s,'SQL',f)
 assert lp.listing(s)['items']==[]

@pytest.mark.parametrize('kind',['invalidated','stale','truncated','mixed','negated','plain','excluded'])
def test_nonpositive_unmatched_or_stale_guidance_cannot_create_practice(s,kind):
 f=priority(s)['learning_options']['plan_fingerprint']
 if kind=='invalidated':s.save_profile(s.profile())
 elif kind=='stale':edit(s,lambda m:m.update(fingerprints={}))
 elif kind=='truncated':edit(s,lambda m:m.update(requirements_truncated=True))
 else:
  description={'mixed':'SQL required. SQL not required.','negated':'SQL not required.','plain':'We use SQL.','excluded':'SQL required.'}[kind]
  if kind=='excluded':s.save_profile({'name':'Synthetic','skills':[],'facts':[],'excluded_title_terms':[JOB['title']]})
  s.ingest([{**JOB,'description':description}]);s.evaluate()
 with pytest.raises(ValueError):lp.create(s,'SQL',f)
 assert lp.listing(s)['items']==[]

@pytest.mark.parametrize('bad',['',None,123,'bad','A'*64,'x'*64,'a'*65,'../secret'])
def test_invalid_offer_fingerprints_atomic(s,bad):
 before=snapshot(s)
 with pytest.raises(ValueError):lp.create(s,'SQL',bad)
 assert snapshot(s)==before

@pytest.mark.parametrize('bad',['',None,True,'x'*81,'x\x00y','\ud800'])
def test_invalid_or_unknown_skills(s,bad):
 with pytest.raises(ValueError):lp.create(s,bad,'a'*64)
 assert lp.listing(s)['items']==[]

@pytest.mark.parametrize('patch',[
 {'status':'bad'},{'status':[]},{'notes':None},{'notes':True},{'notes':'x'*2001},{'notes':'bad\x00note'},
 {'notes':'bad\ud800'},{'completed_attested':'true'},{'completed_attested':1},{'completed_attested':None},
 {'status':'completed','completed_attested':False},{'status':'paused','completed_attested':True},
])
def test_bad_updates_atomic(s,patch):
 item=make(s);v={'status':'in_progress','notes':'ok','completed_attested':False};v.update(patch);before=snapshot(s)
 with pytest.raises(ValueError):lp.update(s,item['id'],v,item['revision'])
 assert snapshot(s)==before

@pytest.mark.parametrize('bad',[None,[],{}, {'status':'planned'}, {'status':'planned','notes':'','completed_attested':False,'snapshot':{}}])
def test_strict_update_object(s,bad):
 item=make(s)
 with pytest.raises(ValueError):lp.update(s,item['id'],bad,1)
 assert lp.listing(s)['items']==[item]

@pytest.mark.parametrize('revision',[None,True,False,0,-1,1.0,'1',1_000_001])
def test_invalid_expected_revision(s,revision):
 item=make(s)
 for fn,args in ((lp.update,(s,item['id'],{'status':'planned','notes':'','completed_attested':False},revision)),(lp.delete,(s,item['id'],revision,True))):
  with pytest.raises(ValueError):fn(*args)
 assert lp.listing(s)['items']==[item]

@pytest.mark.parametrize('id',[None,True,'','../x','a'*31,'A'*32,'z'*32])
def test_invalid_record_ids(s,id):
 with pytest.raises(ValueError):lp.update(s,id,{'status':'planned','notes':'','completed_attested':False},1)
 with pytest.raises(ValueError):lp.delete(s,id,1,True)


def test_missing_and_cross_profile_ids_are_not_found(s):
 item=make(s);s.save_profile({'name':'Other','skills':[],'facts':[]},'other');assert lp.listing(s,'other')['items']==[]
 for profile in ('other','default'):
  missing=item['id'] if profile=='other' else 'a'*32
  with pytest.raises(ValueError,match='not found'):lp.update(s,missing,{'status':'paused','notes':'','completed_attested':False},1,profile)
  with pytest.raises(ValueError,match='not found'):lp.delete(s,missing,1,True,profile)
 assert lp.listing(s)['items']==[item]

@pytest.mark.parametrize('operation',['list','create','update','delete'])
def test_missing_profile_no_implicit_creation(s,operation):
 with pytest.raises(ValueError,match='profile'):
  if operation=='list':lp.listing(s,'missing')
  elif operation=='create':lp.create(s,'SQL','a'*64,'missing')
  elif operation=='update':lp.update(s,'a'*32,{'status':'planned','notes':'','completed_attested':False},1,'missing')
  else:lp.delete(s,'a'*32,1,True,'missing')

@pytest.mark.parametrize('confirmed',[False,None,'true',1,[]])
def test_deletion_requires_actual_confirmation(s,confirmed):
 item=make(s)
 with pytest.raises(ValueError):lp.delete(s,item['id'],1,confirmed)
 assert lp.listing(s)['items']==[item]


def test_stale_update_and_delete_preserve_newer_notes(s):
 item=make(s);new=change(s,item,'in_progress','NEW PRIVATE NOTE');before=snapshot(s)
 with pytest.raises(ValueError,match='changed'):change(s,item,'paused','OLD LOST NOTE')
 with pytest.raises(ValueError,match='changed'):lp.delete(s,item['id'],1,True)
 assert snapshot(s)==before and lp.listing(s)['items']==[new]


def test_concurrent_same_offer_idempotent(s):
 f=priority(s)['learning_options']['plan_fingerprint']
 with ThreadPoolExecutor(max_workers=4) as pool:items=list(pool.map(lambda _:lp.create(s,'SQL',f),range(8)))
 assert len({x['id'] for x in items})==1 and len(lp.listing(s)['items'])==1


def test_concurrent_same_revision_only_one_wins(s):
 item=make(s)
 def run(i):
  try:return change(s,item,'in_progress',str(i))
  except ValueError:return None
 with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(run,range(4)))
 assert sum(x is not None for x in results)==1 and lp.listing(s)['items'][0]['revision']==2


def test_namespace_preservation_all_write_orders_and_concurrency(s):
 config={**DEFAULTS,'enabled':True,'days':13};settings(s,value=config);search=save_search(s,{'name':'PRIVATE SEARCH','query':'Python','status':''});item=make(s)
 settings(s,value={'max_items':2});assert lp.listing(s)['items']==[item] and searches(s)==[search]
 config2=settings(s);change(s,item,'paused');assert settings(s)==config2 and searches(s)==[search]
 def task(i):
  if i%3==0:settings(s,value={'days':i})
  elif i%3==1:save_search(s,{'name':str(i),'query':'','status':''})
  else:make(s,'Docker')
 with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(task,range(12)))
 assert len(lp.listing(s)['items'])==2 and len(searches(s))==5 and settings(s)['days'] in (0,3,6,9)


def test_getting_guidance_or_progress_is_readonly_private_and_no_network(s):
 item=make(s);item=change(s,item,'completed','UNIQUE_PRIVATE_NOTES_<img src=x>',True);before=snapshot(s)
 with pytest.MonkeyPatch.context() as m:
  m.setattr(socket,'create_connection',lambda *a,**k:(_ for _ in ()).throw(AssertionError('Network forbidden')))
  r=s.learning();assert lp.listing(s)['items']==[item]
 assert snapshot(s)==before and item['notes'] not in json.dumps(r)
 with s.connect() as db:
  events=' '.join(r[0] for r in db.execute("SELECT details FROM audit WHERE event LIKE 'learning_%'"))
 assert 'PRIVATE' not in events and 'SQL' not in events and 'postgresql' not in events


def test_progress_changes_only_its_namespace_settings_timestamp_and_minimal_audit(s):
 before=snapshot(s);report=s.learning();item=make(s);change(s,item,'completed','PRIVATE',True);after=snapshot(s)
 for table in before:
  if table not in ('workflow_settings','audit'):assert before[table]==after[table],table
 assert s.learning()==report and s.profile()['facts']==[]


def test_limits_and_existing_item_at_cap(s,monkeypatch):
 item=make(s);monkeypatch.setattr(lp,'MAX_ITEMS',1);assert make(s)==item
 with pytest.raises(ValueError,match='At most'):make(s,'Docker')
 new=change(s,item,'paused');lp.delete(s,new['id'],new['revision'],True);assert make(s,'Docker')['status']=='planned'

@pytest.mark.parametrize('bad',[None,[],{}, {'version':2,'items':[]},{'version':True,'items':[]},{'version':1,'items':{}},{'version':1,'items':[None]}])
def test_corrupt_namespaces_never_reset_or_destroy_other_settings(s,bad):
 make(s);ns_edit(s,lambda d:d.update(learning_progress=bad));before=snapshot(s)
 for op in (lambda:lp.listing(s),lambda:make(s),lambda:lp.delete(s,'a'*32,1,True)):
  with pytest.raises(ValueError):op()
 assert snapshot(s)==before

@pytest.mark.parametrize('field,value',[
 ('id','bad'),('snapshot_hash','a'*64),('snapshot',{}),('status','bad'),('notes',None),('revision',True),
 ('created_at','bad'),('updated_at','2020-01-01T00:00:00'),('updated_at','2000-01-01T00:00:00+00:00'),
 ('completed_at','2026-10-29T00:00:00+00:00'),('notes','x'*2001),('revision',0),
])
def test_malformed_records_fail_closed(s,field,value):
 make(s);ns_edit(s,lambda d:d[lp.KEY]['items'][0].update({field:value}));before=snapshot(s)
 with pytest.raises(ValueError):lp.listing(s)
 assert snapshot(s)==before


def test_even_rehashed_snapshot_must_have_safe_url_and_shape(s):
 make(s)
 def alter(d):
  item=d[lp.KEY]['items'][0];item['snapshot']['resource_url']='javascript:alert(1)';item['snapshot_hash']=lp.digest(item['snapshot'])
 ns_edit(s,alter)
 with pytest.raises(ValueError,match='reading URL'):lp.listing(s)


def test_literal_unicode_notes_not_fetched_or_normalized(s):
 text='  وظيفة\nÜbung <img src=x onerror=BAD> file:///private/path https://example.org  '
 item=change(s,make(s),'in_progress',text);assert lp.listing(s)['items'][0]['notes']==text


def test_clock_rollback_does_not_corrupt_existing_record(s,monkeypatch):
 item=make(s);monkeypatch.setattr(lp,'now',lambda:'2000-01-01T00:00:00+00:00')
 new=change(s,item);assert new['updated_at']>=item['updated_at'] and lp.listing(s)['items']==[new]


def test_completed_state_not_a_progress_score_or_candidate_fact(s):
 before=(s.profile(),s.jobs(),s.summary());item=change(s,make(s),'completed','SELF REPORTED',True)
 assert (s.profile(),s.jobs(),s.summary())==before and 'self-record' in lp.listing(s)['notice']


def test_private_progress_not_in_digest_calendar_outcomes_or_jobs_export(s):
 from jobhunter_app.calendar_export import preview
 from jobhunter_app.outcomes import report
 from jobhunter_app.digests import preview as digest_preview
 item=change(s,make(s),'completed','UNIQUE_PRIVATE_PROGRESS_SECRET',True)
 outputs=[s.learning(),s.jobs(),report(s),preview(s),digest_preview(s)]
 assert all(item['notes'] not in json.dumps(o) for o in outputs)
 assert 'learning_progress' not in json.dumps(settings(s))


def test_http_csrf_snapshot_bound_create_update_delete(web):
 st,server=web;st.ingest([{**JOB,'description':'SQL required.'}]);st.evaluate();f=priority(st)['learning_options']['plan_fingerprint'];h={'X-JobHunter-Token':token(web)}
 assert request(web,'GET','/learning-progress.js')[0]==200
 assert request(web,'POST','/api/learning-save',{'skill':'SQL','preview_fingerprint':f})[0]==403
 code,_,raw=request(web,'POST','/api/learning-save',{'skill':'SQL','preview_fingerprint':f},h);assert code==200;item=json.loads(raw)
 body={'id':item['id'],'revision':1,'progress':{'status':'completed','notes':'PRIVATE_HTTP_<img src=x>','completed_attested':False}}
 assert request(web,'POST','/api/learning-update',body,h)[0]==400
 body['progress']['completed_attested']=True;code,_,raw=request(web,'POST','/api/learning-update',body,h);assert code==200;done=json.loads(raw)
 assert request(web,'POST','/api/learning-update',body,h)[0]==400
 before=snapshot(st);assert json.loads(request(web,'GET','/api/learning-progress')[2])['items']==[done] and snapshot(st)==before
 assert b'PRIVATE_HTTP' not in request(web,'GET','/api/learning')[2]
 assert request(web,'POST','/api/learning-delete',{'id':done['id'],'revision':done['revision']},h)[0]==400
 assert request(web,'POST','/api/learning-delete',{'id':done['id'],'revision':1,'confirmed':True},h)[0]==400
 assert request(web,'POST','/api/learning-delete',{'id':done['id'],'revision':done['revision'],'confirmed':True},h)[0]==200
 assert json.loads(request(web,'GET','/api/learning-progress')[2])['items']==[]
