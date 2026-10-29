"""Release smoke. All inputs/output/databases are synthetic and temporary."""
from pathlib import Path
import subprocess,json,tempfile,sys
root=Path(sys.argv[1]);py=sys.argv[2];excel='--excel' in sys.argv
with tempfile.TemporaryDirectory(prefix='jobhunter-phase3-') as td:
 d=Path(td);db=d/'app.db';commands=[]
 def cli(*args, expected=0, profile='default'):
  r=subprocess.run([py,'run_local.py','--db',str(db),'--profile-id',profile,*map(str,args)],cwd=root,capture_output=True,text=True,timeout=40)
  assert r.returncode==expected,(args[0],r.returncode,r.stderr)
  commands.append(args[0]);return json.loads(r.stdout) if expected==0 else r.stderr
 assert cli('init')['schema']==5
 assert len(cli('source-catalog'))==17
 assert set('ABCDEFGHIJKL')=={r['category'] for r in cli('source-directory','--query','Python Cairo')}
 assert cli('source-health')==[]
 for kind,url in [('wuzzuf','https://wuzzuf.net/a/Jobs-in-Egypt'),('naukrigulf','https://www.naukrigulf.com/jobs-in-egypt')]:
  assert not cli('source',kind,url)['approved']
 sid=cli('source','jobicy','remote')['source']
 assert all(x['approved']==0 for x in cli('source-health'))
 assert 'error' in cli('scan-batch',sid)['results'][0]
 assert cli('source-reset',sid)['reset']==sid
 post=cli('posts-import','examples/posts.json','--rights-attested')['items'][0]['id']
 info=cli('post',post);fields=info['extracted']['fields'];fields['description']=info['body'];review=d/'review.json';review.write_text(json.dumps(fields))
 cli('post-accept',post,review,'--confirmed')
 cli('feed-import','examples/jobs.rss','--rights-attested')
 cli('match');cli('export',d/'opportunities.json')
 cli('init',profile='second');cli('import',d/'opportunities.json','--with-state','--dry-run',profile='second')
 cli('import',d/'opportunities.json','--with-state',profile='second')
 assert cli('list',profile='second')[0]['status']=='discovered'
 legacy=d/'legacy';legacy.mkdir()
 job={'title':'Synthetic Analyst','company':'Fixture Only','url':'https://example.org/jobs/migration','description':'SQL'}
 (legacy/'evaluations.json').write_text(json.dumps([{**job,'success':True,'global_score':4,'recommendation':'apply'}]))
 preview=cli('migrate',legacy);assert preview['preview']['inserted']==1
 before=cli('summary')['total_jobs'];result=cli('migrate',legacy,'--apply')
 assert cli('migrate',legacy,'--apply')['already_applied']
 assert len(cli('history'))==1
 cli('history-export',d/'history.json');assert len(json.loads((d/'history.json').read_text())['historical_records'])==1
 assert cli('export-uaa',d/'queue.jsonl')['exported']==0
 assert cli('summary')['total_jobs']==before+1
 cli('restore',Path(result['backup'])/'before.sqlite3',d/'restored.db')
 restore=subprocess.run([py,'run_local.py','--db',str(d/'restored.db'),'summary'],cwd=root,capture_output=True,text=True,timeout=30)
 assert restore.returncode==0 and json.loads(restore.stdout)['total_jobs']==before
 cli('export',d/'opportunities.csv','--format','csv')
 if excel:
  cli('export',d/'opportunities.xlsx','--format','xlsx');cli('import',d/'opportunities.xlsx','--dry-run')
 else:
  assert 'optional' in cli('export',d/'unsupported.xlsx','--format','xlsx',expected=2)
  assert not (d/'unsupported.xlsx').exists()
 cli('backup',d/'backup.db')
 print(json.dumps({'status':'passed','schema':5,'commands':commands,'excel_enabled':excel,'data':'synthetic only','source_network_requests':0}))
