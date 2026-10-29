"""Synthetic local review UI only; provider requests prohibited."""
import argparse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from jobhunter_app import network
from jobhunter_app.store import Store
from jobhunter_app.web import serve

def denied(*a,**kw):raise AssertionError('No live source calls in UI QA')
network.get=denied
p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--port',type=int,default=8775);a=p.parse_args()
s=Store(a.db);s.save_profile({'name':'Synthetic QA','skills':['Python'],'facts':[],'matching':{'excluded_companies':['Blocked Fixture']}})
s.ingest([{'title':'Python Engineer','company':'Blocked Fixture','url':'https://example.org/qa/context','location':'Remote in Germany only','description':'Python required\n3 years experience required\nDegree preferred or equivalent experience\nEnglish B2 required\nWork authorization required; no visa sponsorship\nSalary EUR 60000 annually\n<script>window.BAD_INJECTION=true</script> Salary $1000\nعن بعد مع الإقامة في مصر\nDeutsch C1 erforderlich'},
          {'title':'Sparse fixture','company':'Fixture','url':'https://example.org/qa/sparse','description':'No supplied qualification details'},
          {'title':'Truncated fixture','company':'Fixture','url':'https://example.org/qa/long','description':'English required\n'*100}])
s.evaluate();serve(s,a.port)
