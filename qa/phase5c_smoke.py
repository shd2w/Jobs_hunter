"""Synthetic saved-search CLI flow. No external service or model calls."""
from pathlib import Path
import subprocess,tempfile,json,sys,os
root=Path(sys.argv[1]);py=sys.argv[2]
with tempfile.TemporaryDirectory(prefix='jobhunter-searches-') as td:
 d=Path(td);db=d/'local.sqlite3';commands=[];env=dict(os.environ)
 for key in ('TELEGRAM_BOT_TOKEN','TELEGRAM_CHAT_ID'):env.pop(key,None)
 def cli(*args,profile='default',expected=0):
  r=subprocess.run([py,'run_local.py','--db',str(db),'--profile-id',profile,*map(str,args)],cwd=root,env=env,capture_output=True,text=True,timeout=40)
  assert r.returncode==expected,(args,r.stderr);commands.append(args[0]);return json.loads(r.stdout) if expected==0 else r.stderr
 cli('init');p=d/'profile.json';p.write_text(json.dumps({'name':'SYNTHETIC','skills':['Python'],'facts':[]}));cli('profile',p)
 j=d/'jobs.json';j.write_text(json.dumps([{'title':'Python Engineer','company':'Synthetic','url':'https://example.org/search/smoke','description':'Python required'}]));cli('import',j);cli('match');job=cli('list')[0]
 assert cli('saved-searches')==[]
 a=cli('saved-search-save','Python review','--query','Python','--status','saved');assert cli('saved-search-run',a['id'])['jobs']==[]
 cli('status',job['id'],'saved');assert len(cli('saved-search-run',a['id'])['jobs'])==1
 cli('saved-search-save','Renamed','--query','Python','--id',a['id']);cli('saved-search-save','renamed',expected=2)
 cfg=d/'settings.json';cfg.write_text(json.dumps({'days':11}));cli('workflow-settings',cfg);assert cli('saved-searches')[0]['id']==a['id']
 cli('profile',p,profile='other');assert cli('saved-searches',profile='other')==[];cli('saved-search-run',a['id'],profile='other',expected=2)
 cli('backup',d/'backup.sqlite3');cli('saved-search-delete',a['id'],'--confirm');assert cli('saved-searches')==[]
 cli('saved-search-run',a['id'],expected=2);assert cli('workflow-settings')['days']==11
 print(json.dumps({'status':'passed','schema':5,'commands':commands,'provider_model_or_message_calls':0,'data':'synthetic disposable inputs only'},indent=2))
