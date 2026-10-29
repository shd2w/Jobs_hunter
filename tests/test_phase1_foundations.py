"""Phase 1 reliability acceptance; inert fixtures, no live sources/user records."""
import json
from threading import Event
from urllib.error import HTTPError
import pytest
from filelock import FileLock
from jobhunter_app.store import Store, now
from jobhunter_app.sources import register, scan
from tests.test_local_store import JOB,PROFILE

@pytest.fixture
def store(tmp_path):
 s=Store(tmp_path/'test.sqlite3');s.save_profile(PROFILE);return s

PAYLOADS={
 'greenhouse':({'jobs':[{'title':'Engineer','absolute_url':'https://example.org/1','content':'Python'},{'title':'Bad','absolute_url':'https://example.org/2','content':{'malformed':'not text'}}]},1),
 'lever':([{'text':'Engineer','hostedUrl':'https://example.org/1','descriptionPlain':'Python'},{'text':'Bad','hostedUrl':'https://example.org/2','descriptionPlain':123,'lists':[{'content':'SQL'}]}],1),
 'ashby':({'jobs':[{'title':'Engineer','jobUrl':'https://example.org/1','descriptionPlain':'Python','isListed':True},{'title':'Bad','jobUrl':'https://example.org/2','descriptionHtml':{'bad':'not text'},'isListed':True}]},1),
 'smartrecruiters':({'content':[{'name':'Engineer','applyUrl':'https://example.org/1','company':{'name':'Example'},'jobAd':{'sections':{}}},{'name':'Bad','applyUrl':'https://example.org/2','jobAd':['not an object']}],'totalFound':2},1),
 'remotive':({'jobs':[{'title':'Engineer','url':'https://remotive.com/remote-jobs/example-1','company_name':'Example','description':'Python'},{'title':'Bad','url':'https://remotive.com/remote-jobs/example-2','company_name':'Example','description':{'bad':'not text'}}]},1),
}

@pytest.mark.parametrize('kind',list(PAYLOADS))
def test_one_malformed_nested_record_does_not_lose_valid_jobs(store,kind):
 payload,expected=PAYLOADS[kind];sid=register(store,kind,'remote' if kind=='remotive' else 'example',True)
 result=scan(store,sid,lambda _:payload)
 assert result['inserted']==expected and result['invalid']==1
 assert len(store.jobs())==1 and store.summary()['sources'][0]['health']=='partial'
 assert store.summary()['recent_runs'][0]['status']=='partial'
 assert 'malformed' not in store.summary()['recent_runs'][0]['metrics']

@pytest.mark.parametrize('kind',['greenhouse','ashby','remotive','smartrecruiters','lever'])
def test_broken_top_level_payload_is_failed_not_success(store,kind):
 sid=register(store,kind,'remote' if kind=='remotive' else 'example',True)
 with pytest.raises(ValueError):scan(store,sid,lambda _:{'unexpected':'private body'})
 assert not store.jobs() and store.summary()['recent_runs'][0]['status']=='failed'
 assert 'private body' not in store.summary()['recent_runs'][0]['metrics']

def test_source_ingest_and_completion_are_atomic(store,monkeypatch):
 sid=register(store,'greenhouse','example',True)
 original=store.audit
 def fail(db,event,details):
  if event=='ingest':raise RuntimeError('simulated storage failure; private note')
  original(db,event,details)
 monkeypatch.setattr(store,'audit',fail)
 with pytest.raises(ValueError):scan(store,sid,lambda _:PAYLOADS['greenhouse'][0])
 assert not store.jobs() and store.summary()['recent_runs'][0]['status']=='failed'
 assert 'private note' not in store.summary()['recent_runs'][0]['metrics']

@pytest.mark.parametrize('kind',['greenhouse','lever','ashby','smartrecruiters','feed'])
def test_quota_pauses_same_adapter_not_independent_provider(store,kind):
 ident=lambda x:'https://example.org/'+x+'.rss' if kind=='feed' else x
 a=register(store,kind,ident('first'),True);register(store,kind,ident('second'),True)
 other=register(store,'remotive','remote',True)
 def quota(_):raise HTTPError('https://example.org',429,'private response',{},None)
 with pytest.raises(ValueError):scan(store,a,quota)
 summary=store.summary()
 assert all(not s['approved'] and s['health']=='rate_limited' for s in summary['sources'] if s['kind']==kind)
 assert next(s for s in summary['sources'] if s['id']==other)['approved']==1
 with store.connect() as db:assert db.execute("SELECT COUNT(*) FROM audit WHERE event='provider_quota_pause'").fetchone()[0]==1

def make_running(store,source):
 with store.connect() as db:
  return db.execute('INSERT INTO runs(source,started_at,status) VALUES(?,?,?)',(source,now(),'running')).lastrowid

def test_abandoned_run_recovered_once_and_records_kept(store):
 sid=register(store,'greenhouse','example',True);store.ingest([JOB]);id=store.jobs()[0]['id'];store.set_status(id,'saved','Keep my notes')
 with store.connect() as db:db.execute('UPDATE sources SET last_run=? WHERE id=?',('2026-10-29T12:00:00+00:00',sid))
 run=make_running(store,sid)
 restored=Store(store.path);s=restored.summary()
 assert s['recent_runs'][0]['status']=='interrupted' and s['sources'][0]['health']=='interrupted'
 assert s['sources'][0]['approved']==1 and s['sources'][0]['last_run']=='2026-10-29T12:00:00+00:00'
 assert restored.jobs()[0]['notes']=='Keep my notes'
 assert s['recent_runs'][0]['finished_at'] and json.loads(s['recent_runs'][0]['metrics'])['recovered_at_startup']
 assert Store(store.path).recover_interrupted_runs()==0
 with restored.connect() as db:
  assert db.execute("SELECT COUNT(*) FROM audit WHERE event='interrupted_runs_recovered'").fetchone()[0]==1
  assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'

def test_live_scan_lock_prevents_false_interruption(store):
 sid=register(store,'greenhouse','example',True);make_running(store,sid)
 with FileLock(str(store.path)+'.scan.lock'):
  other=Store(store.path)
  assert other.summary()['recent_runs'][0]['status']=='running'
 assert Store(store.path).summary()['recent_runs'][0]['status']=='interrupted'

def test_stale_run_does_not_overwrite_newer_source_success(store):
 sid=register(store,'greenhouse','example',True);old=make_running(store,sid)
 with store.connect() as db:
  db.execute('INSERT INTO runs(source,started_at,finished_at,status) VALUES(?,?,?,?)',(sid,now(),now(),'success'))
  db.execute("UPDATE sources SET health='success' WHERE id=?",(sid,))
 restored=Store(store.path)
 assert restored.summary()['sources'][0]['health']=='success'
 with restored.connect() as db:assert db.execute('SELECT status FROM runs WHERE id=?',(old,)).fetchone()[0]=='interrupted'

def test_cancelled_run_never_reclassified_as_interrupted(store):
 sid=register(store,'greenhouse','example',True);event=Event();event.set()
 assert scan(store,sid,lambda _:PAYLOADS['greenhouse'][0],event)['cancelled']
 assert Store(store.path).summary()['recent_runs'][0]['status']=='cancelled'

def test_completion_storage_failure_rolls_back_ingested_jobs(store):
 sid=register(store,'greenhouse','example',True)
 with store.connect() as db:
  db.executescript("CREATE TRIGGER fail_health BEFORE UPDATE ON sources WHEN NEW.health='success' BEGIN SELECT RAISE(ABORT,'simulated completion write failure'); END;")
 with pytest.raises(ValueError):scan(store,sid,lambda _:{'jobs':[PAYLOADS['greenhouse'][0]['jobs'][0]]})
 assert not store.jobs() and store.summary()['recent_runs'][0]['status']=='failed'


def test_corrupt_database_cli_is_non_destructive_and_sanitized(tmp_path):
 import subprocess,sys
 from pathlib import Path
 path=tmp_path/'broken.sqlite3';original=b'not a database\nprivate-test-marker';path.write_bytes(original)
 root=Path(__file__).resolve().parents[1]
 result=subprocess.run([sys.executable,'run_local.py','--db',str(path),'summary'],cwd=root,capture_output=True,text=True,timeout=20)
 assert result.returncode==2 and path.read_bytes()==original
 assert 'no automatic reset' in result.stderr and 'Traceback' not in result.stderr and 'private-test-marker' not in result.stderr
