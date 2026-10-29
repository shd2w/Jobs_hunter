"""Phase 4e synthetic CLI review, persistence and isolation; zero network/model calls."""
from pathlib import Path
import subprocess,tempfile,json,sys
root=Path(sys.argv[1]);py=sys.argv[2]
with tempfile.TemporaryDirectory(prefix='jobhunter-context-') as td:
 d=Path(td);db=d/'canonical.db';commands=[]
 def cli(*args,profile='default'):
  r=subprocess.run([py,'run_local.py','--db',str(db),'--profile-id',profile,*map(str,args)],cwd=root,capture_output=True,text=True,timeout=40)
  assert r.returncode==0,(args[0],r.stderr);commands.append(args[0]);return json.loads(r.stdout)
 cli('init');p=d/'profile.json';p.write_text(json.dumps({'name':'Synthetic','skills':['Python'],'facts':[]}));cli('profile',p)
 f=d/'jobs.json';f.write_text(json.dumps([{'title':'Python Engineer','company':'Fixture','url':'https://example.org/phase4e/1','location':'Remote in Germany','description':'Python required\nEnglish B2 required\n3 years experience required\nDegree preferred\nVisa required\nSalary EUR 60000'}]));cli('import',f);cli('match');job=cli('list')[0]
 assert job['match']['score_percent']==100 and job['match']['eligibility']=='needs_review'
 context=job['match']['eligibility_context'];assert len({r['category'] for r in context['evidence']})==6
 assert all(r['candidate_assessment']=='not_assessed' for r in context['categories'])
 cli('init',profile='other');assert cli('list',profile='other')[0]['match'] is None
 cli('profile',p,profile='other');cli('match',profile='other');assert cli('list',profile='other')[0]['match']['eligibility_context']==context
 cli('profile',p);assert cli('list')[0]['match'] is None
 cli('match');cli('export',d/'jobs-export.json');cli('backup',d/'backup.db')
 print(json.dumps({'status':'passed','commands':commands,'schema':5,'provider_or_model_requests':0,'data':'synthetic temporary records only'}))
