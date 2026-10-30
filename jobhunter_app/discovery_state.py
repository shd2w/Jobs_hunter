"""Opt-in, versioned additive extension; original Store schema remains compatible."""
from pathlib import Path
import sqlite3
from .store import now

SCHEMA = '''
CREATE TABLE autonomy_meta(version INTEGER NOT NULL);
INSERT INTO autonomy_meta VALUES(1);
CREATE TABLE search_progress(signature TEXT PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE search_runs(id TEXT PRIMARY KEY, profile_id TEXT NOT NULL, intent_version TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT, status TEXT NOT NULL, report TEXT NOT NULL);
CREATE TABLE search_tasks(id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES search_runs(id), source_id TEXT NOT NULL, signature TEXT NOT NULL, status TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE source_leads(id TEXT PRIMARY KEY, kind TEXT, identifier TEXT, url TEXT NOT NULL, state TEXT NOT NULL, evidence TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE opportunity_members(job_id TEXT PRIMARY KEY REFERENCES jobs(id), group_id TEXT NOT NULL, evidence TEXT NOT NULL);
CREATE TABLE search_projection(job_id TEXT PRIMARY KEY REFERENCES jobs(id), status TEXT NOT NULL, fingerprint TEXT NOT NULL, error TEXT NOT NULL DEFAULT '');
CREATE TABLE search_quality(source_id TEXT NOT NULL, signature TEXT NOT NULL, observed_at TEXT NOT NULL, valid INTEGER NOT NULL, invalid INTEGER NOT NULL, outcome TEXT NOT NULL, error TEXT NOT NULL);
'''


def ensure(store):
    from filelock import FileLock
    with FileLock(str(store.path)+'.schema.lock', timeout=30), store.connect() as db:
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='autonomy_meta'").fetchone():
            if db.execute('SELECT version FROM autonomy_meta').fetchone()[0] != 1:
                raise ValueError('Unsupported autonomy extension version')
            return
        backup = Path(str(store.path)+'.pre-autonomy-v1-'+now().replace(':','-')+'.bak')
        with sqlite3.connect(backup) as target: db.backup(target)
        db.executescript('BEGIN IMMEDIATE;'+SCHEMA+'COMMIT;')
