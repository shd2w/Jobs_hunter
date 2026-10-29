"""Synthetic CLI calendar snapshots; no calendar/provider/model connection."""
from pathlib import Path
import subprocess,tempfile,json,sys,os
root=Path(sys.argv[1]);py=sys.argv[2]
with tempfile.TemporaryDirectory(prefix='jobhunter-calendar-') as td:
 d=Path(td);db=d/'local.db';commands=[];env=dict(os.environ)
 for key in ('TELEGRAM_BOT_TOKEN','TELEGRAM_CHAT_ID'):env.pop(key,None)
 def cli(*args,profile='default',expected=0):
  r=subprocess.run([py,'run_local.py','--db',str(db),'--profile-id',profile,*map(str,args)],cwd=root,env=env,capture_output=True,text=True,timeout=40)
  assert r.returncode==expected,(args[0],r.returncode,r.stderr);commands.append(args[0]);return json.loads(r.stdout) if not expected else r.stderr
 assert cli('init')['schema']==5
 p=d/'profile.json';p.write_text(json.dumps({'name':'PRIVATE CANDIDATE','skills':['Python'],'facts':[]}));cli('profile',p)
 f=d/'jobs.json';f.write_text(json.dumps([{'title':'Python Engineer','company':'Fixture','url':'https://example.org/calendar/1','description':'Python required'}]));cli('import',f);cli('match');job=cli('list')[0]
 cli('status',job['id'],'reviewing','--deadline','2026-11-01','--notes','PRIVATE APP NOTES');task=cli('followup-add',job['id'],'PRIVATE TASK','2026-11-01','--notes','PRIVATE TASK NOTES')
 preview=cli('calendar-preview','--start','2026-11-01');assert preview['events_in_window']==2
 target=d/'generic.ics';cli('calendar-export',target,'--start','2026-11-01','--preview-fingerprint',preview['fingerprint']);original=target.read_bytes()
 assert original.count(b'BEGIN:VEVENT')==2 and b'PRIVATE' not in original and b'Python Engineer' not in original
 cli('calendar-export',target,'--start','2026-11-01',expected=2);assert target.read_bytes()==original
 cli('calendar-export',d/'detailed.ics','--start','2026-11-01','--include-job-details');assert b'Python Engineer' in (d/'detailed.ics').read_bytes() and b'PRIVATE' not in (d/'detailed.ics').read_bytes()
 cli('followup-add',job['id'],'PRIVATE UPDATED','2026-11-02','--id',task['id'])
 cli('calendar-export',d/'stale.ics','--start','2026-11-01','--preview-fingerprint',preview['fingerprint'],expected=2);assert not (d/'stale.ics').exists()
 cli('init',profile='other');assert cli('calendar-preview','--start','2026-11-01',profile='other')['events_in_window']==0
 cli('backup',d/'backup.db');assert cli('list')[0]['status']=='reviewing'
 print(json.dumps({'status':'passed','schema':5,'commands':commands,'live_source_model_calendar_or_message_calls':0,'data':'synthetic temporary records only'}))
