"""Transactional local store. One authority for the new application workflow."""
from __future__ import annotations
from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

SCHEMA_VERSION = 5
WORKFLOW_SCHEMA = """
CREATE TABLE followups(id TEXT PRIMARY KEY, profile_id TEXT NOT NULL REFERENCES profiles(id), job_id TEXT NOT NULL REFERENCES jobs(id),
 title TEXT NOT NULL, due TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '', completed INTEGER NOT NULL DEFAULT 0 CHECK(completed IN (0,1)), updated_at TEXT NOT NULL);
CREATE INDEX followups_due ON followups(profile_id,completed,due);
CREATE TABLE workflow_settings(profile_id TEXT PRIMARY KEY REFERENCES profiles(id), data TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE digest_deliveries(profile_id TEXT NOT NULL REFERENCES profiles(id), channel TEXT NOT NULL, fingerprint TEXT NOT NULL, delivered_at TEXT NOT NULL,
 PRIMARY KEY(profile_id,channel,fingerprint));
CREATE TABLE notification_gates(channel TEXT PRIMARY KEY, not_before TEXT NOT NULL);
"""
SOURCE_SCHEMA = """
CREATE TABLE source_checkpoints(source_id TEXT PRIMARY KEY REFERENCES sources(id), data TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE provider_gates(kind TEXT PRIMARY KEY, not_before TEXT NOT NULL);
"""
HISTORY_SCHEMA = """
CREATE TABLE migration_batches(id TEXT PRIMARY KEY, profile_id TEXT NOT NULL REFERENCES profiles(id),
 manifest TEXT NOT NULL, result TEXT NOT NULL, completed_at TEXT NOT NULL);
CREATE TABLE historical_records(id TEXT NOT NULL, profile_id TEXT NOT NULL REFERENCES profiles(id),
 source_file TEXT NOT NULL, source_row INTEGER NOT NULL, kind TEXT NOT NULL,
 job_id TEXT REFERENCES jobs(id), payload TEXT NOT NULL, imported_at TEXT NOT NULL,
 PRIMARY KEY(profile_id,id));
CREATE INDEX history_profile_job ON historical_records(profile_id,job_id);
"""
DISCOVERY_SCHEMA = '''
CREATE TABLE discovery_items(id TEXT PRIMARY KEY, origin_url TEXT NOT NULL, source_label TEXT NOT NULL,
 body TEXT NOT NULL, body_hash TEXT NOT NULL, extracted TEXT NOT NULL, created_at TEXT NOT NULL,
 last_seen TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending');
CREATE TABLE job_origins(job_id TEXT NOT NULL REFERENCES jobs(id), item_id TEXT NOT NULL REFERENCES discovery_items(id),
 review_data TEXT NOT NULL, reviewed_at TEXT NOT NULL, PRIMARY KEY(job_id,item_id));
CREATE TABLE job_aliases(alias_url TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id), created_at TEXT NOT NULL);
CREATE INDEX discovery_status ON discovery_items(status,last_seen DESC);
CREATE INDEX discovery_body ON discovery_items(body_hash);
'''

STATES = ('discovered', 'saved', 'reviewing', 'preparing', 'ready', 'applied',
          'interview', 'offer', 'rejected', 'withdrawn', 'archived')
SCHEMA = '''
CREATE TABLE profiles(id TEXT PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE jobs(id TEXT PRIMARY KEY, url TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
 company TEXT NOT NULL, location TEXT NOT NULL, description TEXT NOT NULL,
 data TEXT NOT NULL, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL);
CREATE TABLE sightings(job_id TEXT NOT NULL REFERENCES jobs(id), source TEXT NOT NULL,
 first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, PRIMARY KEY(job_id,source));
CREATE TABLE matches(profile_id TEXT NOT NULL REFERENCES profiles(id), job_id TEXT NOT NULL REFERENCES jobs(id),
 data TEXT NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY(profile_id,job_id));
CREATE TABLE applications(profile_id TEXT NOT NULL REFERENCES profiles(id), job_id TEXT NOT NULL REFERENCES jobs(id),
 status TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '', deadline TEXT NOT NULL DEFAULT '',
 updated_at TEXT NOT NULL, PRIMARY KEY(profile_id,job_id));
CREATE TABLE status_history(id INTEGER PRIMARY KEY, profile_id TEXT NOT NULL, job_id TEXT NOT NULL,
 old_status TEXT, new_status TEXT NOT NULL, changed_at TEXT NOT NULL,
 FOREIGN KEY(profile_id,job_id) REFERENCES applications(profile_id,job_id));
CREATE TABLE sources(id TEXT PRIMARY KEY, kind TEXT NOT NULL, identifier TEXT NOT NULL,
 approved INTEGER NOT NULL DEFAULT 0, last_run TEXT, last_error TEXT, health TEXT NOT NULL DEFAULT 'untested');
CREATE TABLE runs(id INTEGER PRIMARY KEY, source TEXT NOT NULL, started_at TEXT NOT NULL,
 finished_at TEXT, status TEXT NOT NULL, metrics TEXT NOT NULL DEFAULT '{}');
CREATE TABLE audit(id INTEGER PRIMARY KEY, event TEXT NOT NULL, details TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE notification_deliveries(profile_id TEXT NOT NULL, job_id TEXT NOT NULL, channel TEXT NOT NULL,
 fingerprint TEXT NOT NULL, delivered_at TEXT NOT NULL,
 PRIMARY KEY(profile_id,job_id,channel,fingerprint));
CREATE INDEX jobs_recency ON jobs(last_seen DESC);
CREATE INDEX applications_status ON applications(profile_id,status);
CREATE INDEX history_job ON status_history(profile_id,job_id);
'''


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


class Store:
    def __init__(self, path: str | Path = 'data/jobhunter.sqlite3'):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        from filelock import FileLock
        with FileLock(str(self.path) + '.schema.lock', timeout=30), self.connect() as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version > SCHEMA_VERSION:
                raise ValueError('Database is newer than this application; do not downgrade')
            if version == 0:
                db.executescript('BEGIN IMMEDIATE;\n' + SCHEMA + DISCOVERY_SCHEMA + HISTORY_SCHEMA + SOURCE_SCHEMA + WORKFLOW_SCHEMA + '\nPRAGMA user_version=5;\nCOMMIT;')
            elif version in (1, 2, 3, 4):
                # Snapshot the complete prior database before the transactional upgrade.
                backup = self.path.with_name(self.path.name + f'.pre-v{SCHEMA_VERSION}-' + datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f') + '.bak')
                with sqlite3.connect(backup) as target:
                    db.backup(target)
                db.executescript('BEGIN IMMEDIATE;\n' + (DISCOVERY_SCHEMA if version == 1 else '') + (HISTORY_SCHEMA if version < 3 else '') + (SOURCE_SCHEMA if version < 4 else '') + WORKFLOW_SCHEMA + '\nPRAGMA user_version=5;\nCOMMIT;')

        # Match rows are derived caches, not historical evaluations or application state.
        from .matching import MATCHER_VERSION
        with self.connect() as db:
            stale=db.execute("DELETE FROM matches WHERE json_valid(data) AND json_extract(data,'$.method') LIKE 'deterministic %' AND json_extract(data,'$.method') != ?",(MATCHER_VERSION,)).rowcount
            if stale:self.audit(db,'matcher_cache_invalidated',{'rows':stale,'matcher':MATCHER_VERSION})
        self.recover_interrupted_runs()

    def recover_interrupted_runs(self):
        """Reconcile abandoned run records only while owning the scan lock.

        Existing files do not prove a worker is alive. Conversely, elapsed time
        does not prove a live worker is dead; lock ownership is the deciding gate.
        """
        from filelock import FileLock, Timeout
        try:
            with FileLock(str(self.path) + '.scan.lock', timeout=0), self.connect() as db:
                rows = db.execute("SELECT id,source FROM runs WHERE status='running' ORDER BY id").fetchall()
                message = 'Previous worker ended before recording completion. Review stored results and request another run when due.'
                for row in rows:
                    db.execute('UPDATE runs SET status=?,finished_at=?,metrics=? WHERE id=?',
                               ('interrupted', now(), dump({'error': message, 'recovered_at_startup': True}), row['id']))
                    # Do not overwrite a newer successful check's source health.
                    if not db.execute('SELECT 1 FROM runs WHERE source=? AND id>?', (row['source'], row['id'])).fetchone():
                        db.execute('UPDATE sources SET health=?,last_error=? WHERE id=?',
                                   ('interrupted', message, row['source']))
                if rows:
                    self.audit(db, 'interrupted_runs_recovered', {'run_ids': [r['id'] for r in rows]})
                return len(rows)
        except Timeout:
            return 0  # A worker owns the lock. Never label its live work interrupted.

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('PRAGMA busy_timeout=15000')
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def audit(db, event, details):
        db.execute('INSERT INTO audit(event,details,created_at) VALUES(?,?,?)', (event, dump(details), now()))

    def save_profile(self, profile: dict, profile_id='default'):
        if not isinstance(profile_id, str) or not profile_id or len(profile_id) > 100:
            raise ValueError('Invalid profile id')
        if not isinstance(profile, dict) or len(dump(profile)) > 100000:
            raise ValueError('Invalid profile')
        allowed = {'name', 'skills', 'facts', 'excluded_title_terms', 'original_cv', 'languages', 'matching'}
        if set(profile) - allowed:
            raise ValueError('Unknown profile fields')
        if not isinstance(profile.get('name', ''), str) or len(profile.get('name', '')) > 300:
            raise ValueError('Invalid candidate name')
        for field in ('skills', 'excluded_title_terms', 'languages'):
            values = profile.get(field, [])
            if not isinstance(values, list) or len(values) > 200 or any(not isinstance(x, str) or not x.strip() or len(x) > 200 for x in values):
                raise ValueError(f'Invalid {field}')
        from .match_config import validate
        validate(profile.get('matching',{}),profile.get('skills',[]))
        facts = profile.get('facts', [])
        if not isinstance(facts, list) or len(facts) > 100:
            raise ValueError('Invalid facts')
        for f in facts:
            if not isinstance(f, dict) or not isinstance(f.get('text'), str) or not 1 <= len(f['text']) <= 2000 or type(f.get('verified')) is not bool or not isinstance(f.get('source'), str) or not f['source'].strip():
                raise ValueError('Facts require text, explicit verified boolean and source')
        if not isinstance(profile.get('original_cv', ''), str):
            raise ValueError('Invalid original CV path')
        with self.connect() as db:
            db.execute('INSERT INTO profiles VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at',
                       (profile_id, dump(profile), now()))
            # Stale matches must not survive a profile change.
            db.execute('DELETE FROM matches WHERE profile_id=?', (profile_id,))
            self.audit(db, 'profile_updated', {'profile_id': profile_id})

    def profile(self, profile_id='default') -> dict:
        with self.connect() as db:
            row = db.execute('SELECT data FROM profiles WHERE id=?', (profile_id,)).fetchone()
        return json.loads(row['data']) if row else {}

    def ingest(self, rows: list[dict], source='import', dry_run=False, _db=None) -> dict:
        from .validation import normalize_job
        if not isinstance(rows, list) or len(rows) > 10000:
            raise ValueError('Expected at most 10,000 job objects')
        if not isinstance(source, str) or not source.strip() or len(source) > 100:
            raise ValueError('Invalid source')
        report = {'received': len(rows), 'inserted': 0, 'updated': 0, 'invalid': 0, 'errors': [], 'dry_run': dry_run}
        normalized = []
        for i, row in enumerate(rows):
            try:
                job = normalize_job(row)
                job['source'] = source
                normalized.append((i, job))
            except (ValueError, TypeError) as exc:
                report['invalid'] += 1
                report['errors'].append({'row': i + 1, 'error': str(exc)})
        with (nullcontext(_db) if _db is not None else self.connect()) as db:
            seen = set()
            for _, job in normalized:
                alias = db.execute('SELECT job_id FROM job_aliases WHERE alias_url=?', (job['url'],)).fetchone()
                job_id = alias['job_id'] if alias else sha256(job['url'].encode()).hexdigest()
                if alias:
                    # A human-linked syndicated alias cannot overwrite the authoritative record.
                    job = json.loads(db.execute('SELECT data FROM jobs WHERE id=?', (job_id,)).fetchone()['data'])
                present = job_id in seen or db.execute('SELECT 1 FROM jobs WHERE id=?', (job_id,)).fetchone()
                seen.add(job_id)
                report['updated' if present else 'inserted'] += 1
                if dry_run:
                    continue
                timestamp = now()
                # Partial sightings must not erase richer stored descriptions.
                existing = db.execute('SELECT data FROM jobs WHERE id=?', (job_id,)).fetchone()
                if existing:
                    prior = json.loads(existing['data'])
                    job = {k: v or prior.get(k, '') for k, v in job.items()}
                db.execute('''INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,company=excluded.company,location=excluded.location,
                    description=excluded.description,data=excluded.data,last_seen=excluded.last_seen''',
                    (job_id, job['url'], job['title'], job['company'], job['location'], job['description'], dump(job), timestamp, timestamp))
                db.execute('INSERT INTO sightings VALUES(?,?,?,?) ON CONFLICT(job_id,source) DO UPDATE SET last_seen=excluded.last_seen',
                           (job_id, source, timestamp, timestamp))
                db.execute('DELETE FROM matches WHERE job_id=?', (job_id,))
            if not dry_run:
                self.audit(db, 'ingest', {k: v for k, v in report.items() if k != 'errors'})
        return report

    def jobs(self, query='', status='', profile_id='default', limit=200, offset=0):
        if status and status not in STATES:
            raise ValueError('Unknown application status')
        if not isinstance(query, str) or len(query) > 1000:
            raise ValueError('Invalid query')
        with self.connect() as db:
            rows = db.execute('''SELECT j.*,COALESCE(a.status,'discovered') status,
                COALESCE(a.notes,'') notes,COALESCE(a.deadline,'') deadline,m.data match_data
                FROM jobs j LEFT JOIN applications a ON a.job_id=j.id AND a.profile_id=?
                LEFT JOIN matches m ON m.job_id=j.id AND m.profile_id=?
                WHERE (?='' OR instr(lower(j.title || ' ' || j.company || ' ' || j.description),lower(?))>0)
                AND (?='' OR COALESCE(a.status,'discovered')=?) ORDER BY j.last_seen DESC,j.id LIMIT ? OFFSET ?''',
                (profile_id, profile_id, query, query, status, status, min(max(int(limit), 1), 1000), max(int(offset), 0))).fetchall()
        return [{**json.loads(r['data']), 'id': r['id'], 'first_seen': r['first_seen'], 'last_seen': r['last_seen'],
                 'status': r['status'], 'notes': r['notes'], 'deadline': r['deadline'],
                 'match': json.loads(r['match_data']) if r['match_data'] else None} for r in rows]

    def job(self, job_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not row:
            raise ValueError('Job not found')
        return {**json.loads(row['data']), 'id': row['id']}

    def set_status(self, job_id, status, notes='', deadline='', profile_id='default'):
        if status not in STATES or not isinstance(notes, str) or len(notes) > 20000:
            raise ValueError('Invalid application update')
        if not isinstance(deadline,str): raise ValueError('Invalid deadline')
        if deadline:
            from .followups import calendar_day
            calendar_day(deadline)
        with self.connect() as db:
            old = db.execute('SELECT status FROM applications WHERE profile_id=? AND job_id=?', (profile_id, job_id)).fetchone()
            timestamp = now()
            db.execute('INSERT INTO applications VALUES(?,?,?,?,?,?) ON CONFLICT(profile_id,job_id) DO UPDATE SET status=excluded.status,notes=excluded.notes,deadline=excluded.deadline,updated_at=excluded.updated_at',
                       (profile_id, job_id, status, notes, deadline, timestamp))
            if not old or old['status'] != status:
                db.execute('INSERT INTO status_history(profile_id,job_id,old_status,new_status,changed_at) VALUES(?,?,?,?,?)',
                           (profile_id, job_id, old['status'] if old else None, status, timestamp))
            self.audit(db, 'application_updated', {'profile_id': profile_id, 'job_id': job_id, 'status': status})

    def evaluate(self, profile_id='default'):
        from .matching import match_job, MATCHER_VERSION
        with self.connect() as db:
            p = db.execute('SELECT data FROM profiles WHERE id=?', (profile_id,)).fetchone()
            if not p:
                raise ValueError('Configure a profile before matching')
            profile = json.loads(p['data'])
            count = 0
            for row in db.execute('SELECT id,data FROM jobs').fetchall():
                result = match_job(json.loads(row['data']), profile)
                db.execute('INSERT INTO matches VALUES(?,?,?,?) ON CONFLICT(profile_id,job_id) DO UPDATE SET data=excluded.data,updated_at=excluded.updated_at',
                           (profile_id, row['id'], dump(result), now()))
                count += 1
            self.audit(db, 'contextual_matching_completed', {'profile_id': profile_id, 'jobs': count})
        return {'evaluated': count, 'method': MATCHER_VERSION}

    def summary(self, profile_id='default'):
        with self.connect() as db:
            total = db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]
            status = dict(db.execute('SELECT status,COUNT(*) FROM applications WHERE profile_id=? GROUP BY status', (profile_id,)).fetchall())
            tracked = sum(status.values())
            status['discovered'] = status.get('discovered', 0) + total - tracked
            matched = db.execute('SELECT COUNT(*) FROM matches WHERE profile_id=?', (profile_id,)).fetchone()[0]
            sources = [dict(r) for r in db.execute('SELECT * FROM sources ORDER BY id')]
            runs = [dict(r) for r in db.execute('SELECT * FROM runs ORDER BY id DESC LIMIT 20')]
        return {'total_jobs': total, 'status_counts': status, 'matched_jobs': matched, 'sources': sources, 'recent_runs': runs}

    def learning(self, profile_id='default'):
        from .learning import report
        return report(self, profile_id)

    def backup(self, destination: str | Path):
        path = Path(destination)
        if path.resolve() == self.path.resolve() or path.exists():
            raise ValueError('Backup destination must be a new file')
        path.parent.mkdir(parents=True, exist_ok=True)
        # SQLite online backup handles WAL and live readers correctly.
        with self.connect() as source:
            target = sqlite3.connect(path)
            try:
                source.backup(target)
                if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('Backup integrity check failed')
            finally:
                target.close()
        return str(path)
