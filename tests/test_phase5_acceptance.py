"""Integrated synthetic lifecycle and recovery: real loopback HTTP, no external I/O."""
from datetime import date,timedelta
import hashlib,http.client,json,re,socket,subprocess,sys,time
from pathlib import Path
from threading import Event,Thread
from filelock import FileLock
import pytest
from jobhunter_app.store import Store,now,dump
from jobhunter_app.web import make_server
from jobhunter_app import network,digests
from jobhunter_app.source_health import health,reset
from jobhunter_app.sources import register,scan
from jobhunter_app.workflow import settings
from jobhunter_app.saved_searches import listing
from jobhunter_app.outcomes import report
from tests.test_local_store import PROFILE

@pytest.fixture
def isolated(tmp_path,monkeypatch):
 for k in list(__import__('os').environ):
  if k.startswith(('JOBHUNTER_','TELEGRAM_')):monkeypatch.delenv(k)
 monkeypatch.setenv('TELEGRAM_BOT_TOKEN','123:FAKE_ACCEPTANCE_TOKEN');monkeypatch.setenv('TELEGRAM_CHAT_ID','FAKE_ACCEPTANCE_DESTINATION')
 calls=[];deliveries=[]
 def fake_get(url,*a,**kw):
  assert url.startswith('https://jobicy.com/api/jobs?'),'Unexpected fixture URL';calls.append('jobicy-fixture')
  return json.dumps({'jobs':[{'id':91,'jobTitle':'Python Integrated Engineer','companyName':'Fixture Only','url':'https://example.org/integrated/source','jobDescription':'Python required','jobGeo':'Cairo'}],'hasMore':False,'nextCursor':None}).encode(),'application/json'
 monkeypatch.setattr(network,'get',fake_get)
 def fake_send(text):deliveries.append(text);return {'delivered':True,'status':'delivered'}
 monkeypatch.setattr(digests,'telegram_digest_send',fake_send)
 original=socket.create_connection
 def local(address,*a,**kw):
  assert address[0] in ('127.0.0.1','localhost','::1'),'External connections prohibited in acceptance tests'
  return original(address,*a,**kw)
 monkeypatch.setattr(socket,'create_connection',local)
 s=Store(tmp_path/'acceptance.sqlite3');s.save_profile(PROFILE)
 return s,calls,deliveries

class Client:
 def __init__(self,store):
  self.server=make_server(store,0);self.thread=Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.operations=[]
  self.token=re.search(rb'name="csrf-token" content="([^"]+)"',self.raw('GET','/')[2]).group(1).decode()
 def raw(self,method,path,data=None,expected=200):
  c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=10);headers={'Content-Type':'application/json'}
  if hasattr(self,'token'):headers['X-JobHunter-Token']=self.token
  c.request(method,path,json.dumps(data) if data is not None else None,headers);r=c.getresponse();raw=r.read();status=r.status;h=dict(r.getheaders());c.close();self.operations.append(method+' '+path.split('?')[0]);assert status==expected,(path,status,raw[:400]);return status,h,raw
 def get(self,path,expected=200):return json.loads(self.raw('GET',path,expected=expected)[2])
 def post(self,path,data,expected=200):return json.loads(self.raw('POST',path,data,expected)[2])
 def task(self):
  until=time.monotonic()+10
  while time.monotonic()<until:
   value=self.get('/api/task')
   if not value['running']:return value
   time.sleep(.02)
  raise AssertionError('Worker did not finish')
 def close(self):self.server.shutdown();self.server.server_close();self.thread.join(3)


def lifecycle(store,calls,deliveries):
 c=Client(store)
 try:
  source=c.post('/api/source',{'kind':'jobicy','identifier':'remote','approved':False})['source']
  c.post('/api/scan',{'source_id':source});assert 'approved' in c.task()['error'];assert not calls
  c.post('/api/source',{'kind':'jobicy','identifier':'remote','approved':True})
  c.post('/api/scan',{'source_id':source});task=c.task();assert task['error'] is None
  sourcehealth=c.get('/api/source-health')[0];assert sourcehealth['health']=='success' and sourcehealth['last_metrics']['inserted']==1
  c.post('/api/scan',{'source_id':source});assert 'cooldown' in c.task()['error'];assert len(calls)==1
  post={'origin_url':'https://example.org/post/integrated','source_label':'Acceptance post','body':'We are hiring!\nRole: Python Analyst\nCompany: Demo Employer\nLocation: Cairo\nApply: https://example.org/integrated/post\nPython required'}
  preview=c.post('/api/posts/preview',{'posts':[post]});assert c.get('/api/summary')['total_jobs']==1
  c.post('/api/posts/stage',{'posts':[post],'rights_attested':True});c.post('/api/posts/stage',{'posts':[post],'rights_attested':True})
  c.post('/api/match',{})
  summary=c.get('/api/summary');assert summary['total_jobs']==2 and summary['matched_jobs']==2
  jobs=c.get('/api/jobs');job=next(j for j in jobs if j['url'].endswith('/source'));other=next(j for j in jobs if j['url'].endswith('/post'))
  origins=c.get('/api/origins?id='+other['id']);assert 'Automatically' in json.dumps(origins) and 'human' in json.dumps(origins)
  search=c.post('/api/saved-search',{'search':{'name':'Integrated saved review','query':'Python','status':'reviewing'}})
  assert c.get('/api/saved-search-run?id='+search['id'])['jobs']==[]
  day=c.get('/api/inbox')['today'];c.post('/api/status',{'id':job['id'],'status':'reviewing','notes':'PRIVATE APPLICATION NOTES','deadline':day})
  task=c.post('/api/followup',{'job_id':job['id'],'title':'PRIVATE TASK TITLE','due':day,'notes':'PRIVATE TASK NOTES'})
  assert len(c.get('/api/saved-search-run?id='+search['id'])['jobs'])==1
  assert c.get('/api/inbox')['total']==2
  calendar=c.get('/api/calendar-preview?start='+day+'&days=0');assert calendar['events_in_window']==2
  _,headers,ics=c.raw('GET','/api/calendar-export?start='+day+'&days=0&fingerprint='+calendar['fingerprint']);assert b'BEGIN:VEVENT' in ics and ics.count(b'BEGIN:VEVENT')==2
  assert headers['Content-Type'].startswith('text/calendar')
  c.post('/api/status',{'id':job['id'],'status':'applied','notes':'PRIVATE APPLICATION NOTES','deadline':day})
  assert c.get('/api/saved-search-run?id='+search['id'])['jobs']==[];assert c.get('/api/inbox')['total']==1
  c.raw('GET','/api/calendar-export?start='+day+'&days=0&fingerprint='+calendar['fingerprint'],expected=400)
  outcomes=c.get('/api/outcome-report');assert outcomes['snapshot']['explicitly_tracked_jobs']==1 and outcomes['snapshot']['untracked_jobs']==1
  assert outcomes['activity']['events']==2 and outcomes['activity']['distinct_jobs']==1
  _,_,aggregate=c.raw('GET','/api/outcome-export?format=json');assert json.loads(aggregate)['activity']['events']==2
  _,_,csv=c.raw('GET','/api/outcome-export?format=csv');assert b'activity,all_events,2,1' in csv
  disabled=c.get('/api/digest-preview');assert disabled['enabled'] is False
  c.post('/api/digest-send',{'fingerprint':disabled['fingerprint'],'confirmed':True},expected=400);assert not deliveries
  c.post('/api/workflow-settings',{'settings':{'enabled':True}});assert c.get('/api/saved-searches')==[search]
  digest=c.get('/api/digest-preview');assert digest['include_job_details'] is False
  c.post('/api/digest-send',{'fingerprint':digest['fingerprint'],'confirmed':False},expected=400)
  assert c.post('/api/digest-send',{'fingerprint':digest['fingerprint'],'confirmed':True})['status']=='delivered'
  assert c.post('/api/digest-send',{'fingerprint':digest['fingerprint'],'confirmed':True})['status']=='already_delivered'
  assert len(deliveries)==1
  for raw in [ics,aggregate,csv,deliveries[0].encode()]:
   for secret in ['PRIVATE',PROFILE['name'],PROFILE['facts'][0]['text'],'Fixture Only','Demo Employer','example.org']:assert secret.encode() not in raw
  before=c.get('/api/source-health')[0];c.post('/api/source-reset',{'source_id':source});after=c.get('/api/source-health')[0]
  for key in ['approved','last_run','next_allowed_at','health']:assert before[key]==after[key]
  # Ordinary job exports intentionally contain notes; aggregate/privacy contracts differ.
  data=json.loads(c.raw('GET','/api/export?format=json')[2]);assert len(data)==2
  backup=Path(c.post('/api/backup',{})['backup']);restored=Store(backup)
  assert restored.jobs()==store.jobs() and listing(restored)==listing(store) and settings(restored)==settings(store)
  assert restored.profile()==store.profile()
  for table in ('profiles','applications','status_history','followups','job_origins','discovery_items','sources','source_checkpoints','provider_gates'):
   with store.connect() as left,restored.connect() as right:
    assert sorted(map(tuple,left.execute('SELECT * FROM '+table)))==sorted(map(tuple,right.execute('SELECT * FROM '+table)))
  a=report(store);b=report(restored);a.pop('generated_at');b.pop('generated_at');assert a==b
  with restored.connect() as db:assert db.execute('SELECT COUNT(*) FROM digest_deliveries').fetchone()[0]==1
  c.post('/api/followup-complete',{'id':task['id'],'completed':True});assert c.get('/api/inbox')['total']==0
  # Backup is isolated: later completion in the working fixture does not alter it.
  with restored.connect() as db:assert db.execute('SELECT completed FROM followups').fetchone()[0]==0
  return {'status':'passed','http_operations':len(c.operations),'source_fixture_retrievals':len(calls),'fake_digest_deliveries':len(deliveries),'real_external_requests':0,'final_local_jobs':2,'final_explicitly_tracked_jobs':1,'backup_reopened_and_compared':True,'private_outputs_checked':['calendar','aggregate_json','aggregate_csv','counts_only_digest']}
 finally:c.close()

def test_integrated_http_lifecycle(isolated):assert lifecycle(*isolated)['status']=='passed'

def test_checkpoint_reset_preserves_provider_gate_and_records(isolated):
 s,_,_=isolated;identity=register(s,'jobicy','remote',True);future=(__import__('datetime').datetime.now(__import__('datetime').timezone.utc)+timedelta(hours=2)).isoformat()
 with s.connect() as db:
  db.execute('INSERT INTO provider_gates VALUES(?,?)',('jobicy',future));db.execute('INSERT INTO source_checkpoints VALUES(?,?,?)',(identity,dump({'cursor':1}),now()))
 reset(s,identity)
 with s.connect() as db:
  assert db.execute('SELECT not_before FROM provider_gates').fetchone()[0]==future
  assert db.execute('SELECT approved FROM sources').fetchone()[0]==1;assert db.execute('SELECT COUNT(*) FROM source_checkpoints').fetchone()[0]==0
 with pytest.raises(ValueError,match='Retry-After'):scan(s,identity)

def test_cancelled_live_http_scan_imports_nothing(isolated,monkeypatch):
 s,calls,deliveries=isolated;entered=Event();release=Event();original=network.get
 def held(*a,**kw):entered.set();assert release.wait(5);return original(*a,**kw)
 monkeypatch.setattr(network,'get',held);c=Client(s)
 try:
  source=c.post('/api/source',{'kind':'jobicy','identifier':'remote','approved':True})['source'];c.post('/api/scan',{'source_id':source});assert entered.wait(3)
  c.post('/api/stop',{});release.set();task=c.task();assert task['result']['cancelled'] is True
  assert c.get('/api/summary')['total_jobs']==0 and c.get('/api/source-health')[0]['health']=='cancelled'
 finally:release.set();c.close()

def test_restart_respects_live_lock_then_recovers_interruption(isolated):
 s,_,_=isolated;identity=register(s,'jobicy','remote',True)
 with s.connect() as db:
  db.execute('UPDATE sources SET health=?,last_run=? WHERE id=?',('running',now(),identity));db.execute('INSERT INTO runs(source,started_at,status) VALUES(?,?,?)',(identity,now(),'running'))
 with FileLock(str(s.path)+'.scan.lock',timeout=0):
  other=Store(s.path)
  with other.connect() as db:assert db.execute('SELECT status FROM runs').fetchone()[0]=='running'
 recovered=Store(s.path)
 with recovered.connect() as db:assert db.execute('SELECT status FROM runs').fetchone()[0]=='interrupted'
 assert health(recovered)[0]['health']=='interrupted'
 assert recovered.profile()==s.profile()

def test_corrupt_database_cli_does_not_reset_bytes(tmp_path):
 p=tmp_path/'damaged.sqlite3';p.write_bytes(b'NOT A SQLITE DATABASE; ORIGINAL PRESERVE\n');before=hashlib.sha256(p.read_bytes()).hexdigest()
 root=Path(__file__).resolve().parents[1];result=subprocess.run([sys.executable,'run_local.py','--db',str(p),'summary'],cwd=root,capture_output=True,text=True)
 assert result.returncode==2 and 'no automatic reset' in result.stderr
 assert hashlib.sha256(p.read_bytes()).hexdigest()==before
