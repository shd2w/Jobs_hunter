"""Synthetic core CLI version/review lifecycle; never contacts a provider."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
root=Path(sys.argv[1]).resolve();python=sys.argv[2]
with tempfile.TemporaryDirectory(prefix='jobhunter-pack-versions-') as td:
    base=Path(td);commands=[]
    def cli(*args,expected=0):
        proc=subprocess.run([python,'run_local.py','--db',str(base/'local.sqlite3'),*map(str,args)],cwd=root,text=True,capture_output=True,timeout=40)
        assert proc.returncode==expected,(args[0],proc.stderr)
        commands.append(args[0]);return json.loads(proc.stdout) if expected==0 else proc.stderr
    cli('init');profile={'name':'Synthetic Pack Candidate','skills':['Python'],'facts':[{'text':'I built a Python project.','source':'Synthetic evidence','verified':True}]}
    f=base/'profile.json';f.write_text(json.dumps(profile));cli('profile',f)
    jobs=base/'jobs.json';jobs.write_text(json.dumps([{'title':'Python Engineer','company':'Synthetic Pack Employer','url':'https://example.org/pack-smoke','description':'Python required.'}]))
    cli('import',jobs);cli('match');job=cli('list')[0];out=base/'packs'
    p=cli('pack',job['id'],'--output',out);version=p['version_id'];assert p['review_state']=='pending'
    listing=cli('pack-list','--job-id',job['id'],'--output',out);assert listing['packs'][0]['version_id']==version
    preview=cli('pack-inspect',version,'--output',out);assert preview['valid']
    args=('pack-review',version,'--output',out,'--decision','reviewed','--fingerprint',preview['fingerprint'])
    cli(*args,expected=2)
    reviewed=cli(*args,'--confirm');assert reviewed['review_state']=='reviewed'
    cli(*args,'--confirm',expected=2) # Prior preview cannot append a second decision.
    fresh=cli('pack-inspect',version,'--output',out)
    rejected=cli('pack-review',version,'--output',out,'--decision','needs_changes','--fingerprint',fresh['fingerprint'],'--confirm');assert rejected['review_state']=='needs_changes'
    second=cli('pack',job['id'],'--output',out);assert second['version_id']!=version and second['review_state']=='pending'
    f.write_text(json.dumps({**profile,'name':'Updated Synthetic Candidate'}));cli('profile',f)
    blocked=cli('pack-inspect',version,'--output',out);assert not blocked['valid'] and blocked['review_state']=='blocked' and len(blocked['history'])==2
    cli('pack-review',version,'--output',out,'--decision','reviewed','--fingerprint',blocked['fingerprint'],'--confirm',expected=2)
    cli('pack-inspect','../outside','--output',out,expected=2)
    cli('pack-list','--output',out,'--offset',50);assert cli('list')[0]['status']=='discovered'
    cli('backup',base/'database-only.sqlite3')
    print(json.dumps({'status':'passed','schema':5,'commands':commands,'review_states':['pending','reviewed','needs_changes','blocked'],
                      'confirmed_review_and_stale_preview':'passed','old_history_preserved':True,'application_status':'unchanged',
                      'source_model_resource_or_message_calls':0,'data':'disposable synthetic only'},indent=2))
