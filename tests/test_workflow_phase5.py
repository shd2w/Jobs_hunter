"""Synthetic manual workflow tests. No genuine submissions or Telegram calls."""
import json
from datetime import date,timedelta,datetime,timezone
import sqlite3
from concurrent.futures import ThreadPoolExecutor
import pytest
from filelock import FileLock,Timeout
from jobhunter_app.store import Store,SCHEMA,DISCOVERY_SCHEMA,HISTORY_SCHEMA,SOURCE_SCHEMA
from jobhunter_app.followups import save,complete,digest,calendar_day
from jobhunter_app.workflow import settings,report,DEFAULTS
from jobhunter_app.digests import preview,send,destination,retry_seconds
from tests.test_local_store import JOB,PROFILE
from tests.test_web_local import web,request,token

DAY='2026-11-01'
@pytest.fixture
def store(tmp_path):
 s=Store(tmp_path/'test.db');s.save_profile(PROFILE);s.ingest([JOB]);s.evaluate();return s
@pytest.fixture(autouse=True)
def fake_environment(monkeypatch):
 monkeypatch.setenv('TELEGRAM_CHAT_ID','123456');monkeypatch.setenv('TELEGRAM_BOT_TOKEN','123:FAKE_TOKEN')

@pytest.mark.parametrize('version',[1,2,3,4])
def test_upgrade_snapshot_preserves_all_previous_tables(tmp_path,version):
 p=tmp_path/'old.db'
 with sqlite3.connect(p) as db:
  db.executescript(SCHEMA+(DISCOVERY_SCHEMA if version>=2 else '')+(HISTORY_SCHEMA if version>=3 else '')+(SOURCE_SCHEMA if version>=4 else '')+f'PRAGMA user_version={version};')
  db.execute('INSERT INTO profiles VALUES(?,?,?)',('default',json.dumps(PROFILE),'before'))
 s=Store(p);assert s.profile()==PROFILE
 with s.connect() as db:
  assert db.execute('PRAGMA user_version').fetchone()[0]==5
  assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
  assert not db.execute('PRAGMA foreign_key_check').fetchall()
  assert db.execute('SELECT COUNT(*) FROM followups').fetchone()[0]==0
 backup=list(tmp_path.glob('*.pre-v5-*.bak'));assert len(backup)==1
 with sqlite3.connect(backup[0]) as db:
  assert db.execute('PRAGMA user_version').fetchone()[0]==version
  assert db.execute('SELECT data FROM profiles').fetchone()[0]==json.dumps(PROFILE)
 Store(p);assert len(list(tmp_path.glob('*.bak')))==1


def test_upgrade_failure_rolls_back_and_preserves_backup(tmp_path,monkeypatch):
 import jobhunter_app.store as module
 p=tmp_path/'old.db'
 with sqlite3.connect(p) as db:db.executescript(SCHEMA+DISCOVERY_SCHEMA+HISTORY_SCHEMA+SOURCE_SCHEMA+'PRAGMA user_version=4;')
 monkeypatch.setattr(module,'WORKFLOW_SCHEMA',module.WORKFLOW_SCHEMA+'INVALID SQL;')
 with pytest.raises(sqlite3.DatabaseError):Store(p)
 with sqlite3.connect(p) as db:
  assert db.execute('PRAGMA user_version').fetchone()[0]==4
  assert not db.execute("SELECT 1 FROM sqlite_master WHERE name='followups'").fetchone()
 assert len(list(tmp_path.glob('*.bak')))==1


@pytest.mark.parametrize('day',['20261101','2026-1-01','2026-02-30','2026-11-01T12:00:00','2026-W44-1','',None,True,1])
def test_strict_calendar_days(day):
 with pytest.raises(ValueError):calendar_day(day)

@pytest.mark.parametrize('value',[False,None,0,'20261101','2026-02-30'])
def test_application_deadline_strict(store,value):
 with pytest.raises(ValueError):store.set_status(store.jobs()[0]['id'],'reviewing',deadline=value)
 assert store.jobs()[0]['status']=='discovered'


def test_followup_saved_private_no_status_change(store):
 job=store.jobs()[0];before=job['match'];r=save(store,job['id'],'Private task',DAY,'PRIVATE NOTES')
 row=digest(store,today=DAY)['items'][0]
 assert row['notes']=='PRIVATE NOTES' and row['timing']=='today' and row['id']==r['id']
 assert store.jobs()[0]['status']=='discovered' and store.jobs()[0]['match']==before
 complete(store,r['id']);assert digest(store,today=DAY)['total']==0
 assert digest(store,today=DAY,include_completed=True)['counts']['completed']==1
 complete(store,r['id'],False);assert digest(store,today=DAY)['total']==1
 save(store,job['id'],'Rescheduled','2026-11-02','new',followup_id=r['id'])
 assert digest(store,today=DAY)['items'][0]['timing']=='upcoming'


@pytest.mark.parametrize('kwargs',[{'title':''},{'title':None},{'title':'x'*301},{'notes':'x'*2001},{'notes':False},{'due':'20260101'},{'job_id':'missing'},{'profile_id':'missing'},{'followup_id':False},{'followup_id':'missing'}])
def test_invalid_followup_atomic(store,kwargs):
 args={'job_id':store.jobs()[0]['id'],'title':'Task','due':DAY};args.update(kwargs)
 with pytest.raises(ValueError):save(store,**args)
 with store.connect() as db:assert db.execute('SELECT COUNT(*) FROM followups').fetchone()[0]==0


def test_profiles_cannot_edit_others_followups(store):
 s=store;s.save_profile(PROFILE,'other');r=save(s,s.jobs()[0]['id'],'Private',DAY)
 assert digest(s,'other',DAY)['total']==0
 with pytest.raises(ValueError):complete(s,r['id'],profile_id='other')
 with pytest.raises(ValueError):save(s,s.jobs()[0]['id'],'Other',DAY,profile_id='other',followup_id=r['id'])
 with pytest.raises(ValueError):complete(s,r['id'],completed=1)


def test_deadline_counts_dates_and_closed_status(store):
 job=store.jobs()[0];store.set_status(job['id'],'reviewing',deadline='2026-10-31')
 save(store,job['id'],'Today',DAY);save(store,job['id'],'Upcoming','2026-11-03');save(store,job['id'],'Later','2026-12-01')
 d=digest(store,today=DAY,days=7,limit=1)
 assert d['counts']=={'overdue':1,'today':1,'upcoming':1,'completed':0}
 assert d['total']==3 and d['has_more'] and len(d['items'])==1
 assert digest(store,today=DAY,offset=2)['items'][0]['title']=='Upcoming'
 store.set_status(job['id'],'applied',deadline='2026-10-31')
 assert digest(store,today=DAY)['total']==2 # Personal follow-ups remain explicit tasks.


def test_invalid_legacy_date_visible_not_crash(store):
 store.set_status(store.jobs()[0]['id'],'reviewing')
 with store.connect() as db:db.execute("UPDATE applications SET deadline='20261101'")
 assert digest(store,today=DAY)['invalid_dates']==1

@pytest.mark.parametrize('kw',[{'days':True},{'days':-1},{'days':3651},{'limit':0},{'offset':-1},{'include_completed':1},{'today':'9999-12-31','days':1}])
def test_inbox_bounds(store,kw):
 args={'today':DAY};args.update(kw)
 with pytest.raises(ValueError):digest(store,**args)


def test_settings_defaults_persist_scope_no_matching_invalidation(store):
 assert settings(store)==DEFAULTS and not settings(store)['enabled']
 before=store.jobs()[0]['match'];config=settings(store,value={'enabled':True,'days':10})
 assert settings(Store(store.path))==config and store.jobs()[0]['match']==before
 store.save_profile(PROFILE,'other');assert settings(store,'other')==DEFAULTS
 store.save_profile(PROFILE);assert settings(store)==config

@pytest.mark.parametrize('v',[[],None,{'token':'secret'},{'enabled':1},{'include_job_details':'yes'},{'days':False},{'days':366},{'max_items':0},{'max_items':11},{'threshold':float('nan')},{'threshold':float('inf')},{'threshold':True},{'threshold':10**500}])
def test_settings_bad_values(store,v):
 from jobhunter_app.workflow import validate
 with pytest.raises(ValueError):validate(v)
 assert settings(store)==DEFAULTS


def test_report_counts_explicit_states_not_conversion(store):
 job=store.jobs()[0];r=report(store,today=DAY)
 assert r['local_jobs']==1 and r['explicitly_tracked_jobs']==0 and r['ever_marked_applied']==0
 store.set_status(job['id'],'applied');store.set_status(job['id'],'interview');store.set_status(job['id'],'applied');store.set_status(job['id'],'offer')
 r=report(store,today=DAY)
 assert r['ever_marked_applied']==r['ever_marked_interview']==r['ever_marked_offer']==1
 assert r['currently_applied']==0 and r['explicitly_tracked_jobs']==1
 store.save_profile(PROFILE,'other');assert report(store,'other',DAY)['ever_marked_applied']==0


def test_preview_counts_only_and_no_network(store,monkeypatch):
 monkeypatch.setattr('urllib.request.build_opener',lambda *a:pytest.fail('Preview must not access Telegram'))
 save(store,store.jobs()[0]['id'],'PRIVATE TASK',DAY,'PRIVATE NOTES')
 p=preview(store,today=DAY)
 assert not p['enabled'] and p['details_shown']==0
 for secret in [PROFILE['name'],PROFILE['facts'][0]['text'],'PRIVATE TASK','PRIVATE NOTES',JOB['url'],JOB['company']]:assert secret not in p['message']
 assert p==preview(store,today=DAY)
 with store.connect() as db:assert db.execute('SELECT COUNT(*) FROM digest_deliveries').fetchone()[0]==0


def enable(store,details=False):return settings(store,value={'enabled':True,'include_job_details':details})


def test_send_confirm_dedup_and_separate_date(store):
 enable(store);p=preview(store,today=DAY);calls=[]
 def sender(t):calls.append(t);return {'delivered':True}
 assert send(store,p['fingerprint'],True,today=DAY,sender=sender)['sent']==1
 assert send(store,p['fingerprint'],True,today=DAY,sender=sender)['status']=='already_delivered'
 assert len(calls)==1
 p=preview(store,today='2026-11-02');assert send(store,p['fingerprint'],True,today='2026-11-02',sender=sender)['sent']==1

@pytest.mark.parametrize('confirmed',[False,None,1,'yes'])
def test_confirmation_required(store,confirmed):
 enable(store);p=preview(store,today=DAY)
 with pytest.raises(ValueError):send(store,p['fingerprint'],confirmed,today=DAY,sender=lambda _:pytest.fail('No send'))


def test_disabled_or_stale_preview_blocks_send(store,monkeypatch):
 p=preview(store,today=DAY)
 with pytest.raises(ValueError,match='Enable'):send(store,p['fingerprint'],True,today=DAY,sender=lambda _:pytest.fail('No send'))
 enable(store)
 with pytest.raises(ValueError,match='changed'):send(store,p['fingerprint'],True,today=DAY,sender=lambda _:pytest.fail('No send'))
 p=preview(store,today=DAY);monkeypatch.setenv('TELEGRAM_CHAT_ID','different-chat')
 with pytest.raises(ValueError,match='changed'):send(store,p['fingerprint'],True,today=DAY,sender=lambda _:pytest.fail('No send'))


def test_details_opt_in_and_message_bounds(store):
 enable(store,True);p=preview(store,today=DAY);assert JOB['title'] in p['message'] and JOB['url'] in p['message']
 for n in range(12):store.ingest([{**JOB,'url':f'https://example.org/{n}/'+'a'*3500}])
 store.evaluate();p=preview(store,today=DAY)
 assert len(p['message'])<=3500 and p['details_shown']<=5


def test_excluded_and_closed_jobs_not_prioritized(store):
 store.save_profile({**PROFILE,'excluded_title_terms':[JOB['title']]});store.evaluate();enable(store,True)
 assert preview(store,today=DAY)['counts']['matching_active_jobs']==0
 store.save_profile(PROFILE);store.evaluate();store.set_status(store.jobs()[0]['id'],'applied')
 assert preview(store,today=DAY)['counts']['matching_active_jobs']==0


@pytest.mark.parametrize('result',[{'delivered':False,'status':'authorization_failed'},{'delivered':False,'status':'provider_error'},{'delivered':False,'status':'delivery_unconfirmed'},False,{'delivered':'yes'}])
def test_failure_not_recorded_success_and_manual_retry(store,result):
 enable(store);p=preview(store,today=DAY)
 assert send(store,p['fingerprint'],True,today=DAY,sender=lambda _:result)['sent']==0
 assert send(store,p['fingerprint'],True,today=DAY,sender=lambda _:{'delivered':True})['sent']==1


def test_sender_exception_sanitized(store):
 enable(store);p=preview(store,today=DAY)
 def bad(_):raise ValueError('SECRET TOKEN')
 result=send(store,p['fingerprint'],True,today=DAY,sender=bad)
 assert result['status']=='delivery_unconfirmed' and 'SECRET' not in json.dumps(result)
 with store.connect() as db:assert 'SECRET' not in str([tuple(x) for x in db.execute('SELECT * FROM audit')])


def test_rate_gate_persists_and_legacy_notify_respects(store):
 from jobhunter_app.notifications import notify
 enable(store);p=preview(store,today=DAY)
 assert send(store,p['fingerprint'],True,today=DAY,sender=lambda _:{'delivered':False,'status':'rate_limited','retry_after':300})['status']=='rate_limited'
 store=Store(store.path)
 assert send(store,p['fingerprint'],True,today=DAY,sender=lambda _:pytest.fail('Gate bypass'))['status']=='retry_later'
 assert notify(store,sender=lambda _:pytest.fail('Legacy bypass'))['status']=='retry_later'
 store.save_profile(PROFILE,'other');enable_other=settings(store,'other',{'enabled':True});p=preview(store,'other',DAY)
 assert send(store,p['fingerprint'],True,'other',DAY,sender=lambda _:pytest.fail('Profile bypass'))['status']=='retry_later'


def test_expired_gate_and_lock(store):
 enable(store);p=preview(store,today=DAY)
 with store.connect() as db:db.execute('INSERT INTO notification_gates VALUES(?,?)',(destination(),'2000-01-01T00:00:00+00:00'))
 with FileLock(str(store.path)+'.notify.lock'):
  with pytest.raises(Timeout):send(store,p['fingerprint'],True,today=DAY,sender=lambda _:pytest.fail('Concurrent send'))
 assert send(store,p['fingerprint'],True,today=DAY,sender=lambda _:{'delivered':True})['sent']==1

@pytest.mark.parametrize('value,minimum',[(None,60),('abc',60),('120',120),(300,300),(True,60),(float('nan'),60),(10**500,604801),('Wed, 01 Jan 2031 00:00:00 GMT',604801)])
def test_retry_parser(value,minimum):assert retry_seconds(value)>=minimum


def test_routes_and_csrf(web):
 s,_=web;s.ingest([JOB]);job=s.jobs()[0];headers={'X-JobHunter-Token':token(web)}
 for path in ['/api/inbox','/api/workflow-report','/api/workflow-settings','/api/digest-preview','/workflow.js']:assert request(web,'GET',path)[0]==200
 assert request(web,'POST','/api/followup',{'job_id':job['id'],'title':'Task','due':DAY})[0]==403
 r=request(web,'POST','/api/followup',{'job_id':job['id'],'title':'Task','due':DAY},headers);assert r[0]==200
 id=json.loads(r[2])['id'];assert request(web,'POST','/api/followup-complete',{'id':id,'completed':True},headers)[0]==200
 assert request(web,'POST','/api/workflow-settings',{'settings':{'enabled':True}},headers)[0]==200
 assert request(web,'POST','/api/digest-send',{'fingerprint':'bad','confirmed':False},headers)[0]==400
 assert request(web,'GET','/api/inbox?days=-1')[0]==400


def test_same_bot_other_destination_cannot_bypass_gate(store,monkeypatch):
 enable(store);p=preview(store,today=DAY)
 send(store,p['fingerprint'],True,today=DAY,sender=lambda _:{'delivered':False,'status':'rate_limited','retry_after':3600})
 monkeypatch.setenv('TELEGRAM_CHAT_ID','other-destination');p=preview(store,today=DAY)
 assert send(store,p['fingerprint'],True,today=DAY,sender=lambda _:pytest.fail('Same bot bypass'))['status']=='retry_later'


def test_send_commit_failure_does_not_fabricate_success(store):
 enable(store);p=preview(store,today=DAY)
 with store.connect() as db:db.execute("CREATE TRIGGER reject_delivery BEFORE INSERT ON digest_deliveries BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
 calls=[]
 with pytest.raises(sqlite3.DatabaseError):send(store,p['fingerprint'],True,today=DAY,sender=lambda t:calls.append(t) or {'delivered':True})
 assert len(calls)==1
 with store.connect() as db:assert db.execute('SELECT COUNT(*) FROM digest_deliveries').fetchone()[0]==0
 assert store.jobs()[0]['status']=='discovered'


def test_nontext_custom_title_not_sent_and_raw_markup_is_plain_text(store):
 enable(store,True);store.ingest([{**JOB,'title':'Python <b>raw job</b>'}]);store.evaluate();save(store,store.jobs()[0]['id'],'SECRET TASK',DAY,'SECRET NOTES')
 p=preview(store,today=DAY)
 assert 'SECRET TASK' not in p['message'] and 'SECRET NOTES' not in p['message']
 assert '<b>raw job</b>' in p['message'] # Transport explicitly omits parse_mode.


def test_notification_transport_plain_one_post(monkeypatch):
 import urllib.request
 from jobhunter_app.digests import telegram_digest_send
 calls=[]
 class Response:
  status=200
  def __enter__(self):return self
  def __exit__(self,*a):pass
  def read(self,n):assert n==65537;return b'{"ok":true}'
 class Opener:
  def open(self,req,timeout):calls.append(req);assert timeout==15;return Response()
 monkeypatch.setattr(urllib.request,'build_opener',lambda *a:Opener())
 assert telegram_digest_send('<b>literal</b>')['delivered']
 req=calls[0];body=json.loads(req.data)
 assert req.full_url=='https://api.telegram.org/bot123:FAKE_TOKEN/sendMessage' and req.method=='POST'
 assert 'parse_mode' not in body and body['text']=='<b>literal</b>' and len(calls)==1

@pytest.mark.parametrize('code,expected',[(401,'authorization_failed'),(403,'authorization_failed'),(429,'rate_limited'),(500,'provider_error'),(302,'provider_error')])
def test_transport_errors_redacted_and_retry_header(monkeypatch,code,expected):
 import io,urllib.request
 from urllib.error import HTTPError
 from jobhunter_app.digests import telegram_digest_send
 class Opener:
  def open(self,*a,**kw):raise HTTPError('https://api.telegram.org/botSECRET/sendMessage',code,'SECRET',{'Retry-After':'1200'},io.BytesIO(b'{"parameters":{"retry_after":600}}'))
 monkeypatch.setattr(urllib.request,'build_opener',lambda *a:Opener())
 result=telegram_digest_send('test');assert result['status']==expected and 'SECRET' not in json.dumps(result)
 if code==429:assert result['retry_after']==1200


def test_transport_timeout_and_missing_config(monkeypatch):
 import urllib.request
 from jobhunter_app.digests import telegram_digest_send
 class Opener:
  def open(self,*a,**kw):raise TimeoutError('SECRET')
 monkeypatch.setattr(urllib.request,'build_opener',lambda *a:Opener())
 assert telegram_digest_send('test')['status']=='delivery_unconfirmed'
 monkeypatch.delenv('TELEGRAM_BOT_TOKEN')
 with pytest.raises(ValueError,match='Configure'):telegram_digest_send('test')


def test_inbox_pagination_complete_counts(store):
 job=store.jobs()[0]
 for n in range(105):save(store,job['id'],f'Task {n}',DAY)
 a=digest(store,today=DAY);b=digest(store,today=DAY,offset=100)
 assert a['total']==105 and len(a['items'])==100 and a['has_more']
 assert b['total']==105 and len(b['items'])==5 and not b['has_more']
 assert not {x['id'] for x in a['items']}&{x['id'] for x in b['items']}


def test_schema4_upgrade_preserves_jobs_matches_tracking_notifications(tmp_path):
 p=tmp_path/'canonical.db';s=Store(p);s.save_profile(PROFILE);s.ingest([JOB]);s.evaluate();job=s.jobs()[0]
 s.set_status(job['id'],'applied','Original notes',DAY)
 with s.connect() as db:
  db.execute('INSERT INTO notification_deliveries VALUES(?,?,?,?,?)',('default',job['id'],'fixture','fingerprint','before'))
  for table in ['followups','workflow_settings','digest_deliveries','notification_gates']:db.execute('DROP TABLE '+table)
  db.execute('PRAGMA user_version=4')
  preserved={name:[tuple(r) for r in db.execute('SELECT * FROM '+name)] for name in ['profiles','jobs','matches','applications','status_history','notification_deliveries','audit']}
 s=Store(p)
 with s.connect() as db:
  for name,records in preserved.items():assert [tuple(r) for r in db.execute('SELECT * FROM '+name)]==records
 assert s.jobs()[0]['notes']=='Original notes' and s.jobs()[0]['status']=='applied'
 assert s.jobs()[0]['match']==job['match']


def test_invalid_date_warning_in_digest_and_missing_sender_flag(store,monkeypatch):
 store.set_status(store.jobs()[0]['id'],'reviewing')
 with store.connect() as db:db.execute("UPDATE applications SET deadline='bad'")
 monkeypatch.delenv('TELEGRAM_BOT_TOKEN')
 p=preview(store,today=DAY)
 assert p['counts']['invalid_dates']==1 and 'invalid stored dates omitted' in p['message']
 assert p['destination_configured'] and not p['sender_configured']
