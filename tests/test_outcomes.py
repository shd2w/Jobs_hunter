"""Independent synthetic aggregates, time boundaries, privacy and read-only exports."""
import csv,io,json,socket
from datetime import date,datetime,timezone
import pytest
from jobhunter_app.store import Store,STATES
from jobhunter_app.outcomes import report,export,window
from jobhunter_app.followups import save,complete
from tests.test_local_store import JOB,PROFILE
from tests.test_web_local import web,request

@pytest.fixture
def store(tmp_path):
 s=Store(tmp_path/'outcomes.sqlite3');s.save_profile(PROFILE);s.ingest([JOB,{**JOB,'url':'https://example.org/second','title':'Second private job'}]);s.evaluate();return s

def event(s,job,status,stamp,pid='default'):
 with s.connect() as db:db.execute('INSERT INTO status_history(profile_id,job_id,old_status,new_status,changed_at) VALUES(?,?,?,?,?)',(pid,job,None,status,stamp))

def seed(store):
 jobs=store.jobs();a,b=[j['id'] for j in jobs]
 store.set_status(a,'offer','PRIVATE NOTES','2026-11-02');store.set_status(b,'saved','PRIVATE NOTES','2026-11-03')
 with store.connect() as db:db.execute('DELETE FROM status_history')
 for job,state,t in [(a,'applied','2026-11-01T00:00:00Z'),(a,'interview','2026-11-01T12:00:00+00:00'),(a,'applied','2026-11-02T00:00:00+00:00'),(a,'offer','2026-11-03T00:00:00Z'),(b,'applied','2026-11-02T23:59:59.999999Z')]:event(store,job,state,t)
 return a,b

def test_empty_history_and_snapshot_separated(store):
 d=report(store,start='2026-11-01',end='2026-11-03');assert d['snapshot']['local_jobs']==2;assert d['snapshot']['untracked_jobs']==2
 assert d['activity']['events']==0 and len(d['activity']['daily'])==3
 assert all(x['events']==0 for x in d['activity']['daily']);assert d['coverage']['earliest_recorded_utc_day'] is None

def test_independent_totals_and_overlap(store):
 seed(store);d=report(store,start='2026-11-01',end='2026-11-02');a=d['activity'];c=d['coverage']
 assert a['events']==4 and a['distinct_jobs']==2
 by={x['status']:x for x in a['by_status']};assert by['applied']=={'status':'applied','events':3,'distinct_jobs':2};assert by['interview']['events']==1
 assert sum(x['distinct_jobs'] for x in a['by_status'])==3 # overlapping, not 2
 assert [(r['events'],r['distinct_jobs']) for r in a['daily']]==[(2,1),(2,2)]
 assert c['history_rows']==5 and c['outside_window_events']==1 and c['valid_known_status_rows']==5
 assert c['earliest_recorded_utc_day']=='2026-11-01' and c['latest_recorded_utc_day']=='2026-11-03'
 assert d['snapshot']['current_statuses']==[{'status':s,'jobs':1 if s in ('offer','saved') else 0} for s in STATES]
 assert d['snapshot']['explicitly_tracked_jobs']==2

def test_current_snapshot_not_reconstructed_by_window(store):
 seed(store);old=report(store,start='2000-01-01',end='2000-01-01');new=report(store,start='2026-11-01',end='2026-11-03')
 assert old['snapshot']==new['snapshot'];assert old['activity']['events']==0

def test_utc_offsets_and_end_inclusive(store):
 a=seed(store)[0]
 with store.connect() as db:db.execute('DELETE FROM status_history')
 for stamp in ['2026-10-31T23:30:00-01:00','2026-11-02T00:30:00+01:00','2026-11-01T23:59:59.999999+00:00','2026-11-02T00:00:00Z']:event(store,a,'applied',stamp)
 d=report(store,start='2026-11-01',end='2026-11-01');assert d['activity']['events']==3 and d['coverage']['outside_window_events']==1

@pytest.mark.parametrize('stamp',['bad','2026-11-01','2026-11-01T12:00:00','2026-13-01T00:00:00Z','0001-01-01T00:00:00+01:00','9999-12-31T23:59:59-01:00'])
def test_invalid_timestamps_diagnosed(store,stamp):
 a=seed(store)[0]
 with store.connect() as db:db.execute('DELETE FROM status_history')
 event(store,a,'applied',stamp);d=report(store,start='2026-11-01',end='2026-11-01');assert d['coverage']['invalid_timestamp_rows_omitted']==1 and d['activity']['events']==0

@pytest.mark.parametrize('start,end',[('2026-02-30','2026-03-01'),('2026-11-02','2026-11-01'),('2025-01-01','2026-01-02'),('2026-1-1','2026-01-02'),('','2026-01-01'),('2026-01-01',''),(123,'2026-01-01'),('2026-01-01',False)])
def test_invalid_windows(store,start,end):
 with pytest.raises(ValueError):report(store,start=start,end=end)

@pytest.mark.parametrize('start,end,days',[('2024-01-01','2024-12-31',366),('2026-01-01','2026-01-01',1),('0001-01-01','0001-01-02',2),('9999-12-31','9999-12-31',1),('2024-02-28','2024-03-01',3)])
def test_window_boundaries(store,start,end,days):
 d=report(store,start=start,end=end);assert len(d['activity']['daily'])==days and d['window']['inclusive_days']==days

def test_default_window_utc_30_days(store):
 d=report(store);assert d['window']['end']==datetime.now(timezone.utc).date().isoformat();assert d['window']['inclusive_days']==30
 assert report(store,end='2026-11-30')['window']['start']=='2026-11-01'
 with pytest.raises(ValueError):window(end='0001-01-01')

def test_profile_isolation(store):
 a,b=seed(store);store.save_profile(PROFILE,'other');store.set_status(a,'rejected',profile_id='other')
 event(store,a,'interview','2026-11-02T00:00:00Z','other')
 d=report(store,'other','2026-11-01','2026-11-03');assert d['snapshot']['explicitly_tracked_jobs']==1 and d['snapshot']['untracked_jobs']==1
 assert d['activity']['distinct_jobs']==1
 assert sum(x['events'] for x in d['activity']['by_status'] if x['status']=='applied')==0
 with pytest.raises(ValueError):report(store,'missing')

def test_due_items_are_calendar_date_current_completion_snapshots(store):
 a,b=seed(store);store.set_status(b,'saved',deadline='2026-11-02')
 save(store,a,'PRIVATE TITLE','2026-11-01','PRIVATE NOTES');task=save(store,b,'OTHER PRIVATE TITLE','2026-11-02');complete(store,task['id']);save(store,b,'OUTSIDE','2026-11-03')
 d=report(store,start='2026-11-01',end='2026-11-02');assert d['due_items']=={'active_deadlines':1,'unfinished_followups':1,'completed_followups':1}
 assert d['coverage']['outside_window_due_items']['followups']==1
 # Offer-status deadline is excluded. Completion date is not a window event.
 assert d['coverage']['outside_window_due_items']['active_deadlines']==0
 complete(store,task['id'],False);assert report(store,start='2026-11-01',end='2026-11-02')['due_items']['unfinished_followups']==2

def test_invalid_due_and_unknown_statuses_reconcile(store):
 a,b=seed(store);save(store,b,'PRIVATE','2026-11-02')
 with store.connect() as db:
  db.execute("UPDATE applications SET status='unknown' WHERE job_id=?",(a,));db.execute("UPDATE applications SET deadline='bad' WHERE job_id=?",(b,));db.execute("UPDATE followups SET due='bad'")
 event(store,b,'unknown','bad')
 d=report(store,start='2026-11-01',end='2026-11-02');assert d['snapshot']['unknown_status_jobs']==1
 assert sum(r['jobs'] for r in d['snapshot']['current_statuses'])+1==d['snapshot']['explicitly_tracked_jobs']
 assert d['coverage']['unknown_history_status_rows_omitted']==1;assert d['coverage']['invalid_due_dates_omitted']=={'active_deadlines':1,'followups':1}

def test_privacy_read_only_and_no_network(store,monkeypatch):
 seed(store)
 def denied(*args,**kwargs):raise AssertionError('No network')
 monkeypatch.setattr(socket,'create_connection',denied)
 with store.connect() as db:before={name:[tuple(r) for r in db.execute('SELECT * FROM '+name)] for name in ['jobs','profiles','matches','applications','status_history','audit','workflow_settings']}
 for format in ('json','csv'):
  raw=export(store,start='2026-11-01',end='2026-11-02',format=format).decode()
  for x in ['PRIVATE',PROFILE['name'],JOB['url'],JOB['title'],JOB['company'],PROFILE['facts'][0]['text']]:assert x not in raw
 with store.connect() as db:assert before=={name:[tuple(r) for r in db.execute('SELECT * FROM '+name)] for name in before}

def test_csv_json_reconcile(store):
 seed(store);j=json.loads(export(store,start='2026-11-01',end='2026-11-02'));rows=list(csv.DictReader(io.StringIO(export(store,start='2026-11-01',end='2026-11-02',format='csv').decode())))
 assert sum(int(x['value']) for x in rows if x['section']=='activity_status')==j['activity']['events']
 assert sum(int(x['value']) for x in rows if x['section']=='activity_day')==j['activity']['events']
 assert sum(int(x['value']) for x in rows if x['section']=='current_status')==j['snapshot']['explicitly_tracked_jobs']
 assert all(x['window_start']=='2026-11-01' and x['window_end']=='2026-11-02' for x in rows)
 assert all(not v.startswith(('=','+','-','@','\t')) for r in rows for v in r.values())
 with pytest.raises(ValueError):export(store,format='xlsx')

def test_http_readonly_exports_and_errors(web):
 assert request(web,'GET','/outcomes.js')[0]==200
 assert request(web,'GET','/api/outcome-report?start=2026-11-01&end=2026-11-02')[0]==200
 for format in ('json','csv'):
  code,headers,raw=request(web,'GET','/api/outcome-export?format='+format+'&start=2026-11-01&end=2026-11-02');assert code==200
  assert 'attachment' in headers['Content-Disposition'] and headers['Cache-Control']=='no-store'
 assert request(web,'GET','/api/outcome-report?start=bad')[0]==400
 assert request(web,'GET','/api/outcome-export?format=html')[0]==400
 assert request(web,'GET','/api/outcome-report',headers={'Host':'evil.example'})[0]==403

def test_explicit_discovered_and_untracked_are_different(store):
 job=store.jobs()[0];store.set_status(job['id'],'discovered')
 d=report(store);assert d['snapshot']['untracked_jobs']==1
 assert next(x['jobs'] for x in d['snapshot']['current_statuses'] if x['status']=='discovered')==1

def test_same_status_notes_edit_is_not_a_transition(store):
 job=store.jobs()[0];store.set_status(job['id'],'applied','before');store.set_status(job['id'],'applied','after')
 assert report(store)['activity']['events']==1

def test_event_populations_overlap_across_days_not_summed(store):
 a=seed(store)[0]
 with store.connect() as db:db.execute('DELETE FROM status_history')
 event(store,a,'applied','2026-11-01T01:00:00Z');event(store,a,'interview','2026-11-02T01:00:00Z')
 d=report(store,start='2026-11-01',end='2026-11-02');assert d['activity']['distinct_jobs']==1
 assert sum(x['distinct_jobs'] for x in d['activity']['daily'])==2

def test_report_does_not_select_private_columns(store,monkeypatch):
 from contextlib import contextmanager
 import sqlite3
 original=store.connect
 sensitive={'notes','title','company','description','url','data','body','name'}
 @contextmanager
 def protected():
  with original() as db:
   def authorize(action,arg1,arg2,*rest):
    return sqlite3.SQLITE_DENY if action==sqlite3.SQLITE_READ and arg2 in sensitive else sqlite3.SQLITE_OK
   db.set_authorizer(authorize);yield db
 monkeypatch.setattr(store,'connect',protected)
 assert report(store)['snapshot']['local_jobs']==2

def test_backup_preserves_aggregate_data(store,tmp_path):
 seed(store);path=tmp_path/'backup.sqlite3';store.backup(path)
 a=report(store,start='2026-11-01',end='2026-11-03');b=report(Store(path),start='2026-11-01',end='2026-11-03')
 a.pop('generated_at');b.pop('generated_at');assert a==b
