"""Opt-in real collection acceptance. Never run in offline CI.

Examples:
 python qa/scraper_live.py --source arbeitnow:de --source remoteok:remote --output /PRIVATE/results
 python qa/scraper_live.py --jobspy-site indeed --location Egypt --output /PRIVATE/regional

Full payloads stay only in the selected private SQLite database. The JSON report
contains aggregate field counts, errors and repeat-ingest results, not vacancies.
Use a separate workspace, not a production database or a quota-reset workaround.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jobhunter_app.store import Store
from jobhunter_app.sources import register, scan
from jobhunter_app.validation import normalize_job
from scanners.jobspy_registry import SITES


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',action='append',default=[])
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--jobspy-site',choices=SITES)
    parser.add_argument('--location',default=None)
    parser.add_argument('--term',default='Software Engineer')
    parser.add_argument('--limit',type=int,default=3)
    args=parser.parse_args()
    if not args.source and not args.jobspy_site:parser.error('Choose a source or JobSpy site')
    args.output.mkdir(parents=True,exist_ok=True)
    store=Store(args.output/'live.sqlite3');reports=[]
    for label in args.source+([f'jobspy-{args.jobspy_site}:{args.location}'] if args.jobspy_site else []):
        report={'source':label,'checked_at':datetime.now(timezone.utc).isoformat()}
        try:
            if label.startswith('jobspy-'):
                from scanners.jobspy_scanner import JobSpyScanner, bounded_search
                from jobhunter_app.expanded_sources import config
                selected=bounded_search(config(),args.jobspy_site,args.term,args.location,max(1,min(30,args.limit)))
                report['query']=selected
                scanner=JobSpyScanner({})
                rows=[j.to_dict() for j in scanner._run_search(selected)]
                report['metrics']={'provider_errors':scanner.last_errors,'provider_warnings':scanner.last_warnings}
                report['intake']=store.ingest(rows,source='live-jobspy')
            else:
                kind,identifier=label.split(':',1)
                identity=register(store,kind,identifier,True)
                report['metrics']=scan(store,identity)
                with store.connect() as db:
                    rows=[json.loads(x[0]) for x in db.execute('SELECT j.data FROM jobs j JOIN sightings s ON s.job_id=j.id WHERE s.source=?',(identity,))]
            valid=[];invalid=[]
            for i,row in enumerate(rows):
                try:valid.append(normalize_job(row))
                except ValueError as exc:invalid.append({'row':i+1,'error':str(exc)})
            report.update(received=len(rows),valid=len(valid),invalid=invalid,
                nonempty={key:sum(bool(j[key]) for j in valid) for key in
                    ('title','company','location','description','salary','employment_type','url','date_posted')},
                repeat_ingest=store.ingest(rows,source='live-dedup-verification'))
        except Exception as exc:
            report.update(error_type=type(exc).__name__,error=str(exc))
        reports.append(report)
        (args.output/'result.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2))
    print(json.dumps(reports,ensure_ascii=False,indent=2))
    return int(any('error_type' in r for r in reports))

if __name__=='__main__':sys.exit(main())
