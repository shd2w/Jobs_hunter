"""Loopback-only, manually launched local dashboard. No startup or external assets."""
from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import re
from pathlib import Path
import secrets
import sqlite3
from threading import Lock, Thread, Event
from urllib.parse import urlsplit, parse_qs
from .store import STATES

ASSETS = Path(__file__).parent / 'static'


def codespaces_host(port):
    """One exact private forwarding host, only in a genuine Codespaces environment.

    This is not authentication. Keep the Codespaces port private; never expose
    this single-user app as a public service. Forwarded headers are not trusted.
    """
    name = os.environ.get('CODESPACE_NAME', '')
    domain = os.environ.get('GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN', '')
    if (os.environ.get('CODESPACES') != 'true' or domain != 'app.github.dev'
            or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name)
            or len(name) > 100 or type(port) is not int or not 1 <= port <= 65535):
        return None
    return f'{name}-{port}.{domain}'


def make_server(store, port=8765, profile_id='default'):
    token = secrets.token_urlsafe(32)
    task_lock = Lock()
    task = {'running': False, 'result': None, 'error': None}
    cancel = Event()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.0'
        def log_message(self, *args):
            pass  # No candidate URLs, notes or request bodies in access logs.

        def host_ok(self):
            host = self.headers.get('Host', '')
            allowed = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
            forwarded = codespaces_host(self.server.server_port)
            if forwarded:
                allowed.add(forwarded)
            return host in allowed

        def send(self, status, data, content_type='application/json; charset=utf-8', attachment=None):
            if not isinstance(data, bytes):
                data = json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            if attachment:
                self.send_header('Content-Disposition', f'attachment; filename="{attachment}"')
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not self.host_ok():
                return self.send(403, {'error': 'Invalid local Host header'})
            parsed = urlsplit(self.path)
            params = parse_qs(parsed.query)
            path = parsed.path
            try:
                if path == '/':
                    html = (ASSETS / 'index.html').read_text(encoding='utf-8').replace('__CSRF__', token)
                    return self.send(200, html.encode(), 'text/html; charset=utf-8')
                if path in ('/app.js', '/discovery.js', '/workflow.js', '/calendar.js', '/searches.js', '/outcomes.js', '/packs.js', '/learning.js', '/learning-progress.js', '/evidence-mapping.js', '/style.css'):
                    return self.send(200, (ASSETS / path[1:]).read_bytes(), 'application/javascript' if path.endswith('.js') else 'text/css')
                if path in ('/api/packs','/api/pack-inspect'):
                    from .pack_management import list_packs, inspect_pack
                    root = store.path.parent / 'preparation-packs'
                    if path == '/api/packs':
                        return self.send(200, list_packs(store, root, profile_id, params.get('job_id',[''])[0], int(params.get('offset',['0'])[0])))
                    return self.send(200, inspect_pack(store, root, params.get('id',[''])[0], profile_id))
                if path == '/api/source-directory':
                    from .source_directory import directory
                    return self.send(200,directory(params.get('q',[''])[0]))
                if path == '/api/source-health':
                    from .source_health import health
                    return self.send(200,health(store))
                if path == '/api/source-catalog':
                    from .sources import catalog
                    return self.send(200, catalog())
                if path == '/api/posts':
                    from .posts import listing
                    return self.send(200, listing(store, params.get('status', ['pending'])[0], int(params.get('offset', ['0'])[0])))
                if path == '/api/post':
                    from .posts import detail
                    return self.send(200, detail(store, params.get('id', [''])[0]))
                if path == '/api/origins':
                    from .posts import origins
                    return self.send(200, origins(store, params.get('id', [''])[0]))
                if path == '/api/saved-searches':
                    from .saved_searches import listing
                    return self.send(200,listing(store,profile_id))
                if path == '/api/saved-search-run':
                    from .saved_searches import run
                    return self.send(200,run(store,params.get('id',[''])[0],profile_id,int(params.get('offset',['0'])[0])))
                if path == '/api/workflow-settings':
                    from .workflow import settings
                    return self.send(200,settings(store,profile_id))
                if path in ('/api/outcome-report','/api/outcome-export'):
                    from .outcomes import report,export
                    start=params.get('start',[None])[0];end=params.get('end',[None])[0]
                    if path=='/api/outcome-report':return self.send(200,report(store,profile_id,start,end))
                    format=params.get('format',['json'])[0]
                    content=export(store,profile_id,start,end,format)
                    return self.send(200,content,'text/csv; charset=utf-8' if format=='csv' else 'application/json; charset=utf-8','jobhunter-outcomes.'+format)
                if path == '/api/workflow-report':
                    from .workflow import report
                    return self.send(200,report(store,profile_id))
                if path in ('/api/calendar-preview','/api/calendar-export'):
                    from .calendar_export import preview,export
                    detail=params.get('details',['0'])[0]
                    if detail not in ('0','1'):raise ValueError('Invalid calendar detail option')
                    options=(store,profile_id,params.get('start',[None])[0],int(params.get('days',['30'])[0]),int(params.get('past_days',['0'])[0]),detail=='1')
                    if path=='/api/calendar-preview':return self.send(200,preview(*options))
                    fingerprint=params.get('fingerprint',[''])[0]
                    if not fingerprint:raise ValueError('Preview the current calendar before downloading')
                    content,_=export(*options,fingerprint=fingerprint)
                    return self.send(200,content,'text/calendar; charset=utf-8','jobhunter-reminders.ics')
                if path == '/api/inbox':
                    from .followups import digest
                    return self.send(200,digest(store,profile_id,days=int(params.get('days',['7'])[0]),offset=int(params.get('offset',['0'])[0]),include_completed=params.get('completed',['0'])[0]=='1'))
                if path == '/api/digest-preview':
                    from .digests import preview
                    return self.send(200,preview(store,profile_id))
                if path == '/api/summary':
                    return self.send(200, {**store.summary(profile_id), 'states': STATES})
                if path == '/api/jobs':
                    return self.send(200, store.jobs(params.get('q', [''])[0], params.get('status', [''])[0], profile_id,
                                                    offset=int(params.get('offset', ['0'])[0])))
                if path == '/api/profile':
                    # Original filesystem path is set only via trusted CLI.
                    profile = store.profile(profile_id)
                    return self.send(200, {k: v for k, v in profile.items() if k != 'original_cv'})
                if path == '/api/cover-evidence':
                    from .evidence_mapping import preview
                    return self.send(200,preview(store.job(params.get('id',[''])[0]),store.profile(profile_id)))
                if path == '/api/learning-progress':
                    from .learning_progress import listing
                    return self.send(200,listing(store,profile_id))
                if path == '/api/learning':
                    return self.send(200, store.learning(profile_id))
                if path == '/api/task':
                    with task_lock:
                        return self.send(200, dict(task))
                if path == '/api/history':
                    with store.connect() as db:
                        rows = [dict(r) for r in db.execute('SELECT old_status,new_status,changed_at FROM status_history WHERE profile_id=? AND job_id=? ORDER BY id DESC',
                                                           (profile_id, params.get('id', [''])[0]))]
                    return self.send(200, rows)
                if path == '/api/export':
                    from .intake import export_jobs
                    format = params.get('format', ['json'])[0]
                    if format not in ('json', 'csv'):
                        raise ValueError('Use the CLI for optional Excel exports')
                    data = export_jobs(store, format, profile_id)
                    return self.send(200, data, 'text/csv; charset=utf-8' if format == 'csv' else 'application/json', f'jobhunter.{format}')
                return self.send(404, {'error': 'Not found'})
            except (ValueError, KeyError, TypeError) as exc:
                return self.send(400, {'error': str(exc)[:200]})
            except Exception:
                return self.send(500, {'error': 'Local operation failed; no sensitive details were logged'})

        def do_POST(self):
            if not self.host_ok() or not secrets.compare_digest(self.headers.get('X-JobHunter-Token', ''), token):
                return self.send(403, {'error': 'Invalid local request token'})
            origin = self.headers.get('Origin')
            allowed = {f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'}
            forwarded = codespaces_host(self.server.server_port)
            if forwarded:
                allowed.add('https://' + forwarded)
            if origin and origin not in allowed:
                return self.send(403, {'error': 'Cross-origin requests are not allowed'})
            if self.headers.get_content_type() != 'application/json':
                return self.send(415, {'error': 'JSON required'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 10 * 1024 * 1024:
                    return self.send(413, {'error': 'Request must be at most 10 MiB'})
                self.connection.settimeout(10)
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError('Expected request object')
                path = urlsplit(self.path).path
                if path == '/api/posts/preview':
                    from .posts import process
                    result = process(store, data.get('posts'), dry_run=True,profile_id=profile_id)
                elif path == '/api/posts/stage':
                    from .posts import process
                    result = process(store, data.get('posts'), data.get('rights_attested'),profile_id=profile_id)
                elif path == '/api/posts/accept':
                    from .posts import accept
                    result = accept(store, data.get('id'), data.get('fields'), data.get('confirmed'), data.get('target_job_id', ''))
                elif path == '/api/posts/dismiss':
                    from .posts import dismiss
                    result = dismiss(store, data.get('id'))
                elif path == '/api/feed-import':
                    from .feeds import ingest
                    result = ingest(store, data.get('content'), data.get('rights_attested'), dry_run=data.get('dry_run') is True,auto_add=True,profile_id=profile_id)
                elif path == '/api/source':
                    from .sources import register
                    result = {'source': register(store, data.get('kind'), data.get('identifier'), data.get('approved') is True)}
                elif path == '/api/import':
                    rows = data.get('jobs')
                    from .pipeline import import_records
                    result = import_records(store, rows, profile_id, data.get('dry_run') is True, source='dashboard-import')
                elif path == '/api/profile':
                    profile = data.get('profile')
                    if not isinstance(profile, dict):
                        raise ValueError('Expected profile object')
                    if 'original_cv' in profile:
                        raise ValueError('Configure original CV paths through the CLI only')
                    prior = store.profile(profile_id)
                    if prior.get('original_cv'):
                        profile['original_cv'] = prior['original_cv']
                    store.save_profile(profile, profile_id)
                    result = {'saved': True}
                elif path == '/api/learning-save':
                    from .learning_progress import create
                    result=create(store,data.get('skill'),data.get('preview_fingerprint'),profile_id)
                elif path == '/api/learning-update':
                    from .learning_progress import update
                    result=update(store,data.get('id'),data.get('progress'),data.get('revision'),profile_id)
                elif path == '/api/learning-delete':
                    from .learning_progress import delete
                    result=delete(store,data.get('id'),data.get('revision'),data.get('confirmed'),profile_id)
                elif path == '/api/saved-search':
                    from .saved_searches import save
                    result=save(store,data.get('search'),profile_id,data.get('id'))
                elif path == '/api/saved-search-delete':
                    from .saved_searches import delete
                    if data.get('confirmed') is not True:raise ValueError('Confirm saved search deletion')
                    result=delete(store,data.get('id'),profile_id)
                elif path == '/api/workflow-settings':
                    from .workflow import settings
                    if not isinstance(data.get('settings'),dict):raise ValueError('Expected workflow settings object')
                    result=settings(store,profile_id,data['settings'])
                elif path == '/api/followup':
                    from .followups import save
                    result=save(store,data.get('job_id'),data.get('title'),data.get('due'),data.get('notes',''),profile_id,data.get('id'))
                elif path == '/api/followup-complete':
                    from .followups import complete
                    result=complete(store,data.get('id'),data.get('completed'),profile_id)
                elif path == '/api/digest-send':
                    from .digests import send
                    result=send(store,data.get('fingerprint'),data.get('confirmed'),profile_id)
                elif path == '/api/match':
                    result = store.evaluate(profile_id)
                elif path == '/api/status':
                    store.set_status(data['id'], data['status'], data.get('notes', ''), data.get('deadline', ''), profile_id)
                    result = {'saved': True}
                elif path == '/api/pack':
                    if 'evidence_mapping' in data and not isinstance(data['evidence_mapping'],dict):raise ValueError('Expected an evidence map object')
                    from .documents import prepare_pack
                    result = prepare_pack(store, data['id'], store.path.parent / 'preparation-packs', profile_id, data.get('evidence_mapping'))
                elif path == '/api/pack-review':
                    from .pack_management import review_pack
                    result = review_pack(store, store.path.parent / 'preparation-packs', data.get('id'),
                                         data.get('decision'), data.get('fingerprint'), data.get('confirmed'),
                                         data.get('checks'), profile_id)
                elif path == '/api/backup':
                    from datetime import datetime, timezone
                    name = 'backup-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-') + secrets.token_hex(3) + '.sqlite3'
                    result = {'backup': store.backup(store.path.parent / 'backups' / name)}
                elif path == '/api/source-reset':
                    from .source_health import reset
                    result = reset(store,data.get('source_id'))
                elif path in ('/api/scan', '/api/scan-batch'):
                    from .sources import scan
                    with task_lock:
                        if task['running']:
                            return self.send(409, {'error': 'A manual scan is already running'})
                        task.update(running=True, result=None, error=None)
                        cancel.clear()
                    source_id = data.get('source_id')
                    ids = data.get('source_ids')
                    is_batch = path == '/api/scan-batch'
                    if (not is_batch and not isinstance(source_id,str)) or (is_batch and (not isinstance(ids,list) or not 1<=len(ids)<=10 or any(not isinstance(x,str) for x in ids) or len(set(ids))!=len(ids))):
                        with task_lock:
                            task['running'] = False
                        raise ValueError('Source id required')
                    def run():
                        try:
                            if is_batch:
                                from .source_health import batch
                                result = batch(store,ids,cancel_event=cancel,profile_id=profile_id)
                            else:
                                result = scan(store, source_id, cancel_event=cancel,profile_id=profile_id)
                            with task_lock:
                                task['result'] = result
                        except Exception as exc:
                            with task_lock:
                                task['error'] = str(exc)[:200]
                        finally:
                            with task_lock:
                                task['running'] = False
                    Thread(target=run, daemon=True).start()
                    result = {'started': True}
                elif path == '/api/stop':
                    cancel.set()
                    result = {'stop_requested': True, 'notice': 'In-flight HTTP request may take up to its timeout; no import after cancellation.'}
                else:
                    return self.send(404, {'error': 'Not found'})
                return self.send(200, result)
            except (ValueError, KeyError, TypeError, UnicodeError, sqlite3.IntegrityError) as exc:
                return self.send(400, {'error': str(exc)[:200]})
            except Exception:
                return self.send(500, {'error': 'Local operation failed; no sensitive details were logged'})

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    return server


def serve(store, port=8765, profile_id='default'):
    if not store.profile(profile_id):
        store.save_profile({'name': '', 'skills': [], 'facts': []}, profile_id)
    server = make_server(store, port, profile_id)
    print(f'JobHunter dashboard: http://127.0.0.1:{server.server_port} (manual session; Ctrl+C to stop)')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
