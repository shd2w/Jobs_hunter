"""Isolated workflow QA: no source access and fake local delivery only."""
import argparse,sys,os,json
from pathlib import Path
from datetime import date,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from jobhunter_app import network,digests,notifications
from jobhunter_app.store import Store
from jobhunter_app.followups import save
from jobhunter_app.web import serve
p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--port',type=int,default=8776);p.add_argument('--delivery-log',required=True);a=p.parse_args()
os.environ['TELEGRAM_CHAT_ID']='FAKE_QA_DESTINATION';os.environ['TELEGRAM_BOT_TOKEN']='123:FAKE_QA_TOKEN'
def denied(*args,**kwargs):raise AssertionError('QA forbids source/network calls')
network.get=denied;notifications.telegram_send=denied
# This callback writes only synthetic message text to an external QA file.
def fake(text):
 with open(a.delivery_log,'a') as f:f.write(json.dumps({'message':text})+'\n')
 return {'delivered':True,'status':'delivered'}
digests.telegram_digest_send=fake
s=Store(a.db);s.save_profile({'name':'PRIVATE CANDIDATE','skills':['Python'],'facts':[]})
s.ingest([{'title':'Python Engineer','company':'Synthetic Employer','url':'https://example.org/phase5/ui','description':'Python required'},{'title':'Applied Fixture','company':'Synthetic','url':'https://example.org/phase5/applied','description':'Python required'}]);s.evaluate()
for j in s.jobs():
 if j['title']=='Python Engineer':s.set_status(j['id'],'reviewing','PRIVATE APP NOTES',(date.today()-timedelta(days=1)).isoformat());save(s,j['id'],'PRIVATE TASK',date.today().isoformat(),'PRIVATE TASK NOTES')
 else:s.set_status(j['id'],'applied')
serve(s,a.port)
