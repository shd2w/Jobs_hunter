import os
os.environ.setdefault("JOBHUNTER_POST_MODE","review")
"""Synthetic UI QA only. Does not read or write the user's real database."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from jobhunter_app.store import Store
from jobhunter_app.web import serve
p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--port',type=int,default=8765);args=p.parse_args()
s=Store(args.db)
s.save_profile({'name':'Demo Candidate','skills':['Python','SQL'],'facts':[{'text':'I built a Python data analysis project.','source':'Synthetic QA fixture only','verified':True}]})
s.ingest([
 {'title':'Python Engineer','company':'Example Analytics','url':'https://example.com/jobs/python','location':'Remote · Europe','description':'Build data workflows in Python and SQL. Docker knowledge preferred.'},
 {'title':'Data Analyst','company':'Example Research','url':'https://example.com/jobs/data','location':'Berlin, Germany','description':'SQL, Excel and communication skills. Work authorization requires review.'},
 {'title':'مهندس تعلم الآلة','company':'Example Labs','url':'https://example.com/jobs/ml','location':'Cairo, Egypt','description':'Python, تعلم الآلة and data analysis.'},
 {'title':'<img src=x onerror=alert(1)>','company':'Untrusted listing test','url':'https://example.com/jobs/xss','location':'Unknown','description':'<script>alert("test")</script> Python job, intentionally hostile fixture.'},
]);s.evaluate();serve(s,args.port)
