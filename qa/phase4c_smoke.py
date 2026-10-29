"""Offline CLI setup, source mode and optional-runtime contracts; no live calls."""
from pathlib import Path
import importlib.util, json, os, subprocess, sys, tempfile
root=Path(sys.argv[1]); py=sys.argv[2]
with tempfile.TemporaryDirectory(prefix='jobhunter-phase4c-') as td:
 db=Path(td)/'core.db';commands=[]
 def cli(*args,mode='http',expected=0):
  env=dict(os.environ);env['JOBHUNTER_AUTHORIZED_BOARD_TRANSPORT']=mode
  env['JOBHUNTER_AUTHORIZED_BOARD_ROBOTS']='skip'
  r=subprocess.run([py,'run_local.py','--db',str(db),*args],cwd=root,env=env,capture_output=True,text=True,timeout=25)
  assert r.returncode==expected,(args,r.returncode,r.stderr);commands.append(args[0])
  return json.loads(r.stdout) if expected==0 else r.stderr
 assert cli('init')['schema']==5
 for mode in ('http','browser'):
  rows={r['kind']:r for r in cli('source-catalog',mode=mode)}
  assert rows['wuzzuf']['transport']==mode and rows['naukrigulf']['transport']==mode
  assert rows['wuzzuf']['requests']==5 and rows['wuzzuf']['robots_mode']=='skip'
 assert 'must be http or browser' in cli('source-catalog',mode='auto',expected=2)
 directory={r['name']:r for r in cli('source-directory')}
 assert directory['Wuzzuf']['live_verified'] and 'four details' in directory['Wuzzuf']['live_verification_scope']
 sid=cli('source','wuzzuf','https://wuzzuf.net/a/Jobs-in-Egypt')['source']
 assert 'approved' in cli('scan',sid,mode='browser',expected=2)
 assert not cli('summary')['total_jobs']
 print(json.dumps({'status':'passed','commands':commands,'schema':5,'provider_or_model_requests':0,'data':'synthetic temporary database only'}))
