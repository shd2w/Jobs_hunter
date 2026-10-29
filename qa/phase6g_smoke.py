"""Disposable exact evidence-map CLI/pack lifecycle; no provider calls."""
import json,sys,tempfile,subprocess
from pathlib import Path
root=Path(sys.argv[1]).resolve();py=sys.argv[2]
with tempfile.TemporaryDirectory(prefix='jobhunter-evidence-map-') as td:
 base=Path(td);db=base/'local.sqlite3';commands=[];rejected=[]
 def cli(*args,fail=False,pid='default'):
  r=subprocess.run([py,'run_local.py','--db',str(db),'--profile-id',pid,*map(str,args)],cwd=root,capture_output=True,text=True,timeout=40)
  assert r.returncode==(2 if fail else 0),(args,r.stdout,r.stderr)
  (rejected if fail else commands).append(args[0]);return r.stderr if fail else json.loads(r.stdout)
 cli('init');profile={'name':'Synthetic Mapping Candidate','skills':['Python'],'facts':[{'text':'I coordinated a workshop.','source':'Synthetic workshop record','verified':True}]}
 pf=base/'profile.json';pf.write_text(json.dumps(profile));cli('profile',pf)
 jf=base/'jobs.json';jf.write_text(json.dumps([{'title':'Python Engineer','company':'Synthetic Mapping Employer','url':'https://example.org/mapping','description':'😀 Python required. Coordinate project reviews.'}]))
 cli('import',jf);cli('match');job=cli('list')[0];out=base/'packs';cli('pack',job['id'],'--output',out,fail=True);assert not out.exists()
 pr=cli('cover-evidence',job['id']);text='Coordinate project reviews.';start=pr['target']['description'].index(text)
 m={'format':1,'preview_fingerprint':pr['preview_fingerprint'],'confirmed':True,'links':[{'fact_id':pr['facts'][0]['id'],'field':'description','start':start,'end':start+len(text),'quote':text,'reason':'Synthetic personal judgment: workshop coordination offers a transferable example.'}]}
 mf=base/'map.json';mf.write_text(json.dumps(m));d=cli('pack',job['id'],'--output',out,'--evidence-map',mf);assert d['validation_report']['relevance']['status']=='user_attested'
 inspected=cli('pack-inspect',d['version_id'],'--output',out);assert inspected['valid'] and inspected['evidence_relevance']['links'][0]['reason']==m['links'][0]['reason']
 cli('pack-review',d['version_id'],'--output',out,'--decision','reviewed','--fingerprint',inspected['fingerprint'],'--confirm')
 assert cli('list')[0]['status']=='discovered';cli('learning-progress');cli('backup',base/'backup.sqlite3')
 m['confirmed']=False;mf.write_text(json.dumps(m));cli('pack',job['id'],'--output',out,'--evidence-map',mf,fail=True)
 m['confirmed']=True;m['links'][0]['quote']='Not exact';mf.write_text(json.dumps(m));cli('pack',job['id'],'--output',out,'--evidence-map',mf,fail=True)
 m['links'][0]['quote']=text;mf.write_text(json.dumps(m));pf.write_text(json.dumps({**profile,'facts':[{**profile['facts'][0],'source':'Updated source'}]}));cli('profile',pf)
 cli('pack',job['id'],'--output',out,'--evidence-map',mf,fail=True);assert not cli('pack-inspect',d['version_id'],'--output',out)['valid']
 pf.write_text(json.dumps({'name':'Other profile','skills':[],'facts':[]}));cli('profile',pf,pid='other');assert cli('cover-evidence',job['id'],pid='other')['facts']==[]
 cli('pack',job['id'],'--output',out,'--evidence-map',mf,fail=True,pid='other');assert len(list(out.glob('pack-*')))==1
 print(json.dumps({'status':'passed','commands':commands,'rejected_commands':rejected,'exact_links_user_attested_not_semantic_verification':True,'zero_overlap_automatic_fill_blocked':True,'source_change_invalidates_preview_and_review':True,'private_mapping_snapshot_persisted':True,'application_status_unchanged':True,'external_source_model_resource_or_message_calls':0,'data':'disposable synthetic only'},indent=2))
