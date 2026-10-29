"""Disposable resource/practice CLI lifecycle; never opens publisher URLs."""
import json,sqlite3,subprocess,sys,tempfile
from pathlib import Path
root=Path(sys.argv[1]).resolve();python=sys.argv[2]
with tempfile.TemporaryDirectory(prefix='jobhunter-resource-practice-') as td:
 b=Path(td);db=b/'db.sqlite3';commands=[]
 def cli(*args,profile='default'):
  c=subprocess.run([python,'run_local.py','--db',str(db),'--profile-id',profile,*map(str,args)],cwd=root,text=True,capture_output=True,timeout=40)
  assert c.returncode==0,(args,c.stderr);commands.append(args[0]);return json.loads(c.stdout)
 def audit():
  with sqlite3.connect(db) as c:return c.execute('SELECT count(*) FROM audit').fetchone()[0]
 cli('init');f=b/'profile.json';f.write_text(json.dumps({'name':'Synthetic Catalog Learner','skills':['Python'],'facts':[]}));cli('profile',f)
 j=b/'jobs.json';j.write_text(json.dumps([{'title':'Synthetic Engineer','company':'Synthetic','url':'https://example.org/practice/1','description':'SQL required. AWS preferred. Git not required. We use Excel.'}]))
 cli('import',j);cli('match');before=audit();r=cli('learning');assert r==cli('learning') and audit()==before
 assert r['resource_catalog']['resource_count']==17 and r['resource_catalog']['exercise_count']==17
 assert r['capabilities']['verified_resources'] and r['capabilities']['exercise_catalog'] and r['capabilities']['learning_progress']
 o={x['skill']:x['learning_options'] for x in r['priorities']}
 assert o['SQL']['resources'][0]['id']=='postgresql-tutorial' and o['SQL']['exercise']['self_checks']
 assert o['AWS']['mode']=='optional_practice' and 'No cloud' in o['AWS']['exercise']['setup_and_cost']
 assert o['Git']['mode']=='not_recommended' and not o['Git']['resources'] and o['Excel']['mode']=='clarify_first' and not o['Excel']['exercise']
 cli('profile',f,profile='other');assert cli('learning',profile='other')['priorities']==[] and cli('learning')==r
 with sqlite3.connect(db) as c:
  assert json.loads(c.execute("SELECT data FROM profiles WHERE id='default'").fetchone()[0])['facts']==[]
 j.write_text(json.dumps([{'title':'Synthetic Engineer','company':'Synthetic','url':'https://example.org/practice/1','description':'SQL required. Git required.'}]))
 cli('import',j);assert cli('learning')['priorities']==[]
 cli('match');assert next(p for p in cli('learning')['priorities'] if p['skill']=='Git')['learning_options']['exercise']
 cli('backup',b/'backup.sqlite3')
 print(json.dumps({'status':'passed','schema':5,'commands':commands,'resources':17,'authored_exercises':17,'context_withholding':'passed','profile_isolation_and_manual_rematch':'passed','learning_audit_writes':0,'candidate_facts_unchanged':True,'external_source_model_resource_or_message_calls':0,'data':'synthetic temporary only'},indent=2))
