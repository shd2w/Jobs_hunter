"""Opt-in local real qualification. Synthetic profile, bounded child process, no claims from mocks."""
from pathlib import Path
import argparse,json,subprocess,sys,tempfile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true',help='Permit real public collection, not paid/search API calls')
    parser.add_argument('--provider',choices=('indeed','linkedin'),default='indeed')
    parser.add_argument('--attempts',type=int,default=2)
    parser.add_argument('--state',type=Path,help='Reuse an existing qualification database; gates are never reset')
    parser.add_argument('--inspect-public-links',action='store_true')
    parser.add_argument('--child',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not args.live: parser.error('Explicit --live required')
    args.output.mkdir(parents=True,exist_ok=True)
    if args.child:
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
        from jobhunter_app.store import Store
        from jobhunter_app.discovery_run import run
        # No source URL/company/exact query supplied. This is not the user's real candidate profile.
        store=Store(args.state or args.output/'synthetic.sqlite3')
        store.save_profile({'skills':['Python','SQL'],'matching':{'preferred_title_terms':['backend']}})
        result=run(store,regions=['Germany'],languages=['en'],max_attempts=args.attempts,seconds=60,
                   providers=[args.provider],project=False,approve_public_ats=False,inspect_links=args.inspect_public_links)
        (args.output/'run.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        return 0
    try:
        with (args.output/'process.log').open('w',encoding='utf-8') as log:
            result=subprocess.run([sys.executable,__file__,'--live','--child','--output',str(args.output.resolve()),'--provider',args.provider,'--attempts',str(args.attempts)]+(['--state',str(args.state.resolve())] if args.state else [])+(['--inspect-public-links'] if args.inspect_public_links else []),
                                  stdout=log,stderr=subprocess.STDOUT,timeout=120)
        status='finished' if result.returncode==0 else 'process_failed'
    except subprocess.TimeoutExpired:
        status='hard_timeout'
    receipt={'process_status':status,'hard_timeout_seconds':120,'scope':f'{args.provider} generated scope plus independent eligible work, at most {args.attempts} adapter attempts',
             'access_policy':'New sources require separate approval; no external permission inferred.',
             'qualification':'Inspect run.json and actual persisted source outcomes. Process success is not discovery success; no coverage gain adjudicated.'}
    (args.output/'qualification.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt))
    return 0 if status=='finished' else 1


if __name__=='__main__': raise SystemExit(main())
