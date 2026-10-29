"""Offline iCalendar format/privacy contracts; no real calendar import claim."""
from datetime import date,timedelta
import json
import re
import sqlite3
import pytest
from jobhunter_app.store import Store
from jobhunter_app.followups import save,complete
from jobhunter_app.calendar_export import preview,export,_text,_fold,MAX_EVENTS
from tests.test_local_store import JOB,PROFILE
from tests.test_web_local import web,request,token

DAY='2026-11-01'
@pytest.fixture
def store(tmp_path):
 s=Store(tmp_path/'calendar.db');s.save_profile(PROFILE);s.ingest([JOB]);s.evaluate();return s

def unfolded(data):
 assert data.endswith(b'\r\n') and b'\n' not in data.replace(b'\r\n',b'')
 assert all(len(line)<=75 for line in data.split(b'\r\n'))
 return re.sub(r'\r\n[ \t]','',data.decode('utf-8'))

def event_ids(data):return re.findall(r'^UID:(.+)$',unfolded(data),re.M)


def test_default_private_generic_file_no_actions(store):
 job=store.jobs()[0];store.set_status(job['id'],'reviewing','PRIVATE APP NOTES',DAY);save(store,job['id'],'PRIVATE TASK',DAY,'PRIVATE TASK NOTES')
 before=store.jobs();content,meta=export(store,start=DAY)
 text=unfolded(content)
 assert meta['events_in_window']==2 and meta['can_export']
 assert text.count('BEGIN:VEVENT')==2 and text.startswith('BEGIN:VCALENDAR\r\nVERSION:2.0\r\n')
 assert 'SUMMARY:Application deadline' in text and 'SUMMARY:Personal follow-up' in text
 assert 'DTSTART;VALUE=DATE:20261101' in text and 'DTEND;VALUE=DATE:20261102' in text
 for secret in ['PRIVATE',PROFILE['name'],PROFILE['facts'][0]['text'],JOB['title'],JOB['company'],JOB['url']]:assert secret not in text
 for forbidden in ['ATTENDEE','ORGANIZER','METHOD:','VALARM','ATTACH:','TZID']:assert forbidden not in text
 assert store.jobs()==before


def test_optin_only_job_context_not_personal_data(store):
 job=store.jobs()[0];save(store,job['id'],'PRIVATE TASK',DAY,'PRIVATE NOTES')
 data,meta=export(store,start=DAY,include_job_details=True)
 text=unfolded(data)
 assert JOB['title'] in text and JOB['company'] in text and JOB['url'] in text
 assert 'PRIVATE' not in text and PROFILE['name'] not in text and PROFILE['facts'][0]['text'] not in text
 assert meta['sample'][0]['summary'].startswith('Personal follow-up — ')
 assert JOB['url'] in meta['sample'][0]['description']


@pytest.mark.parametrize('start,days,past',[('2026-11-01',0,0),('2026-11-01',30,7),('2024-02-28',1,0)])
def test_inclusive_window_and_exclusive_event_end(store,start,days,past):
 first=date.fromisoformat(start)-timedelta(days=past);last=date.fromisoformat(start)+timedelta(days=days);job=store.jobs()[0]
 for d in [first-timedelta(days=1),first,last,last+timedelta(days=1)]:save(store,job['id'],'Task',d.isoformat())
 p=preview(store,start=start,days=days,past_days=past)
 assert p['events_in_window']==2 and p['outside_window_omitted']==2
 data,_=export(store,start=start,days=days,past_days=past)
 assert data.count(b'BEGIN:VEVENT')==2


def test_zero_and_early_year_file(store):
 data,meta=export(store,start=DAY,days=0)
 assert meta['events_in_window']==0 and meta['can_export'] and 'BEGIN:VEVENT' not in data.decode()
 save(store,store.jobs()[0]['id'],'Early','0001-01-01')
 data,_=export(store,start='0001-01-01',days=0)
 assert b'DTSTART;VALUE=DATE:00010101' in data and b'DTEND;VALUE=DATE:00010102' in data


def test_past_default_excluded_and_explicitly_included(store):
 save(store,store.jobs()[0]['id'],'Old','2026-10-31')
 assert preview(store,start=DAY)['events_in_window']==0
 assert preview(store,start=DAY,past_days=1)['events_in_window']==1


@pytest.mark.parametrize('args',[{'days':True},{'days':366},{'days':-1},{'days':2.5},{'past_days':True},{'past_days':366},{'include_job_details':1},{'include_job_details':'yes'},{'start':'20261101'},{'start':'2026-02-30'},{'start':'9999-12-31','days':1},{'start':'0001-01-01','past_days':1}])
def test_window_strict_bounds(store,args):
 with pytest.raises(ValueError):preview(store,**args)


def test_last_possible_day_preview_disables_file(store):
 save(store,store.jobs()[0]['id'],'Impossible end','9999-12-31')
 p=preview(store,start='9999-12-31',days=0)
 assert not p['can_export'] and p['unrepresentable_dates']==1
 with pytest.raises(ValueError,match='year 9999'):export(store,start='9999-12-31',days=0)


def test_completed_and_applied_deadlines_not_exported(store):
 j=store.jobs()[0];store.set_status(j['id'],'applied',deadline=DAY);task=save(store,j['id'],'Task',DAY)
 assert preview(store,start=DAY)['events_in_window']==1
 complete(store,task['id']);assert preview(store,start=DAY)['events_in_window']==0


def test_closed_job_personal_task_remains_explicit(store):
 j=store.jobs()[0];store.set_status(j['id'],'archived',deadline=DAY);save(store,j['id'],'Own task',DAY)
 assert preview(store,start=DAY)['events_in_window']==1


def test_invalid_stored_dates_visible(store):
 j=store.jobs()[0];store.set_status(j['id'],'reviewing',deadline=DAY);save(store,j['id'],'Task',DAY)
 with store.connect() as db:
  db.execute("UPDATE applications SET deadline='20261101'");db.execute("UPDATE followups SET due='bad'")
 p=preview(store,start=DAY);assert p['invalid_dates_omitted']==2 and p['events_in_window']==0


def test_profile_isolation_and_stable_ids_across_backup(store,tmp_path):
 j=store.jobs()[0];store.set_status(j['id'],'reviewing',deadline=DAY);save(store,j['id'],'Task',DAY)
 data,p=export(store,start=DAY)
 backup=tmp_path/'backup.db';store.backup(backup);b=Store(backup)
 assert preview(b,start=DAY)['fingerprint']==p['fingerprint'] and event_ids(export(b,start=DAY)[0])==event_ids(data)
 store.save_profile(PROFILE,'other');assert preview(store,'other',DAY)['events_in_window']==0
 store.set_status(j['id'],'reviewing',deadline=DAY,profile_id='other')
 other=export(store,'other',DAY)[0];assert not set(event_ids(other))&set(event_ids(data))
 assert 'default' not in data.decode() and 'calendar.db' not in data.decode()


def test_reschedule_keeps_uid_but_changes_fingerprint(store):
 j=store.jobs()[0];task=save(store,j['id'],'Task',DAY);data,p=export(store,start=DAY)
 save(store,j['id'],'Changed private title','2026-11-02',followup_id=task['id'])
 changed,meta=export(store,start=DAY)
 assert event_ids(data)==event_ids(changed) and meta['fingerprint']!=p['fingerprint']
 with pytest.raises(ValueError,match='changed'):export(store,start=DAY,fingerprint=p['fingerprint'])


def test_private_notes_changes_do_not_change_export_content_hash(store):
 j=store.jobs()[0];task=save(store,j['id'],'Private A',DAY,'Notes A');p=preview(store,start=DAY)
 save(store,j['id'],'Private B',DAY,'Notes B',followup_id=task['id'])
 assert preview(store,start=DAY)['fingerprint']==p['fingerprint']


@pytest.mark.parametrize('fingerprint',['',False,0,'x'*64,'f'*65])
def test_invalid_fingerprints(store,fingerprint):
 with pytest.raises(ValueError):export(store,start=DAY,fingerprint=fingerprint)


def test_optin_or_window_change_invalidates_fingerprint(store):
 p=preview(store,start=DAY)
 for kwargs in [{'include_job_details':True},{'days':0},{'past_days':1}]:
  with pytest.raises(ValueError,match='changed'):export(store,start=DAY,fingerprint=p['fingerprint'],**kwargs)


def test_no_network_no_writes_or_cache_changes(store,monkeypatch):
 import socket
 monkeypatch.setattr(socket,'create_connection',lambda *a,**k:pytest.fail('No calendar network'))
 with store.connect() as db:before={t:[tuple(r) for r in db.execute('SELECT * FROM '+t)] for t in ['profiles','jobs','matches','applications','audit','notification_deliveries','digest_deliveries','followups','workflow_settings']}
 assert preview(store,start=DAY)==preview(store,start=DAY);export(store,start=DAY)
 with store.connect() as db:
  for t,values in before.items():assert [tuple(r) for r in db.execute('SELECT * FROM '+t)]==values


def test_more_than_dashboard_page_and_hard_cap(store):
 j=store.jobs()[0]
 with store.connect() as db:
  db.executemany('INSERT INTO followups VALUES(?,?,?,?,?,?,?,?)',[(f'fixture-{n}','default',j['id'],'PRIVATE',DAY,'PRIVATE',0,'before') for n in range(MAX_EVENTS)])
 p=preview(store,start=DAY);data,_=export(store,start=DAY)
 assert p['events_in_window']==1000 and len(p['sample'])==10 and not p['sample_is_complete']
 assert data.count(b'BEGIN:VEVENT')==1000
 save(store,j['id'],'One too many',DAY)
 p=preview(store,start=DAY);assert p['events_in_window']==1001 and not p['can_export']
 with pytest.raises(ValueError,match='No partial'):export(store,start=DAY)


@pytest.mark.parametrize('value',['é'*200,'عربي، نص;'+('🔥'*200),'x'*300,'line1\r\nline2\rline3\nBEGIN:VALARM','\\,;'])
def test_utf8_folding_unfolds_and_text_escaping(value):
 escaped=_text(value);line='SUMMARY:'+escaped
 folded=_fold(line)
 assert all(len(x.encode('utf-8'))<=75 for x in folded.split('\r\n'))
 assert folded.replace('\r\n ','')==line
 assert '\r' not in escaped and '\n' not in escaped
 assert 'BEGIN:VALARM' not in '\r\n'.join(folded.split('\r\n')[1:]) or not any(x=='BEGIN:VALARM' for x in folded.split('\r\n'))


def test_injected_properties_never_become_ics_lines(store):
 malicious='Python; comma, slash\\\r\nBEGIN:VALARM\r\nATTENDEE:mailto:bad@example.org'
 store.ingest([{**JOB,'title':malicious}]);save(store,store.jobs()[0]['id'],'Private',DAY)
 text=unfolded(export(store,start=DAY,include_job_details=True)[0])
 assert '\\; comma\\, slash\\\\\\nBEGIN:VALARM\\nATTENDEE' in text
 assert not re.search(r'\r\n(?:ATTENDEE|BEGIN:VALARM)',text)


def test_missing_profile_and_local_date_defaults(store):
 with pytest.raises(ValueError):preview(store,'missing',DAY)
 assert preview(store,days=0)['start']==date.today().isoformat()


def test_web_preview_download_and_stale_protection(web):
 s,_=web;s.ingest([JOB]);j=s.jobs()[0];s.set_status(j['id'],'reviewing',deadline=DAY)
 query='start='+DAY+'&days=30&details=0';r=request(web,'GET','/api/calendar-preview?'+query)
 assert r[0]==200;p=json.loads(r[2]);assert p['events_in_window']==1
 assert request(web,'GET','/api/calendar-export?'+query)[0]==400
 status,headers,data=request(web,'GET','/api/calendar-export?'+query+'&fingerprint='+p['fingerprint'])
 assert status==200 and headers['Content-Type'].startswith('text/calendar')
 assert headers['Content-Disposition']=='attachment; filename="jobhunter-reminders.ics"'
 assert data.count(b'BEGIN:VEVENT')==1 and JOB['title'].encode() not in data
 s.set_status(j['id'],'applied')
 assert request(web,'GET','/api/calendar-export?'+query+'&fingerprint='+p['fingerprint'])[0]==400
 assert request(web,'GET','/calendar.js')[0]==200
 assert request(web,'GET','/api/calendar-preview?details=maybe')[0]==400
 assert request(web,'GET','/api/calendar-preview?days=-1')[0]==400
 assert request(web,'GET','/api/calendar-preview',headers={'Host':'evil.example'})[0]==403


def test_output_byte_bound_visible_in_preview(store,monkeypatch):
 import jobhunter_app.calendar_export as module
 save(store,store.jobs()[0]['id'],'Task',DAY)
 normal=preview(store,start=DAY);assert normal['output_bytes']>100 and not normal['output_limit_exceeded']
 monkeypatch.setattr(module,'MAX_BYTES',100)
 p=preview(store,start=DAY)
 assert not p['can_export'] and p['output_limit_exceeded'] and p['output_bytes']>p['max_bytes']
 with pytest.raises(ValueError,match='8-MiB'):export(store,start=DAY)
