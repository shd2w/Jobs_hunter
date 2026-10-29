"""Opt-in all-platform live samples, isolated deadlines and aggregate-only output.

python qa/jobspy_platforms_live.py --output /PRIVATE/platform-verification
Runs up to three independent providers concurrently; no proxies, credentials,
retry loop, job bodies or private workspace reads. Not an offline CI test.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scanners.jobspy_registry import SITES
from scanners.jobspy_scanner import bounded_search
from jobhunter_app.expanded_sources import config

CHILD='''import json,sys
from scanners.jobspy_scanner import JobSpyScanner
from jobhunter_app.validation import normalize_job
search=json.loads(sys.argv[1]); scanner=JobSpyScanner({})
rows=[j.to_dict() for j in scanner._run_search(search)]
valid=[]; invalid=0
for row in rows:
 try: valid.append(normalize_job(row))
 except ValueError: invalid+=1
print('RESULT:'+json.dumps({'received':len(rows),'valid':len(valid),'invalid':invalid,
 'nonempty':{key:sum(bool(r[key]) for r in valid) for key in
 ('title','company','location','description','salary','employment_type','url','date_posted')},
 'errors':scanner.last_errors,'warnings':scanner.last_warnings}))
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--site',action='append',choices=SITES)
    parser.add_argument('--limit',type=int,default=3)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    registry=config()
    def run(site):
        search=bounded_search(registry,site,'Software Engineer',None,max(1,min(10,args.limit)))
        started=time.monotonic()
        result={'site':site,'query':search,'checked_at':datetime.now(timezone.utc).isoformat()}
        try:
            process=subprocess.run([sys.executable,'-c',CHILD,json.dumps(search)],cwd=ROOT,
                capture_output=True,text=True,timeout=150)
            markers=[line[7:] for line in process.stdout.splitlines() if line.startswith('RESULT:')]
            if markers:result.update(json.loads(markers[-1]))
            else:
                last=process.stderr.splitlines()[-1] if process.stderr else 'No provider report'
                result.update(failure='provider_error',detail=last[:500].replace('blocked: use a proxy','blocked; no bypass attempted'))
            result['exit_code']=process.returncode
        except subprocess.TimeoutExpired:
            result.update(failure='wall_timeout',detail='150-second process limit; no success claimed')
        result['seconds']=round(time.monotonic()-started,2)
        return result
    results=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        for result in pool.map(run,list(dict.fromkeys(args.site or SITES))):
            results.append(result)
            (args.output/'results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
            print(result['site'],result.get('valid',0),result.get('failure','completed'),flush=True)
    return int(any(r.get('failure') or r.get('invalid') or r.get('errors') for r in results))

if __name__=='__main__':sys.exit(main())
