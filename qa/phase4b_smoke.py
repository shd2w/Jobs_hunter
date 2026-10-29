"""No provider/model calls; installed-runtime CLI and mode checks."""
from pathlib import Path
import subprocess,tempfile,json,os,sys
root=Path(sys.argv[1]);py=sys.argv[2]
with tempfile.TemporaryDirectory(prefix='jobhunter-phase4b-') as td:
 d=Path(td);db=d/'app.db';commands=[]
 def cli(*args,env=None,expected=0):
  e=dict(os.environ);e.pop('JOBHUNTER_AUTHORIZED_BOARD_ROBOTS',None)
  if env:e.update(env)
  r=subprocess.run([py,'run_local.py','--db',str(db),*map(str,args)],cwd=root,env=e,capture_output=True,text=True,timeout=40)
  assert r.returncode==expected,(args,r.returncode,r.stderr);commands.append(args[0])
  return json.loads(r.stdout) if not expected else r.stderr
 status=cli('semantic-status');assert not db.exists() and not status['downloads_enabled'] and not status['ready']
 cli('init');cat=cli('source-catalog')
 assert len(cat)==17
 for row in cat:
  if row['kind'] in ('wuzzuf','naukrigulf'):assert row['robots_mode']=='skip' and row['requests']==5
  else:assert 'robots_mode' not in row
 checked=cli('source-catalog',env={'JOBHUNTER_AUTHORIZED_BOARD_ROBOTS':'check'})
 assert all(x['robots_mode']=='check' and x['requests']==6 for x in checked if x['kind'] in ('wuzzuf','naukrigulf'))
 sid=cli('source','wuzzuf','https://wuzzuf.net/a/Jobs-in-Egypt')['source']
 assert 'approved' in cli('scan',sid,expected=2)
 cli('profile',root/'examples/matching-profile.json')
 assert 'local model directory' in cli('semantic-rank','--model-dir',d/'missing',expected=2)
 assert not cli('summary')['total_jobs']
 print(json.dumps({'status':'passed','commands':commands,'source_or_model_requests':0,'default_authorized_board_robots_mode':'skip','schema':5,'data':'synthetic temporary database only'}))
