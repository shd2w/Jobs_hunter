"""Nondestructive, profile-scoped legacy migration. No external paths are opened."""
from __future__ import annotations
from hashlib import sha256
import csv
import io
import json
from pathlib import Path
import re
import sqlite3
import tempfile
from .intake import MAX_BYTES, strict_json
from .store import dump, now, SCHEMA_VERSION
from .validation import normalize_job

FILES = ('evaluations.json', 'jd_cache.json', 'pipeline.md', 'applications.md',
         'below_threshold.md', 'application_queue.jsonl', 'scan-history.tsv', 'jobs_database.xlsx')
MAX_RECORDS = 10000


def _table(text):
    header = None
    for number, line in enumerate(text.splitlines(), 1):
        if not line.startswith('|'):
            continue
        cells = [x.strip() for x in line.strip().strip('|').split('|')]
        if header is None:
            header = cells
        elif all(re.fullmatch(r'[:\- ]+', x) for x in cells):
            continue
        else:
            if len(cells) != len(header):
                raise ValueError('Malformed markdown table width')
            yield number, dict(zip(header, cells))


def _records(filename, content):
    if filename == 'jobs_database.xlsx':
        from .spreadsheets import read_xlsx
        return [(i, x, 'excel_evaluation') for i, x in enumerate(read_xlsx(content, legacy=True), 2)]
    text = content.decode('utf-8-sig')
    if filename == 'evaluations.json':
        records = strict_json(text)
        if not isinstance(records, list):
            raise ValueError('Expected evaluation array')
        return [(i, x, 'evaluation') for i, x in enumerate(records, 1)]
    if filename == 'jd_cache.json':
        records = strict_json(text)
        if not isinstance(records, dict):
            raise ValueError('Expected cache object')
        return [(i, {**x, 'url': url} if isinstance(x, dict) else x, 'description_cache')
                for i, (url, x) in enumerate(records.items(), 1)]
    if filename == 'application_queue.jsonl':
        return [(i, strict_json(line), 'uaa_queue') for i, line in enumerate(text.splitlines(), 1) if line.strip()]
    if filename == 'scan-history.tsv':
        reader = csv.DictReader(io.StringIO(text), delimiter='\t')
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError('Invalid scan history headers')
        rows = list(reader)
        if any(None in row or any(x is None for x in row.values()) for row in rows):
            raise ValueError('Malformed scan history width')
        return [(i, x, 'scan_event') for i, x in enumerate(rows, 2)]
    if filename == 'pipeline.md':
        rows = []
        for i, line in enumerate(text.splitlines(), 1):
            if not line.startswith('- ['):
                continue
            m = re.fullmatch(r'- \[([ x/])\] (https?://\S+)\s*\|\s*([^|]+)\s*\|\s*(.+?)(?:\s*\[([^\]]*)\])?\s*', line)
            if not m:
                raise ValueError('Unrecognized pipeline row')
            marker, url, company, title, location = m.groups()
            rows.append((i, {'url': url, 'company': company.strip(), 'title': title.strip(),
                             'location': location or '', 'evaluation_marker': marker, 'original_line': line}, 'pipeline'))
        return rows
    return [(i, x, 'recommendation_table') for i, x in _table(text)]


def _candidate(raw):
    """Only explicit URL identity. Never join on similar company/title or a report path."""
    url = raw.get('url') or raw.get('URL')
    if isinstance(url, str) and (m := re.fullmatch(r'\[link\]\((https?://[^\s]+)\)', url)):
        url = m.group(1)
    return {'url': url or '', 'title': raw.get('title') or raw.get('job_title') or raw.get('Title') or '',
            'company': raw.get('company') or raw.get('company_name') or raw.get('Company') or '',
            'location': raw.get('location') or '', 'description': raw.get('description') or raw.get('job_description') or '',
            'date_posted': raw.get('date_posted') or ''}


def _collect(directory):
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError('Migration requires a real directory, not a symlink')
    blobs, records, errors = {}, [], []
    for filename in FILES:
        path = directory / filename
        if not path.exists() and not path.is_symlink():
            continue
        if path.is_symlink() or not path.is_file():
            errors.append({'file': filename, 'error': 'Symlink or non-file rejected'})
            continue
        with path.open('rb') as stream:
            content = stream.read(MAX_BYTES + 1)
        if len(content) > MAX_BYTES:
            errors.append({'file': filename, 'error': 'File exceeds 10 MiB'})
            continue
        blobs[filename] = content
        try:
            items = _records(filename, content)
            if len(items) > MAX_RECORDS or len(records) + len(items) > 50000:
                raise ValueError('Migration record budget exceeded')
            for row, payload, kind in items:
                if not isinstance(payload, dict):
                    errors.append({'file': filename, 'row': row, 'error': 'Expected record object'})
                    continue
                serialized = dump(payload)  # No NaN or implicit executable serialization.
                record_id = sha256((filename + '\n' + serialized).encode()).hexdigest()
                records.append({'id': record_id, 'file': filename, 'row': row, 'kind': kind, 'payload': payload})
        except (ValueError, UnicodeError, TypeError, csv.Error) as exc:
            errors.append({'file': filename, 'error': str(exc)[:180]})
    ignored = sorted(p.name for p in directory.iterdir() if p.is_file() and p.name not in FILES and not p.name.endswith(('.lock', '-wal', '-shm')))
    return blobs, records, errors, ignored


def _plan(store, records, db):
    candidates, links, conflicts, invalid, warnings = {}, {}, [], [], []
    for record in records:
        raw = record['payload']; item = _candidate(raw)
        if record['kind'] == 'recommendation_table' and not item['url']:
            warnings.append({'file': record['file'], 'row': record['row'], 'reason': 'No explicit URL; archived without a job link'})
            continue
        # Scan filters/recommendations/checkmarks are history, not active application states.
        if record['kind'] == 'scan_event' and str(raw.get('status', '')).startswith('skipped_'):
            continue
        try:
            job = normalize_job(item)
        except (ValueError, TypeError) as exc:
            invalid.append({'file': record['file'], 'row': record['row'], 'error': str(exc)})
            continue
        alias = db.execute('SELECT job_id FROM job_aliases WHERE alias_url=?', (job['url'],)).fetchone()
        job_id = alias['job_id'] if alias else sha256(job['url'].encode()).hexdigest()
        links[record['id']] = job_id
        if alias:
            # Reviewed aliases cannot rewrite the authoritative listing.
            continue
        previous = candidates.get(job_id)
        stored = db.execute('SELECT data FROM jobs WHERE id=?', (job_id,)).fetchone()
        authoritative = json.loads(stored['data']) if stored else previous
        if authoritative:
            different = [k for k in ('title', 'company') if ' '.join(authoritative[k].casefold().split()) != ' '.join(job[k].casefold().split())]
            if different:
                conflicts.append({'file': record['file'], 'row': record['row'], 'job_id': job_id, 'fields': different,
                                  'reason': 'Same canonical URL has different identity fields; no automatic overwrite'})
                continue
        if stored:
            # Existing DB is authoritative. Only fill blanks, never downgrade richer facts.
            candidates[job_id] = {k: v or job.get(k, '') for k, v in authoritative.items()}
        elif previous:
            candidates[job_id] = {k: v or job.get(k, '') for k, v in previous.items()}
        else:
            candidates[job_id] = job
    blocked = {c['job_id'] for c in conflicts}
    for job_id in blocked:
        candidates.pop(job_id, None)
    # Conflicts are archived unlinked, never given a misleading successful association.
    links = {k: v for k, v in links.items() if v not in blocked}
    return candidates, links, conflicts, invalid, warnings


def migrate(store, legacy_dir: Path, dry_run=True, profile_id='default', allow_partial=False):
    if not store.profile(profile_id) and not _profile_exists(store, profile_id):
        raise ValueError('Initialize the selected profile before migration')
    blobs, records, errors, ignored = _collect(legacy_dir)
    manifest = {k: sha256(v).hexdigest() for k, v in blobs.items()}
    batch_id = sha256(dump({'profile': profile_id, 'manifest': manifest, 'partial': allow_partial, 'version': 1}).encode()).hexdigest()
    def preview(db):
        candidates, links, conflicts, invalid, warnings = _plan(store, records, db)
        stats = store.ingest(list(candidates.values()), source='legacy-migration', dry_run=True, _db=db)
        stats['invalid'] += len(invalid)
        archived = sum(not db.execute('SELECT 1 FROM historical_records WHERE profile_id=? AND id=?', (profile_id, x['id'])).fetchone() for x in {r['id']: r for r in records}.values())
        return candidates, links, {'preview': stats, 'file_errors': errors, 'conflicts': conflicts,
                'invalid_records': invalid, 'warnings': warnings, 'new_history_records': archived,
                'ignored_files': ignored, 'manifest': manifest, 'batch_id': batch_id, 'backup': None,
                'notice': 'Historical evaluations, queue states, recommendations and scan events are archived, not current eligibility or application claims. Documents are never opened.'}
    with store.connect() as db:
        candidates, links, report = preview(db)
    if dry_run:
        return report
    if (errors or report['conflicts'] or report['invalid_records']) and not allow_partial:
        raise ValueError('Migration has invalid or conflicting records; inspect preview. Use a corrected COPY, or explicitly --allow-partial to archive available records and omit unresolved jobs')
    if not blobs:
        raise ValueError('No supported readable input files')
    from filelock import FileLock
    with FileLock(str(store.path) + '.migration.lock', timeout=0):
        with store.connect() as db:
            completed = db.execute('SELECT result FROM migration_batches WHERE id=?', (batch_id,)).fetchone()
        if completed:
            saved = json.loads(completed['result'])
            # Backward-compatible result shape; no writes, invalidation or duplicate history.
            return {**saved, 'already_applied': True, 'result': {**saved['result'], 'inserted': 0,
                    'updated': saved['preview']['inserted'] + saved['preview']['updated'], 'unchanged': len(candidates)}}
        backup_root = Path(legacy_dir) / 'migration-backups'
        if backup_root.is_symlink():
            raise ValueError('Backup directory cannot be a symlink')
        backup_root.mkdir(exist_ok=True)
        backup = Path(tempfile.mkdtemp(prefix='legacy-', dir=backup_root))
        for filename, content in blobs.items():
            (backup / filename).write_bytes(content)
        (backup / 'manifest.json').write_text(dump(manifest), encoding='utf-8')
        store.backup(backup / 'before.sqlite3')
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            candidates, links, report = preview(db)  # Recheck conflicts under the write lock.
            if (errors or report['conflicts'] or report['invalid_records']) and not allow_partial:
                raise ValueError('Migration conflict detected under write lock; no records changed')
            for filename, content in blobs.items():
                path = Path(legacy_dir) / filename
                if path.is_symlink() or path.read_bytes() != content:
                    raise ValueError('Migration input changed since preview; rerun with a stable copy')
            result = store.ingest(list(candidates.values()), source='legacy-migration', _db=db)
            for record in records:
                # A link is valid only if the job survived validation/alias/conflict gates.
                job_id = links.get(record['id'])
                db.execute('INSERT OR IGNORE INTO historical_records VALUES(?,?,?,?,?,?,?,?)',
                    (record['id'], profile_id, record['file'], record['row'], record['kind'], job_id, dump(record['payload']), now()))
            report.update(result=result, backup=str(backup), already_applied=False)
            db.execute('INSERT INTO migration_batches VALUES(?,?,?,?,?)', (batch_id, profile_id, dump(manifest), dump(report), now()))
            store.audit(db, 'legacy_migration', {'batch_id': batch_id, 'profile_id': profile_id, 'partial': allow_partial,
                                               'jobs': len(candidates), 'records': len(records)})
        return report


def _profile_exists(store, profile_id):
    with store.connect() as db:
        return db.execute('SELECT 1 FROM profiles WHERE id=?', (profile_id,)).fetchone() is not None


def history(store, profile_id='default', job_id='', limit=200, offset=0):
    if not 1 <= limit <= 1000 or offset < 0:
        raise ValueError('Invalid history page')
    with store.connect() as db:
        rows = db.execute('SELECT * FROM historical_records WHERE profile_id=? AND (?=\'\' OR job_id=?) ORDER BY source_file,source_row,id LIMIT ? OFFSET ?',
                          (profile_id, job_id, job_id, limit, offset)).fetchall()
    return [{**dict(row), 'payload': json.loads(row['payload'])} for row in rows]


def restore_backup(source: Path, destination: Path):
    """Restore to a NEW filename only; never roll back a live database in place."""
    source, destination = Path(source), Path(destination)
    if source.is_symlink() or not source.is_file() or destination.exists() or destination.is_symlink():
        raise ValueError('Restore requires a real backup and a new destination filename')
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Opening SQLite read-only prevents accidental creation/reset of a bad source.
    with sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True) as origin:
        version = origin.execute('PRAGMA user_version').fetchone()[0]
        if version < 1 or version > SCHEMA_VERSION or origin.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Backup schema/integrity validation failed')
        required = {'profiles', 'jobs', 'applications', 'status_history'}
        if not required <= {x[0] for x in origin.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
            raise ValueError('Backup is not a supported JobHunter database')
        if origin.execute('PRAGMA foreign_key_check').fetchone():
            raise ValueError('Backup foreign key validation failed')
        with destination.open('xb'):
            pass
        try:
            with sqlite3.connect(destination) as target:
                origin.backup(target)
                if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('Restored database failed validation')
        except BaseException:
            destination.unlink(missing_ok=True)
            raise
    return {'restored_to': str(destination), 'schema': version, 'notice': 'Original/live database unchanged. Stop workers and select this new database explicitly.'}
