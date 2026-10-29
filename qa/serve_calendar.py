"""Isolated calendar UI fixture. Every external fetch/delivery is prohibited."""
import argparse,sys,os
from pathlib import Path
from datetime import date,timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from jobhunter_app import network,digests
from jobhunter_app.store import Store
from jobhunter_app.followups import save,complete
from jobhunter_app.web import serve
p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--port',type=int,default=8777);a=p.parse_args()
for key in ('TELEGRAM_BOT_TOKEN','TELEGRAM_CHAT_ID'):os.environ.pop(key,None)
def denied(*args,**kwargs):raise AssertionError('Calendar QA prohibits external requests')
network.get=denied;digests.telegram_digest_send=denied
s=Store(a.db);s.save_profile({'name':'PRIVATE CANDIDATE','skills':['Python'],'facts':[]})
s.ingest([{'title':'Python Engineer <img src=x onerror=window.BAD_CALENDAR=true>','company':'Fixture Employer','url':'https://example.org/calendar/ui','description':'Python required'}]);s.evaluate();job=s.jobs()[0]
s.set_status(job['id'],'reviewing','PRIVATE APPLICATION NOTES',(date.today()+timedelta(days=1)).isoformat())
save(s,job['id'],'PRIVATE TASK',date.today().isoformat(),'PRIVATE TASK NOTES')
save(s,job['id'],'PRIVATE OLD TASK',(date.today()-timedelta(days=1)).isoformat(),'PRIVATE OLD NOTES')
task=save(s,job['id'],'PRIVATE COMPLETED',date.today().isoformat());complete(s,task['id'])
serve(s,a.port)
