"""Source UI fixture server. All provider network access is replaced and denied by default."""
from pathlib import Path
import argparse,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from jobhunter_app.store import Store
from jobhunter_app.web import serve
from jobhunter_app import network
p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--port',type=int,default=8767);args=p.parse_args()
def fixture_get(url,*a,**kw):
    if not url.startswith('https://jobicy.com/api/jobs?'): raise ValueError('Fixture denies all other provider requests')
    return json.dumps({'jobs':[{'id':1,'jobTitle':'Synthetic Python Engineer','companyName':'UI Fixture Only','url':'https://example.org/jobs/source-ui','jobDescription':'Python fixture only','jobGeo':'Europe'}],'hasMore':False,'nextCursor':None}).encode(),'application/json'
network.get=fixture_get
store=Store(args.db);store.save_profile({'name':'Synthetic QA','skills':['Python'],'facts':[]});serve(store,args.port)
