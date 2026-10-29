"""Fresh synthetic UI workspace; refuses existing DB; no external calls."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from jobhunter_app.store import Store
from jobhunter_app.web import serve
p=argparse.ArgumentParser();p.add_argument('--db',type=Path,required=True);p.add_argument('--port',type=int,default=8784);a=p.parse_args()
if a.db.exists():raise SystemExit('QA requires a new disposable database path')
s=Store(a.db);s.save_profile({'name':'Synthetic Context Learner','skills':['Python'],'facts':[],'excluded_title_terms':['Senior']})
rows=[('Engineer','SQL required.\nDocker preferred.\nGit not required.\nAWS required or optional.\nWe use Excel.'),
      ('Engineer','SQL required; SQL not required.\nDocker preferred <img src=x onerror=window.BAD_LEARN=1>.\nGit not required.'),
      ('Senior Engineer','Java required.'),('Engineer','React required.')]
s.ingest([{'title':title,'company':'Synthetic Learning Employer','url':f'https://example.org/learning-ui/{i}','description':text} for i,(title,text) in enumerate(rows)]);s.evaluate()
with s.connect() as db:
    row=db.execute("SELECT m.job_id,m.data FROM matches m JOIN jobs j ON j.id=m.job_id WHERE j.description='React required.'").fetchone()
    value=json.loads(row['data']);value['fingerprints']['profile']='synthetic stale input'
    db.execute('UPDATE matches SET data=? WHERE job_id=?',(json.dumps(value),row['job_id']))
serve(s,a.port)
