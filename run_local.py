"""Private JobHunter CLI with automatic discovery on server startup. No cloud account needed for core workflows."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import sqlite3
from jobhunter_app.store import Store, SCHEMA_VERSION
from jobhunter_app.intake import read_jobs, export_jobs
from jobhunter_app.files import publish_new


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default='data/jobhunter.sqlite3')
    parser.add_argument('--profile-id', default='default')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('init')
    p = sub.add_parser('profile'); p.add_argument('file', type=Path)
    p = sub.add_parser('import'); p.add_argument('file', type=Path); p.add_argument('--dry-run', action='store_true'); p.add_argument('--with-state', action='store_true')
    p = sub.add_parser('migrate'); p.add_argument('directory', type=Path); p.add_argument('--apply', action='store_true'); p.add_argument('--allow-partial', action='store_true')
    sub.add_parser('match')
    sub.add_parser('semantic-status')
    p = sub.add_parser('semantic-rank'); p.add_argument('--model-dir',required=True,type=Path); p.add_argument('--limit',type=int,default=50); p.add_argument('--threads',type=int,default=2); p.add_argument('--cache',type=Path); p.add_argument('--output',type=Path)
    sub.add_parser('summary')
    sub.add_parser('learning')
    sub.add_parser('learning-progress')
    p=sub.add_parser('learning-save');p.add_argument('skill');p.add_argument('--preview-fingerprint',required=True)
    p=sub.add_parser('learning-update');p.add_argument('id');p.add_argument('--revision',required=True,type=int);p.add_argument('--status',required=True,choices=['planned','in_progress','paused','completed']);p.add_argument('--notes');p.add_argument('--completed-attested',action='store_true')
    p=sub.add_parser('learning-delete');p.add_argument('id');p.add_argument('--revision',required=True,type=int);p.add_argument('--confirm',required=True,action='store_true')
    for command in ('outcome-report','outcome-export'):
        p=sub.add_parser(command);p.add_argument('--start');p.add_argument('--end')
        if command=='outcome-export':p.add_argument('file',type=Path);p.add_argument('--format',choices=['json','csv'],default='json')
    sub.add_parser('saved-searches')
    p=sub.add_parser('saved-search-save');p.add_argument('name');p.add_argument('--query',default='');p.add_argument('--status',default='');p.add_argument('--id')
    p=sub.add_parser('saved-search-delete');p.add_argument('id');p.add_argument('--confirm',action='store_true',required=True)
    p=sub.add_parser('saved-search-run');p.add_argument('id');p.add_argument('--offset',type=int,default=0)
    for command in ('calendar-preview','calendar-export'):
        p=sub.add_parser(command)
        if command=='calendar-export':
            p.add_argument('file',type=Path); p.add_argument('--preview-fingerprint')
        p.add_argument('--start'); p.add_argument('--days',type=int,default=30); p.add_argument('--past-days',type=int,default=0); p.add_argument('--include-job-details',action='store_true')
    p = sub.add_parser('inbox'); p.add_argument('--today'); p.add_argument('--days',type=int,default=7); p.add_argument('--offset',type=int,default=0); p.add_argument('--include-completed',action='store_true')
    p = sub.add_parser('followup-add'); p.add_argument('job_id'); p.add_argument('title'); p.add_argument('due'); p.add_argument('--notes',default=''); p.add_argument('--id')
    p = sub.add_parser('followup-done'); p.add_argument('id'); p.add_argument('--reopen',action='store_true')
    p = sub.add_parser('workflow-settings'); p.add_argument('file',type=Path,nargs='?')
    p = sub.add_parser('workflow-report'); p.add_argument('--today')
    p = sub.add_parser('digest-preview'); p.add_argument('--today')
    p = sub.add_parser('digest-send'); p.add_argument('--confirm',required=True)
    p = sub.add_parser('notify'); p.add_argument('--threshold', type=float, default=60)
    p = sub.add_parser('list'); p.add_argument('--query', default=''); p.add_argument('--status', default='')
    p = sub.add_parser('status'); p.add_argument('job_id'); p.add_argument('state'); p.add_argument('--notes', default=''); p.add_argument('--deadline', default='')
    p = sub.add_parser('source'); p.add_argument('kind', choices=__import__('jobhunter_app.sources',fromlist=['POLICIES']).POLICIES); p.add_argument('identifier'); p.add_argument('--approve', action='store_true')
    p = sub.add_parser('posts-import'); p.add_argument('file', type=Path); p.add_argument('--rights-attested', action='store_true'); p.add_argument('--dry-run', action='store_true')
    p = sub.add_parser('posts-process'); p.add_argument('file',type=Path); p.add_argument('--rights-attested',action='store_true'); p.add_argument('--dry-run',action='store_true')
    p = sub.add_parser('feed-import'); p.add_argument('file', type=Path); p.add_argument('--rights-attested', action='store_true'); p.add_argument('--dry-run', action='store_true')
    p = sub.add_parser('posts'); p.add_argument('--status', default='pending'); p.add_argument('--offset', type=int, default=0)
    p = sub.add_parser('post'); p.add_argument('id')
    p = sub.add_parser('post-accept'); p.add_argument('id'); p.add_argument('fields', type=Path); p.add_argument('--confirmed', action='store_true'); p.add_argument('--link-job', default='')
    p = sub.add_parser('post-dismiss'); p.add_argument('id')
    sub.add_parser('source-catalog')
    p = sub.add_parser('source-directory'); p.add_argument('--query', default='')
    sub.add_parser('source-health')
    p = sub.add_parser('source-reset'); p.add_argument('source_id')
    p = sub.add_parser('scan-batch'); p.add_argument('source_ids', nargs='+')
    p = sub.add_parser('scan'); p.add_argument('source_id')
    p = sub.add_parser('cover-evidence'); p.add_argument('job_id')
    p = sub.add_parser('pack'); p.add_argument('--evidence-map', type=Path); p.add_argument('job_id'); p.add_argument('--output', type=Path, default=Path('output/packs'))
    p = sub.add_parser('pack-list'); p.add_argument('--job-id', default=''); p.add_argument('--offset', type=int, default=0); p.add_argument('--output', type=Path, default=Path('output/packs'))
    p = sub.add_parser('pack-inspect'); p.add_argument('version_id'); p.add_argument('--output', type=Path, default=Path('output/packs'))
    p = sub.add_parser('pack-review'); p.add_argument('version_id'); p.add_argument('--decision', choices=['reviewed','needs_changes'], required=True); p.add_argument('--fingerprint', required=True); p.add_argument('--confirm', action='store_true', help='Confirm facts, target, CV selection/absence and manual-only submission'); p.add_argument('--output', type=Path, default=Path('output/packs'))

    p = sub.add_parser('export'); p.add_argument('file', type=Path); p.add_argument('--format', choices=['json', 'csv', 'xlsx'], default='json')
    p = sub.add_parser('history'); p.add_argument('--job-id', default=''); p.add_argument('--offset', type=int, default=0)
    p = sub.add_parser('history-export'); p.add_argument('file', type=Path)
    p = sub.add_parser('export-uaa'); p.add_argument('file', type=Path); p.add_argument('--threshold', type=float, default=3.5); p.add_argument('--candidate-profile', type=Path)
    p = sub.add_parser('restore'); p.add_argument('backup', type=Path); p.add_argument('destination', type=Path)
    p = sub.add_parser('backup'); p.add_argument('file', type=Path)
    p = sub.add_parser('serve'); p.add_argument('--port', type=int, default=8765); p.add_argument('--manual-discovery', action='store_true', help='Disable automatic discovery for offline/testing sessions')
    args = parser.parse_args(argv)
    try:
        if args.command == 'semantic-status':
            from jobhunter_app.semantic import status
            print(json.dumps(status(),indent=2))
            return 0
        if args.command == 'restore':
            from jobhunter_app.migration import restore_backup
            print(json.dumps(restore_backup(args.backup, args.destination), indent=2))
            return 0
        store = Store(args.db)
        pid = args.profile_id
        if args.command == 'init':
            if not store.profile(pid):
                store.save_profile({'name': '', 'skills': [], 'facts': []}, pid)
            result = {'database': str(store.path), 'schema': SCHEMA_VERSION, 'profile_id': pid}
        elif args.command == 'profile':
            store.save_profile(json.loads(args.file.read_text(encoding='utf-8')), pid)
            result = {'saved': pid}
        elif args.command == 'import':
            from jobhunter_app.pipeline import import_records
            result = import_records(store, read_jobs(args.file), pid, args.dry_run, args.with_state)
        elif args.command == 'migrate':
            from jobhunter_app.migration import migrate
            result = migrate(store, args.directory, dry_run=not args.apply, profile_id=pid, allow_partial=args.allow_partial)
        elif args.command == 'match':
            result = store.evaluate(pid)
        elif args.command == 'semantic-rank':
            from jobhunter_app.semantic import rank
            if args.output and args.output.exists(): raise ValueError('Semantic output must use a new filename')
            result=rank(store,args.model_dir,pid,args.limit,args.threads,args.cache)
            if args.output:
                publish_new(args.output,json.dumps(result,ensure_ascii=False,indent=2).encode('utf-8'))
        elif args.command == 'summary':
            result = store.summary(pid)
        elif args.command in ('outcome-report','outcome-export'):
            from jobhunter_app.outcomes import report,export
            if args.command=='outcome-report':result=report(store,pid,args.start,args.end)
            else:
                content=export(store,pid,args.start,args.end,args.format);publish_new(args.file,content);result={'exported_to':str(args.file),'bytes':len(content),'format':args.format}
        elif args.command.startswith('saved-search'):
            from jobhunter_app.saved_searches import listing,save,delete,run
            if args.command=='saved-searches':result=listing(store,pid)
            elif args.command=='saved-search-save':result=save(store,{'name':args.name,'query':args.query,'status':args.status},pid,args.id)
            elif args.command=='saved-search-delete':result=delete(store,args.id,pid)
            else:result=run(store,args.id,pid,args.offset)
        elif args.command in ('learning-progress','learning-save','learning-update','learning-delete'):
            from jobhunter_app.learning_progress import listing,create,update,delete
            if args.command=='learning-progress':result=listing(store,pid)
            elif args.command=='learning-save':result=create(store,args.skill,args.preview_fingerprint,pid)
            elif args.command=='learning-update':
                notes=args.notes if args.notes is not None else next((x['notes'] for x in listing(store,pid)['items'] if x['id']==args.id),'')
                result=update(store,args.id,{'status':args.status,'notes':notes,'completed_attested':args.completed_attested},args.revision,pid)
            else:result=delete(store,args.id,args.revision,args.confirm,pid)
        elif args.command == 'learning':
            result = store.learning(pid)
        elif args.command in ('calendar-preview','calendar-export'):
            from jobhunter_app.calendar_export import preview,export
            if args.command=='calendar-preview':result=preview(store,pid,args.start,args.days,args.past_days,args.include_job_details)
            else:
                content,metadata=export(store,pid,args.start,args.days,args.past_days,args.include_job_details,args.preview_fingerprint)
                publish_new(args.file,content)
                result={'exported_to':str(args.file),'bytes':len(content),'calendar':metadata}
        elif args.command == 'inbox':
            from jobhunter_app.followups import digest
            result=digest(store,pid,args.today,args.days,args.offset,include_completed=args.include_completed)
        elif args.command == 'followup-add':
            from jobhunter_app.followups import save
            result=save(store,args.job_id,args.title,args.due,args.notes,pid,args.id)
        elif args.command == 'followup-done':
            from jobhunter_app.followups import complete
            result=complete(store,args.id,not args.reopen,pid)
        elif args.command == 'workflow-settings':
            from jobhunter_app.workflow import settings
            result=settings(store,pid,json.loads(args.file.read_text(encoding='utf-8')) if args.file else None)
        elif args.command == 'workflow-report':
            from jobhunter_app.workflow import report
            result=report(store,pid,args.today)
        elif args.command == 'digest-preview':
            from jobhunter_app.digests import preview
            result=preview(store,pid,args.today)
        elif args.command == 'digest-send':
            from jobhunter_app.digests import send
            result=send(store,args.confirm,True,pid)
        elif args.command == 'notify':
            from jobhunter_app.notifications import notify
            result = notify(store, args.threshold, pid)
        elif args.command == 'list':
            result = store.jobs(query=args.query, status=args.status, profile_id=pid)
        elif args.command == 'status':
            store.set_status(args.job_id, args.state, args.notes, args.deadline, pid)
            result = {'updated': args.job_id, 'status': args.state}
        elif args.command == 'source':
            from jobhunter_app.sources import register
            result = {'source': register(store, args.kind, args.identifier, args.approve), 'approved': args.approve}
        elif args.command == 'source-directory':
            from jobhunter_app.source_directory import directory
            result = directory(args.query)
        elif args.command == 'source-health':
            from jobhunter_app.source_health import health
            result = health(store)
        elif args.command == 'source-reset':
            from jobhunter_app.source_health import reset
            result = reset(store,args.source_id)
        elif args.command == 'scan-batch':
            from jobhunter_app.source_health import batch
            result = batch(store,args.source_ids,profile_id=pid)
        elif args.command == 'source-catalog':
            from jobhunter_app.sources import catalog
            result = catalog()
        elif args.command in ('posts-import', 'posts-process', 'feed-import'):
            if args.command in ('posts-import','posts-process'):
                from jobhunter_app.posts import stage, process
                if args.file.stat().st_size > 5 * 1024 * 1024: raise ValueError('Post import exceeds 5 MiB')
                rows=json.loads(args.file.read_text(encoding='utf-8-sig'))
                result = process(store,rows,args.rights_attested,args.dry_run,profile_id=pid) if args.command=='posts-process' else stage(store,rows,args.rights_attested,args.dry_run)
            else:
                from jobhunter_app.feeds import ingest
                with args.file.open('rb') as stream: content = stream.read(5 * 1024 * 1024 + 1)
                result = ingest(store, content, args.rights_attested, dry_run=args.dry_run)
        elif args.command == 'posts':
            from jobhunter_app.posts import listing
            result = listing(store, args.status, args.offset)
        elif args.command == 'post':
            from jobhunter_app.posts import detail
            result = detail(store, args.id)
        elif args.command == 'post-accept':
            from jobhunter_app.posts import accept
            if args.fields.stat().st_size > 200000: raise ValueError('Review file too large')
            result = accept(store, args.id, json.loads(args.fields.read_text(encoding='utf-8')), args.confirmed, args.link_job)
        elif args.command == 'post-dismiss':
            from jobhunter_app.posts import dismiss
            result = dismiss(store, args.id)
        elif args.command == 'scan':
            from jobhunter_app.sources import scan
            result = scan(store, args.source_id,profile_id=pid)
        elif args.command == 'cover-evidence':
            from jobhunter_app.evidence_mapping import preview
            result=preview(store.job(args.job_id),store.profile(pid))
        elif args.command == 'pack':
            from jobhunter_app.documents import prepare_pack
            from jobhunter_app.evidence_mapping import load as load_evidence_map
            result = prepare_pack(store, args.job_id, args.output, pid, load_evidence_map(args.evidence_map) if args.evidence_map else None)
        elif args.command in ('pack-list','pack-inspect','pack-review'):
            from jobhunter_app.pack_management import list_packs, inspect_pack, review_pack, CHECKS
            if args.command == 'pack-list':
                result = list_packs(store, args.output, pid, args.job_id, args.offset)
            elif args.command == 'pack-inspect':
                result = inspect_pack(store, args.output, args.version_id, pid)
            else:
                result = review_pack(store, args.output, args.version_id, args.decision, args.fingerprint,
                                     args.confirm, {k: args.confirm for k in CHECKS}, pid)
        elif args.command == 'history':
            from jobhunter_app.migration import history
            result = history(store, pid, args.job_id, offset=args.offset)
        elif args.command == 'history-export':
            from jobhunter_app.pipeline import export_history
            content = export_history(store, pid)
            publish_new(args.file, content)
            result = {'exported_to': str(args.file)}
        elif args.command == 'export-uaa':
            from jobhunter_app.pipeline import export_uaa
            result = export_uaa(store, args.file, pid, args.threshold, args.candidate_profile)
        elif args.command == 'export':
            # Avoid accidentally overwriting source files or originals.
            content = export_jobs(store, args.format, pid)
            publish_new(args.file, content)
            result = {'exported_to': str(args.file)}
        elif args.command == 'backup':
            result = {'backup': store.backup(args.file)}
        elif args.command == 'serve':
            from jobhunter_app.web import serve
            serve(store, args.port, pid, automatic=not args.manual_discovery)
            return 0
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except sqlite3.DatabaseError:
        print('Error: Local database operation failed. Preserve the database and any WAL/SHM files. Restore a verified backup to a new filename; no automatic reset was attempted.', file=sys.stderr)
        return 2
    except (ValueError, OSError, KeyError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
