"""New platform availability and automatic intake CLI; all data synthetic, no HTTP."""
from pathlib import Path
import subprocess,tempfile,json,sys,os
root=Path(sys.argv[1]);py=sys.argv[2]
with tempfile.TemporaryDirectory(prefix='jobhunter-phase4d-') as td:
 d=Path(td);db=d/'app.db';commands=[];env=dict(os.environ)
 for key in list(env):
  if key.startswith(('JOBHUNTER_LINKEDIN_','JOBHUNTER_X_','JOBHUNTER_REDDIT_','JOBHUNTER_DISCORD_','JOBHUNTER_TELEGRAM_')):env.pop(key)
 env['JOBHUNTER_POST_MODE']='auto'
 def cli(*args,expected=0):
  r=subprocess.run([py,'run_local.py','--db',str(db),*map(str,args)],cwd=root,env=env,capture_output=True,text=True,timeout=30)
  assert r.returncode==expected,(args,r.returncode,r.stderr);commands.append(args[0]);return json.loads(r.stdout) if expected==0 else r.stderr
 cli('init');policies=cli('source-catalog');assert len(policies)==17
 for kind in ('linkedin','x','reddit','telegram','discord'):
  p=next(p for p in policies if p['kind']==kind);assert p['state']=='setup_required' and p['live_verified'] is False
 sid=cli('source','x','12345','--approve')['source'];assert 'JOBHUNTER_X_BEARER' in cli('scan',sid,expected=2)
 assert cli('source-health')[0]['last_run'] is None
 profile=d/'profile.json';profile.write_text(json.dumps({'name':'QA','skills':['Python'],'facts':[]}));cli('profile',profile)
 rows=[{'body':'We are hiring!\nRole: Python Engineer\nCompany: QA Employer\nApply: https://example.org/jobs/smoke\nPython required','origin_url':'https://example.org/post/smoke'},
       {'body':'Lunch with colleagues','origin_url':'https://example.org/post/non-job'},
       {'body':'We are hiring!\nRole: Data Analyst','origin_url':'https://example.org/post/incomplete'}]
 f=d/'posts.json';f.write_text(json.dumps(rows))
 p=cli('posts-process',f,'--dry-run');assert p['would_auto_add']==1 and cli('summary')['total_jobs']==0
 p=cli('posts-process',f,'--rights-attested');assert p['auto_added']==1 and p['needs_review']==1 and p['skipped']==1 and p['evaluated']==1
 assert cli('list')[0]['status']=='discovered' and cli('summary')['matched_jobs']==1
 assert cli('posts-process',f,'--rights-attested')['auto_added']==0
 assert len(cli('posts','--status','pending'))==1 and len(cli('posts','--status','accepted'))==1
 cli('export',d/'jobs.json');cli('backup',d/'backup.db')
 print(json.dumps({'status':'passed','commands':commands,'data':'synthetic temporary database only','platform_source_or_model_requests':0,'new_apis_live_verified':False,'schema':5}))
