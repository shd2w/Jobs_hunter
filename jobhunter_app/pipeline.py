"""Canonical file ingestion, state reconciliation and database-backed UAA projection."""
from __future__ import annotations
from hashlib import sha256
import json
import math
from pathlib import Path
from .store import STATES, dump, now
from .validation import normalize_job


def import_records(store, rows, profile_id='default', dry_run=False, with_state=False, source='import'):
    if not isinstance(rows, list) or len(rows) > 10000:
        raise ValueError('Expected at most 10,000 job objects')
    normalized, errors = [], []
    states, conflicts = {}, []
    for i, raw in enumerate(rows, 1):
        try:
            job = normalize_job(raw)
            normalized.append((i, job, raw))
            if with_state:
                status, notes, deadline = raw.get('status', 'discovered'), raw.get('notes', ''), raw.get('deadline', '')
                if status not in STATES or not isinstance(notes, str) or len(notes) > 20000 or not isinstance(deadline, str):
                    raise ValueError('Invalid explicit application state')
                if deadline:
                    from datetime import date
                    date.fromisoformat(deadline)
                state = (status, notes, deadline)
                if job['url'] in states and states[job['url']] != state:
                    raise ValueError('Input contains conflicting states for one canonical URL')
                states[job['url']] = state
        except (ValueError, TypeError) as exc:
            errors.append({'row': i, 'error': str(exc)})
    with store.connect() as db:
        if not dry_run:
            db.execute('BEGIN IMMEDIATE')
        if with_state and not db.execute('SELECT 1 FROM profiles WHERE id=?', (profile_id,)).fetchone():
            raise ValueError('Initialize the selected profile before importing application state')
        seen = {}
        state_updates = {}
        for i, job, raw in normalized:
            alias = db.execute('SELECT job_id FROM job_aliases WHERE alias_url=?', (job['url'],)).fetchone()
            job_id = alias['job_id'] if alias else sha256(job['url'].encode()).hexdigest()
            stored = db.execute('SELECT data FROM jobs WHERE id=?', (job_id,)).fetchone()
            previous = json.loads(stored['data']) if stored else seen.get(job_id)
            if previous and not alias and any(previous[k].casefold().strip() != job[k].casefold().strip() for k in ('title', 'company')):
                conflicts.append({'row': i, 'job_id': job_id, 'reason': 'Conflicting identity at the same canonical URL'})
            seen[job_id] = job
            if with_state and job['url'] in states:
                state = states[job['url']]
                current = db.execute('SELECT status,notes,deadline FROM applications WHERE profile_id=? AND job_id=?', (profile_id, job_id)).fetchone()
                if current and tuple(current) != state:
                    conflicts.append({'row': i, 'job_id': job_id, 'reason': 'Existing profile application state differs; update it explicitly, not by import'})
                if job_id in state_updates and state_updates[job_id] != state:
                    conflicts.append({'row': i, 'job_id': job_id, 'reason': 'Aliases have conflicting application state'})
                state_updates[job_id] = state
        report = store.ingest([x[1] for x in normalized], source=source, dry_run=True, _db=db)
        report.update(invalid=len(errors), errors=errors, conflicts=conflicts,
                      state_import=with_state, state_rows=len(state_updates),
                      notice='State is imported only with explicit --with-state. Existing differing state is never overwritten.')
        if dry_run:
            return report
        if errors or conflicts:
            raise ValueError('Import has invalid/conflicting records; preview first. No rows were saved')
        result = store.ingest([x[1] for x in normalized], source=source, _db=db)
        for job_id, state in state_updates.items():
            current = db.execute('SELECT status,notes,deadline FROM applications WHERE profile_id=? AND job_id=?', (profile_id, job_id)).fetchone()
            if current:
                continue  # Equal state rerun, no duplicate status history.
            status, notes, deadline = state
            timestamp = now()
            db.execute('INSERT INTO applications VALUES(?,?,?,?,?,?)', (profile_id, job_id, status, notes, deadline, timestamp))
            db.execute('INSERT INTO status_history(profile_id,job_id,old_status,new_status,changed_at) VALUES(?,?,?,?,?)',
                       (profile_id, job_id, None, status, timestamp))
        store.audit(db, 'canonical_file_import', {'profile_id': profile_id, 'state_rows': len(state_updates), 'rows': len(normalized)})
        return {**report, **result, 'conflicts': []}


def export_history(store, profile_id='default'):
    from .migration import history
    rows, offset = [], 0
    while True:
        page = history(store, profile_id, limit=1000, offset=offset)
        rows.extend(page)
        if len(page) < 1000:
            break
        offset += len(page)
    return json.dumps({'profile_id': profile_id, 'historical_records': rows,
                       'notice': 'Historical source observations, not current eligibility or applications.'},
                      ensure_ascii=False, allow_nan=False, indent=2).encode('utf-8')


def export_uaa(store, destination: Path, profile_id='default', threshold=3.5, profile_path=None):
    """Reuse the pinned exporter. Never infer qualifications or manufacture documents."""
    from utils.queue_exporter import build_queue_entries, _atomic_write_jsonl, load_profile, extract_candidate_profile_snapshot, _detect_source
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or not 1 <= threshold <= 5:
        raise ValueError('UAA threshold must be between 1 and 5')
    if Path(destination).exists() or Path(destination).is_symlink():
        raise ValueError('Choose a new UAA export filename; never overwrite originals')
    with store.connect() as db:
        records = db.execute("SELECT h.payload,h.job_id,h.source_row FROM historical_records h WHERE profile_id=? AND kind='evaluation' ORDER BY source_row,id", (profile_id,)).fetchall()
        jobs = {r['id']: json.loads(r['data']) for r in db.execute('SELECT id,data FROM jobs')}
    # Choose the newest explicit timestamp per job, deterministic on ties. Retain history separately.
    from datetime import datetime, timezone
    latest, unlinked, ambiguous = {}, [], set()
    for record in records:
        evaluation = json.loads(record['payload']); jid = record['job_id']
        if not jid or jid not in jobs:
            unlinked.append({'reason': 'unlinked_historical_evaluation', 'source_row': record['source_row']})
            continue
        raw_time = evaluation.get('evaluated_at')
        try:
            timestamp = datetime.fromisoformat(raw_time.replace('Z', '+00:00')) if raw_time else datetime.min.replace(tzinfo=timezone.utc)
            if timestamp.tzinfo is None:
                # Do not guess a timezone for competing historical evaluations.
                raise ValueError('Naive evaluation timestamp')
            timestamp = timestamp.astimezone(timezone.utc)
        except (ValueError, TypeError, AttributeError):
            unlinked.append({'reason': 'invalid_or_naive_evaluation_timestamp', 'job_id': jid})
            continue
        if jid not in latest or timestamp > latest[jid][0]:
            latest[jid] = (timestamp, evaluation)
            ambiguous.discard(jid)
        elif timestamp == latest[jid][0] and dump(evaluation) != dump(latest[jid][1]):
            ambiguous.add(jid)
    # Current shared evaluations supersede historical scores only for this
    # explicit profile/job. Local, failed or stale receipts must NEVER resurrect
    # an older AI recommendation in the application queue.
    from .evaluation_service import latest as latest_evaluation
    with store.connect() as db:
        has_evaluations = db.execute("SELECT 1 FROM sqlite_master WHERE name='evaluation_meta'").fetchone()
        evaluated_jobs = [r[0] for r in db.execute('SELECT DISTINCT job_id FROM evaluations WHERE profile_id=?',(profile_id,))] if has_evaluations else []
    for jid in evaluated_jobs:
        if jid not in jobs: continue
        current = latest_evaluation(store,jid,profile_id)
        latest.pop(jid,None); ambiguous.discard(jid)
        if not current or current.get('stale') or current.get('status')!='completed_ai' or current.get('method')!='ai':
            unlinked.append({'reason':'current_evaluation_not_exportable','job_id':jid})
            continue
        evaluation = {**current['ai'],'evaluated_at':current['finished_at']}
        latest[jid] = (datetime.fromisoformat(current['finished_at']),evaluation)
    original_cv = store.profile(profile_id).get('original_cv', '')
    original_hash = None
    if original_cv:
        cv = Path(original_cv)
        if cv.suffix.lower() != '.pdf' or not cv.is_file() or cv.stat().st_size > 20 * 1024 * 1024:
            raise ValueError('Select an existing original PDF CV (at most 20 MiB)')
        content = cv.read_bytes()
        if not content.startswith(b'%PDF-'):
            raise ValueError('Original CV is not a PDF')
        original_hash = sha256(content).hexdigest()
    evaluations, pipeline = [], {}
    for jid, (_, evaluation) in sorted(latest.items()):
        job = jobs[jid]
        if jid in ambiguous:
            unlinked.append({'reason': 'ambiguous_latest_historical_evaluation', 'job_id': jid})
            continue
        # Do not transplant an old score to a different role after a live listing update.
        if any(str(evaluation.get(k) or '').strip().casefold() != job[k].strip().casefold() for k in ('title', 'company')):
            unlinked.append({'reason': 'historical_identity_changed', 'job_id': jid})
            continue
        if not original_cv and (evaluation.get('cv_pdf_path') or evaluation.get('cv_path')):
            unlinked.append({'reason': 'original_cv_not_selected', 'job_id': jid})
            continue
        projection = {**evaluation, 'url': job['url'], 'title': job['title'], 'company': job['company']}
        if original_cv:
            projection['cv_pdf_path'] = str(Path(original_cv).resolve())
            projection.pop('cv_path', None)  # Optional cv_md must not expose an old tailored CV.
        evaluations.append(projection)
        pipeline[job['url']] = {**job, 'source': _detect_source(job['url'])}
    snapshot = extract_candidate_profile_snapshot(load_profile(Path(profile_path))) if profile_path else {}
    rows, skips = build_queue_entries(evaluations, pipeline, snapshot, threshold)
    if original_cv and sha256(Path(original_cv).read_bytes()).hexdigest() != original_hash:
        raise ValueError('Original CV changed during export; no queue published')
    import tempfile
    from .files import publish_new
    # Retain the existing deterministic JSONL writer, then publish without clobbering.
    with tempfile.TemporaryDirectory(prefix='jobhunter-uaa-') as directory:
        temporary = Path(directory) / 'queue.jsonl'
        _atomic_write_jsonl(temporary, rows)
        publish_new(Path(destination), temporary.read_bytes())
    return {'exported': len(rows), 'skipped': skips + unlinked, 'file': str(destination),
            'original_cv_sha256': original_hash,
            'notice': 'Current shared AI or historical evaluation projection. Local/fallback/stale evaluations are not AI queue entries. Required existing PDFs and pinned UAA validation remain enforced. Nothing submitted.'}
