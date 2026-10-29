"""Phase 4 CLI contracts on synthetic temporary inputs; zero provider/model calls."""
from pathlib import Path
import subprocess,tempfile,json,sys
root=Path(sys.argv[1]);py=sys.argv[2]
with tempfile.TemporaryDirectory(prefix='jobhunter-phase4-') as td:
 d=Path(td);db=d/'app.db';commands=[]
 def cli(*args,profile='default',expected=0):
  r=subprocess.run([py,'run_local.py','--db',str(db),'--profile-id',profile,*map(str,args)],cwd=root,capture_output=True,text=True,timeout=40)
  assert r.returncode==expected,(args[0],r.returncode,r.stderr);commands.append(args[0])
  return json.loads(r.stdout) if not expected else r.stderr
 cli('init');cli('profile',root/'examples/matching-profile.json')
 job={'title':'Python Engineer','company':'Synthetic Only','url':'https://example.org/phase4/smoke','location':'Cairo','description':'Python required; SQL not required.'}
 f=d/'jobs.json';f.write_text(json.dumps([job]));cli('import',f);r=cli('match');assert r['method']=='deterministic contextual lexical v2.2'
 a=cli('list')[0];assert a['match']['ranking']['score_percent'] is not None
 assert any(x['classification']=='not_required' for x in a['match']['requirements'])
 p=json.loads((root/'examples/matching-profile.json').read_text());p['matching']['excluded_companies']=['Synthetic Only'];pf=d/'profile.json';pf.write_text(json.dumps(p));cli('profile',pf)
 assert cli('list')[0]['match'] is None
 cli('match');assert cli('list')[0]['match']['eligibility']=='excluded_by_config'
 cli('init',profile='other');assert cli('list',profile='other')[0]['match'] is None
 p['matching']['weights']['skills']=0;pf.write_text(json.dumps(p));assert 'positive' in cli('profile',pf,expected=2)
 cli('export',d/'export.json');cli('backup',d/'backup.db')
 print(json.dumps({'status':'passed','commands':commands,'schema':5,'data':'synthetic temporary inputs only','provider_or_model_requests':0}))
