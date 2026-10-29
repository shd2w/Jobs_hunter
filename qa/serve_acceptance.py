"""Empty synthetic workspace for end-to-end UI; no real credentials or delivery."""
import argparse,json,sys,os,socket
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from jobhunter_app import network,digests
from jobhunter_app.store import Store
from jobhunter_app.web import serve
p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--events',required=True);p.add_argument('--port',type=int,default=8780);args=p.parse_args()
for k in list(os.environ):
 if k.startswith(('JOBHUNTER_','TELEGRAM_')):os.environ.pop(k,None)
os.environ['TELEGRAM_BOT_TOKEN']='123:FAKE_ACCEPTANCE_TOKEN';os.environ['TELEGRAM_CHAT_ID']='FAKE_ACCEPTANCE_DESTINATION'
def event(kind,**kw):
 with open(args.events,'a') as f:f.write(json.dumps({'kind':kind,**kw})+'\n')
def fake_get(url,*a,**kw):
 if not url.startswith('https://jobicy.com/api/jobs?'):raise AssertionError('Fixture denies other source requests')
 event('source_fixture')
 return json.dumps({'jobs':[{'id':91,'jobTitle':'Python Integrated Engineer','companyName':'Acceptance Employer','url':'https://example.org/integrated/ui','jobDescription':'Python required','jobGeo':'Cairo'}],'hasMore':False,'nextCursor':None}).encode(),'application/json'
def fake_send(text):
 if any(x in text for x in ('PRIVATE','Acceptance Employer','example.org','Demo Employer')):raise AssertionError('Counts-only message leaked private detail')
 event('fake_delivery',counts_only=True);return {'delivered':True,'status':'delivered'}
network.get=fake_get;digests.telegram_digest_send=fake_send
original=socket.create_connection
def local(address,*a,**kw):
 if address[0] not in ('127.0.0.1','localhost','::1'):raise AssertionError('External connections prohibited')
 return original(address,*a,**kw)
socket.create_connection=local
store=Store(args.db);store.save_profile({'name':'PRIVATE ACCEPTANCE CANDIDATE','skills':['Python'],'facts':[]})
serve(store,args.port)
