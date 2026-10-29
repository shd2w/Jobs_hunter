"""Manual Phase 5 CLI smoke; no delivery, source or model requests."""
from pathlib import Path
import subprocess,tempfile,json,sys,os
root=Path(sys.argv[1]);py=sys.argv[2]
with tempfile.TemporaryDirectory(prefix='jobhunter-phase5-') as td:
 d=Path(td);db=d/'local.db';commands=[];env=dict(os.environ)
 for key in ('TELEGRAM_BOT_TOKEN','TELEGRAM_CHAT_ID'):env.pop(key,None)
 def cli(*args,profile='default',expected=0):
  r=subprocess.run([py,'run_local.py','--db',str(db),'--profile-id',profile,*map(str,args)],cwd=root,env=env,capture_output=True,text=True,timeout=40)
  assert r.returncode==expected,(args[0],r.returncode,r.stderr);commands.append(args[0]);return json.loads(r.stdout) if not expected else r.stderr
 assert cli('init')['schema']==5
 p=d/'profile.json';p.write_text(json.dumps({'name':'Synthetic','skills':['Python'],'facts':[]}));cli('profile',p)
 f=d/'jobs.json';f.write_text(json.dumps([{'title':'Python Engineer','company':'Fixture','url':'https://example.org/phase5/1','description':'Python required'}]));cli('import',f);cli('match');job=cli('list')[0]
 cli('status',job['id'],'reviewing','--deadline','2026-11-01','--notes','PRIVATE NOTES')
 task=cli('followup-add',job['id'],'PRIVATE TASK','2026-11-01','--notes','PRIVATE TASK NOTES')
 inbox=cli('inbox','--today','2026-11-01');assert inbox['total']==2 and inbox['counts']['today']==2
 assert cli('workflow-settings')['enabled'] is False
 config=d/'settings.json';config.write_text(json.dumps({'enabled':False,'include_job_details':False}));cli('workflow-settings',config)
 preview=cli('digest-preview','--today','2026-11-01');assert 'PRIVATE' not in preview['message'] and not preview['destination_configured']
 assert cli('digest-send','--confirm',preview['fingerprint'],expected=2)
 cli('followup-done',task['id']);assert cli('inbox','--today','2026-11-01','--include-completed')['counts']['completed']==1
 cli('followup-done',task['id'],'--reopen');cli('followup-add',job['id'],'Rescheduled','2026-11-02','--id',task['id'])
 assert cli('workflow-report')['ever_marked_applied']==0
 cli('status',job['id'],'applied');assert cli('workflow-report')['ever_marked_applied']==1
 cli('init',profile='other');assert cli('inbox','--today','2026-11-01',profile='other')['total']==0
 cli('export',d/'export.json');cli('backup',d/'backup.db')
 print(json.dumps({'status':'passed','schema':5,'commands':commands,'source_model_or_message_requests':0,'data':'synthetic temporary records only'}))
