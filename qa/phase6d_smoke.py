"""Disposable contextual guidance CLI; no model/provider/resource requests."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
root=Path(sys.argv[1]).resolve();python=sys.argv[2]
with tempfile.TemporaryDirectory(prefix='jobhunter-learning-context-') as td:
    base=Path(td);db=base/'local.sqlite3';commands=[]
    def cli(*args,profile='default'):
        p=subprocess.run([python,'run_local.py','--db',str(db),'--profile-id',profile,*map(str,args)],cwd=root,text=True,capture_output=True,timeout=40)
        assert p.returncode==0,(args[0],p.stderr);commands.append(args[0]);return json.loads(p.stdout)
    def audit_count():
        with sqlite3.connect(db) as conn:return conn.execute('SELECT count(*) FROM audit').fetchone()[0]
    cli('init');profile={'name':'Synthetic Learner','skills':['Python'],'facts':[],'excluded_title_terms':['Senior']}
    f=base/'profile.json';f.write_text(json.dumps(profile));cli('profile',f)
    rows=[{'title':title,'company':'Synthetic Employer','url':f'https://example.org/learn-smoke/{i}','description':text}
          for i,(title,text) in enumerate([('Engineer','SQL not required.'),('Engineer','SQL not required.'),('Engineer','Docker preferred. Git required.'),('Senior Engineer','Java required.')])]
    jobs=base/'jobs.json';jobs.write_text(json.dumps(rows));cli('import',jobs);cli('match')
    before=audit_count();r=cli('learning');assert audit_count()==before and r==cli('learning') and audit_count()==before
    assert r['vacancies_reviewed']==3 and r['coverage']['excluded_vacancies']==1
    assert r['contextual_order']==['Git','Docker','SQL'] and r['priorities'][0]['skill']=='SQL' and r['priorities'][0]['vacancies']==2
    assert next(p for p in r['priorities'] if p['skill']=='SQL')['guidance']['tier']=='negated_only'
    for p in r['priorities']:
        assert sum(p['contexts'].values())==p['vacancies']
        for e in p['evidence_samples']:
            original=next(j['description'] for j in rows if j['url']==e['url']);assert original[e['start']:e['end']]==e['evidence']
    f.write_text(json.dumps({**profile,'skills':['Python','SQL','Docker','Git','Java']}));cli('profile',f,profile='other');cli('match',profile='other');assert cli('learning',profile='other')['priorities']==[]
    assert cli('learning')==r
    jobs.write_text(json.dumps([{**rows[0],'description':'SQL required.'}]));cli('import',jobs)
    stale=cli('learning');assert stale['vacancies_reviewed']==2 and stale['coverage']['unmatched_vacancies']==1
    cli('match');updated=cli('learning');assert updated['vacancies_reviewed']==3 and next(p for p in updated['priorities'] if p['skill']=='SQL')['contexts']['required']==1
    cli('backup',base/'backup.sqlite3')
    print(json.dumps({'status':'passed','schema':5,'commands':commands,'legacy_counts_and_contextual_order':'passed','source_offsets':'passed',
                      'profile_isolation_and_explicit_rematch':'passed','learning_audit_writes':0,'source_model_resource_or_message_calls':0,'data':'synthetic disposable only'},indent=2))
