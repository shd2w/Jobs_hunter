"""Repeatable canonical-URL contribution demonstration. Synthetic, not live coverage/relevance."""
from pathlib import Path
import json,sys,tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from jobhunter_app.store import Store
from jobhunter_app.sources import register,scan
from jobhunter_app.collection import Collection
with tempfile.TemporaryDirectory() as td:
 s=Store(Path(td)/'coverage.db');result=[]
 fixtures=[('greenhouse','example',{'jobs':[{'title':'Python Engineer','absolute_url':'https://example.org/job/1'}]}),('jobicy','remote',Collection({'jobs':[{'jobTitle':'Python Engineer','companyName':'Example','url':'https://example.org/job/1'},{'jobTitle':'Analyst','companyName':'Example','url':'https://example.org/job/2'}]},{'complete':True},{'coverage_complete':True,'requests':1})),('arbeitnow','de',Collection({'data':[{'title':'Analyst','company_name':'Example','url':'https://example.org/job/2'},{'title':'Engineer','company_name':'Example','url':'https://example.org/job/3'}]},{'complete':True},{'coverage_complete':True,'requests':1}))]
 for kind,identifier,payload in fixtures:
  identity=register(s,kind,identifier,True);r=scan(s,identity,transport=lambda source,payload=payload:payload);result.append({'source':kind,'received':r['received'],'valid':r['valid_records'],'new_canonical_records':r['new_unique_jobs'],'existing_observations':r['existing_job_observations']})
 print(json.dumps({'type':'synthetic URL identity/contribution demonstration','providers_contacted':0,'relevance_evaluated':False,'distinct_employer_vacancies_verified':False,'rows':result,'total_canonical_records':s.summary()['total_jobs'],'limitations':'Same canonical URL only; syndication at different URLs can remain separate until human linking. No live volume, recall, suitability or regional coverage measured.'},indent=2))
