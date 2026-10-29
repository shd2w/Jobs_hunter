"""Disposable mapping fixture; refuses existing DB and makes no external requests."""
import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from jobhunter_app.store import Store
from jobhunter_app.web import serve
p=argparse.ArgumentParser();p.add_argument('--db',type=Path,required=True);p.add_argument('--port',type=int,default=8790);a=p.parse_args()
if a.db.exists():raise SystemExit('Use a new disposable database')
if (a.db.parent/'preparation-packs').exists():raise SystemExit('Use a new isolated parent directory: sibling preparation-packs already exists')
s=Store(a.db);s.save_profile({'name':'Synthetic Mapping Candidate','skills':['Python'],'facts':[{'text':'I built a Python project.','source':'Synthetic project','verified':True},{'text':'I coordinated a workshop.','source':'Synthetic record <img src=x onerror=window.BAD_MAPPING=1>','verified':True}]})
s.ingest([{'title':'Python Engineer','company':'Synthetic Mapping Employer','url':'https://example.org/mapping-ui','description':'😀 Python required.\nCoordinate project reviews.\nPython preferred.'}]);s.evaluate();serve(s,a.port)
