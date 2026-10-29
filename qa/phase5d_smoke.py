"""Synthetic aggregate-report CLI checks, no source/model/delivery requests."""
from pathlib import Path
import subprocess,tempfile,json,sys,os,csv,io
root=Path(sys.argv[1]);py=sys.argv[2]
with tempfile.TemporaryDirectory(prefix='jobhunter-outcomes-') as td:
 d=Path(td);db=d/'local.sqlite3';commands=[];env=dict(os.environ)
 for key in ('TELEGRAM_BOT_TOKEN','TELEGRAM_CHAT_ID'):env.pop(key,None)
 def cli(*args,profile='default',expected=0):
  r=subprocess.run([py,'run_local.py','--db',str(db),'--profile-id',profile,*map(str,args)],cwd=root,env=env,capture_output=True,text=True,timeout=40)
  assert r.returncode==expected,(args,r.stderr);commands.append(args[0]);return json.loads(r.stdout) if expected==0 else r.stderr
 cli('init');p=d/'profile.json';p.write_text(json.dumps({'name':'PRIVATE CANDIDATE','skills':['Python'],'facts':[]}));cli('profile',p)
 j=d/'jobs.json';j.write_text(json.dumps([{'title':'PRIVATE JOB','company':'PRIVATE EMPLOYER','url':'https://example.org/outcomes/smoke','description':'Python required'}]));cli('import',j);cli('match');job=cli('list')[0]
 cli('status',job['id'],'applied','--notes','PRIVATE NOTES','--deadline','2026-11-02');cli('status',job['id'],'interview');cli('followup-add',job['id'],'PRIVATE TASK','2026-11-02','--notes','PRIVATE NOTES')
 current=cli('outcome-report');assert current['activity']['events']==2 and current['snapshot']['explicitly_tracked_jobs']==1
 cli('outcome-export',d/'report.json');report=json.loads((d/'report.json').read_text());assert report['activity']['events']==2
 cli('outcome-export',d/'report.csv','--format','csv');rows=list(csv.DictReader(io.StringIO((d/'report.csv').read_text())));assert sum(int(x['value']) for x in rows if x['section']=='activity_status')==2
 for f in ['report.json','report.csv']:assert 'PRIVATE' not in (d/f).read_text()
 cli('outcome-export',d/'report.json',expected=2);cli('outcome-report','--start','2026-11-03','--end','2026-11-01',expected=2)
 old=cli('outcome-report','--start','2000-01-01','--end','2000-01-01');assert old['activity']['events']==0 and old['snapshot']==current['snapshot']
 cli('profile',p,profile='other');other=cli('outcome-report',profile='other');assert other['snapshot']['untracked_jobs']==1 and other['activity']['events']==0
 cli('outcome-report',profile='missing',expected=2);cli('backup',d/'backup.sqlite3');assert cli('list')[0]['status']=='interview'
 print(json.dumps({'status':'passed','schema':5,'commands':commands,'source_model_or_message_calls':0,'data':'synthetic disposable records only'},indent=2))
