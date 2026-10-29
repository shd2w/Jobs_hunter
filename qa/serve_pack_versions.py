"""Fresh synthetic local UI workspace only; refuses any existing database."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from jobhunter_app.store import Store
from jobhunter_app.web import serve
p=argparse.ArgumentParser();p.add_argument('--db',type=Path,required=True);p.add_argument('--port',type=int,default=8782);args=p.parse_args()
if args.db.exists():raise SystemExit('QA requires a new disposable database path')
s=Store(args.db)
s.save_profile({'name':'Synthetic Pack Reviewer','skills':['Python'],'facts':[{'text':'I built a Python project.','source':'Synthetic record <img src=x onerror=window.BAD_PACK=1>','verified':True}]})
s.ingest([{'title':'Python Engineer','company':'Synthetic Pack Employer','url':'https://example.org/pack-review','description':'Python required.'}]);s.evaluate();serve(s,args.port)
