"""Disposable aggregate-report fixture. All source/message retrieval denied."""
import argparse,sys,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from jobhunter_app import network,digests
from jobhunter_app.store import Store
from jobhunter_app.followups import save,complete
from jobhunter_app.web import serve
p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--port',type=int,default=8779);args=p.parse_args()
for key in ('TELEGRAM_BOT_TOKEN','TELEGRAM_CHAT_ID'):os.environ.pop(key,None)
def denied(*args,**kw):raise AssertionError('Report QA prohibits external retrieval or delivery')
network.get=denied;digests.telegram_digest_send=denied
s=Store(args.db);s.save_profile({'name':'PRIVATE CANDIDATE','skills':['Python'],'facts':[]})
s.ingest([{'title':'PRIVATE JOB '+str(i),'company':'PRIVATE EMPLOYER','url':f'https://example.org/outcomes/{i}','description':'PRIVATE Python'} for i in range(3)]);s.evaluate();a,b,c=[j['id'] for j in s.jobs()]
s.set_status(a,'offer','PRIVATE APP NOTES','2026-11-02');s.set_status(b,'saved','PRIVATE APP NOTES','2026-11-03')
with s.connect() as db:
 db.execute('DELETE FROM status_history')
 for job,state,stamp in [(a,'applied','2026-11-01T00:00:00Z'),(a,'interview','2026-11-02T00:00:00Z'),(a,'applied','2026-11-02T12:00:00Z'),(b,'applied','2026-11-02T23:00:00-01:00'),(a,'offer','2026-11-04T00:00:00Z')]:db.execute('INSERT INTO status_history(profile_id,job_id,new_status,changed_at) VALUES(?,?,?,?)',('default',job,state,stamp))
save(s,a,'PRIVATE TASK','2026-11-01','PRIVATE NOTES');t=save(s,b,'PRIVATE COMPLETE','2026-11-02');complete(s,t['id']);save(s,b,'PRIVATE OUTSIDE','2026-11-10')
serve(s,args.port)
