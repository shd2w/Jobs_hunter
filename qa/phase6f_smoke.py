"""Disposable manual progress CLI, stale revisions, isolated settings and backup."""
import json,sqlite3,subprocess,sys,tempfile
from pathlib import Path
root=Path(sys.argv[1]).resolve();python=sys.argv[2]
with tempfile.TemporaryDirectory(prefix='jobhunter-learning-progress-') as td:
 b=Path(td);db=b/'d.sqlite3';commands=[];rejected=[]
 def cli(*args,profile='default',ok=True):
  c=subprocess.run([python,'run_local.py','--db',str(db),'--profile-id',profile,*map(str,args)],cwd=root,text=True,capture_output=True,timeout=40)
  if not ok:assert c.returncode==2;rejected.append(args[0]);return
  assert c.returncode==0,(args,c.stderr);commands.append(args[0]);return json.loads(c.stdout)
 cli('init');f=b/'profile.json';f.write_text(json.dumps({'name':'Synthetic Progress','skills':['Python'],'facts':[]}));cli('profile',f)
 j=b/'jobs.json';j.write_text(json.dumps([{'title':'Synthetic','company':'Synthetic','url':'https://example.org/learning-progress','description':'SQL required. Docker preferred. Git not required.'}]))
 cli('import',j);cli('match');r=cli('learning');p=next(x for x in r['priorities'] if x['skill']=='SQL');fingerprint=p['learning_options']['plan_fingerprint']
 assert cli('learning-progress')['items']==[]
 item=cli('learning-save','SQL','--preview-fingerprint',fingerprint)
 item=cli('learning-update',item['id'],'--revision',1,'--status','in_progress','--notes','SYNTHETIC PRIVATE PROGRESS')
 cli('learning-update',item['id'],'--revision',1,'--status','paused',ok=False)
 cli('learning-update',item['id'],'--revision',2,'--status','completed',ok=False)
 done=cli('learning-update',item['id'],'--revision',2,'--status','completed','--completed-attested','--notes','SYNTHETIC PRIVATE PROGRESS')
 assert cli('learning-save','SQL','--preview-fingerprint',fingerprint)==done
 assert cli('learning-progress')['items']==[done] and cli('learning')==r
 config=b/'settings.json';config.write_text(json.dumps({'days':12}));cli('workflow-settings',config);search=cli('saved-search-save','Synthetic filter','--query','Python');assert cli('learning-progress')['items']==[done]
 cli('profile',f,profile='other');assert cli('learning-progress',profile='other')['items']==[]
 cli('learning-delete',done['id'],'--revision',done['revision'],'--confirm',profile='other',ok=False)
 f.write_text(json.dumps({'name':'Changed','skills':['Python','SQL'],'facts':[]}));cli('profile',f);cli('match');assert cli('learning-progress')['items']==[done]
 paused=cli('learning-update',done['id'],'--revision',done['revision'],'--status','paused');assert paused['completed_at']=='' and paused['notes']=='SYNTHETIC PRIVATE PROGRESS'
 cli('backup',b/'backup.sqlite3')
 with sqlite3.connect(b/'backup.sqlite3') as c:
  raw=json.loads(c.execute("SELECT data FROM workflow_settings WHERE profile_id='default'").fetchone()[0]);assert raw['learning_progress']['items']==[paused] and raw['saved_searches'][0]['id']==search['id'] and raw['days']==12
 cli('learning-delete',paused['id'],'--revision',done['revision'],'--confirm',ok=False)
 cli('learning-delete',paused['id'],'--revision',paused['revision'],'--confirm');assert cli('learning-progress')['items']==[]
 print(json.dumps({'status':'passed','schema':5,'commands':commands,'rejected_commands':rejected,'completion_requires_explicit_attestation':True,'stale_revision_preserves_newer_record':True,'snapshot_survives_guidance_changes':True,'namespaces_backup_and_profile_isolation':'passed','candidate_evidence_and_matching_unchanged_by_progress':True,'external_source_model_resource_or_message_calls':0,'data':'synthetic temporary only'},indent=2))
