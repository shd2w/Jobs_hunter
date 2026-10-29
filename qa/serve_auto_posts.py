"""Isolated auto-post UI fixture; every provider request is prohibited."""
import argparse,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from jobhunter_app import network
from jobhunter_app.store import Store
from jobhunter_app.web import serve
for key in list(os.environ):
 if key.startswith(('JOBHUNTER_LINKEDIN_','JOBHUNTER_X_','JOBHUNTER_REDDIT_','JOBHUNTER_DISCORD_','JOBHUNTER_TELEGRAM_')):os.environ.pop(key)
os.environ['JOBHUNTER_POST_MODE']='auto'
def denied(*a,**kw):raise AssertionError('UI fixture prohibits all provider access')
network.get=denied
p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--port',type=int,default=8773);a=p.parse_args()
s=Store(a.db);s.save_profile({'name':'QA','skills':['Python'],'facts':[]});serve(s,a.port)
