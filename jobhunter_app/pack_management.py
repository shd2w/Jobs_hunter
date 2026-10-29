"""Private filesystem versions and explicit manual review; never applications."""
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from uuid import uuid4
from filelock import FileLock, Timeout

FORMAT = 1
CHECKS = ('facts', 'target', 'original_cv', 'manual_submission')
ID = re.compile(r'[0-9a-f]{32}')
HEX = re.compile(r'[0-9a-f]{64}')
MAX_REVIEWS = 1000


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def root_path(root):
    root = Path(root).absolute()
    if root.is_symlink():
        raise ValueError('Pack root must not be a symlink')
    return root.resolve()


@contextmanager
def locked(root, name):
    root = root_path(root)
    lock = root.parent / ('.' + root.name + '-' + name + '.lock')
    if lock.is_symlink():
        raise ValueError('Unsafe pack lock')
    try:
        with FileLock(str(lock), timeout=10):
            yield
    except Timeout as exc:
        raise ValueError('Pack operation busy; refresh and retry manually') from exc


def stage_version(root):
    root = root_path(root)
    root.mkdir(parents=True, exist_ok=True)
    return uuid4().hex, Path(tempfile.mkdtemp(prefix='.pack-stage-', dir=root))


def publish_version(root, stage, version_id, kind='pack'):
    root = root_path(root)
    if not isinstance(version_id, str) or not ID.fullmatch(version_id) or kind not in ('pack', 'cover'):
        raise ValueError('Invalid version identifier')
    final = root / (kind + '-' + version_id)
    with locked(root, 'publish'):
        if final.exists() or final.is_symlink():
            raise ValueError('Version already exists; no output overwritten')
        stage.rename(final)  # Same-filesystem publication of the completed directory.
    return final


def write_json(path, data):
    """Atomic replacement only inside an owned stage or locked new event slot."""
    path = Path(path)
    fd, temp = tempfile.mkstemp(prefix='.write-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def read_bytes(path, limit):
    # Open the inspected regular file, not a linked/replaced artifact.
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
        raise ValueError('Missing, linked or oversized pack artifact')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'rb') as stream:
        opened, current = os.fstat(stream.fileno()), path.lstat()
        if (not stat.S_ISREG(current.st_mode) or not stat.S_ISREG(opened.st_mode)
                or (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino)
                or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)):
            raise ValueError('Pack artifact changed while opening')
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Oversized pack artifact')
    return data


def read_json(path, limit=2 * 1024 * 1024):
    try:
        return json.loads(read_bytes(path, limit))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('Unreadable pack metadata') from exc


def context(store, job_id, profile_id):
    from .posts import origins
    return digest({'job': store.job(job_id), 'profile': store.profile(profile_id),
                   'post_origins': origins(store, job_id)})


def seal_pack(stage, version_id, job_id, profile_id, context_sha, has_cv):
    names = ['cover-letter-draft.txt', 'preparation.json'] + (['original-cv.pdf'] if has_cv else [])
    manifest = {'format': FORMAT, 'kind': 'core-preparation', 'version_id': version_id,
                'created_at': now(), 'job_id': job_id, 'profile_id': profile_id,
                'context_sha256': context_sha,
                'artifacts': {n: sha256((stage/n).read_bytes()).hexdigest() for n in names}}
    write_json(stage/'pack.json', manifest)
    return manifest


def _folder(root, version_id):
    if not isinstance(version_id, str) or not ID.fullmatch(version_id):
        raise ValueError('Invalid pack version ID')
    folder = root_path(root) / ('pack-' + version_id)
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError('Pack version not found')
    return folder


def _manifest(root, version_id, profile_id):
    folder = _folder(root, version_id)
    m = read_json(folder/'pack.json', 64000)
    if (not isinstance(m, dict) or m.get('format') != FORMAT or m.get('kind') != 'core-preparation'
            or m.get('version_id') != version_id or m.get('profile_id') != profile_id):
        raise ValueError('Pack version unavailable for this profile')
    if (not isinstance(m.get('job_id'), str) or not m['job_id']
            or not isinstance(m.get('created_at'), str) or len(m['created_at']) > 100
            or not isinstance(m.get('context_sha256'), str) or not HEX.fullmatch(m['context_sha256'])):
        raise ValueError('Invalid pack manifest')
    names = set(m.get('artifacts', {})) if isinstance(m.get('artifacts'), dict) else set()
    if names not in ({'cover-letter-draft.txt', 'preparation.json'}, {'cover-letter-draft.txt', 'preparation.json', 'original-cv.pdf'}):
        raise ValueError('Invalid pack artifact list')
    if any(not isinstance(h, str) or not HEX.fullmatch(h) for h in m['artifacts'].values()):
        raise ValueError('Invalid pack artifact hash')
    return folder, m


def _history(folder, m):
    directory = folder/'reviews'
    if not directory.exists() and not directory.is_symlink():
        return [], ''
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError('Invalid pack review directory')
    files = sorted(directory.iterdir())
    if len(files) > MAX_REVIEWS:
        raise ValueError('Pack review limit reached')
    rows, previous = [], ''
    for i, path in enumerate(files, 1):
        if path.name != f'{i:06d}.json':
            raise ValueError('Pack review history is incomplete or corrupt')
        raw = read_bytes(path, 64000)
        try:
            event = json.loads(raw)
            stamp = datetime.fromisoformat(event['recorded_at'])
        except (ValueError, KeyError, TypeError, UnicodeError, AttributeError) as exc:
            raise ValueError('Invalid pack review event') from exc
        if (not isinstance(event, dict) or event.get('sequence') != i or event.get('version_id') != m['version_id']
                or event.get('profile_id') != m['profile_id'] or event.get('previous_sha256') != previous
                or event.get('decision') not in ('reviewed', 'needs_changes') or event.get('confirmed') is not True
                or stamp.tzinfo is None or not isinstance(event.get('checks'), dict) or set(event['checks']) != set(CHECKS)
                or any(type(v) is not bool for v in event['checks'].values())
                or not isinstance(event.get('artifact_fingerprint'), str) or not HEX.fullmatch(event['artifact_fingerprint'])
                or not isinstance(event.get('preview_fingerprint'), str) or not HEX.fullmatch(event['preview_fingerprint'])
                or (event['decision'] == 'reviewed' and not all(event['checks'].values()))):
            raise ValueError('Invalid pack review event')
        rows.append(event)
        previous = sha256(raw).hexdigest()
    return rows, previous


def inspect_pack(store, root, version_id, profile_id='default'):
    from .documents import validate_cover_report
    folder, m = _manifest(root, version_id, profile_id)
    issues, actual, side, text, report = [], {}, None, '', None
    for name, expected in m['artifacts'].items():
        try:
            raw = read_bytes(folder/name, 21*1024*1024 if name.endswith('.pdf') else 2*1024*1024)
            actual[name] = sha256(raw).hexdigest()
            if actual[name] != expected:
                issues.append('Pack artifact changed: ' + name)
            if name == 'cover-letter-draft.txt':
                text = raw.decode('utf-8')
            elif name == 'preparation.json':
                side = json.loads(raw)
        except (ValueError, OSError, UnicodeError) as exc:
            issues.append('Pack artifact unavailable: ' + name)
    current = None
    try:
        current = context(store, m['job_id'], profile_id)
        if current != m['context_sha256']:
            issues.append('Job, profile or provenance changed; generate a new version')
        if not isinstance(side, dict) or side['job']['id'] != m['job_id']:
            raise ValueError('Invalid preparation snapshot')
        facts = [f['text'] for f in side['cover']['evidence']]
        report = validate_cover_report(text, store.job(m['job_id']), store.profile(profile_id), facts, side['cover'].get('evidence_mapping'))
        if not report['valid'] or report != side['cover']['validation_report']:
            issues.append('Cover validation is no longer current; generate a new version')
        cv = side.get('original_cv')
        if bool(cv) != ('original-cv.pdf' in m['artifacts']):
            raise ValueError('Original CV manifest mismatch')
        if cv:
            original = Path(store.profile(profile_id).get('original_cv', '')).expanduser().resolve()
            source = read_bytes(original, 20*1024*1024)
            if sha256(source).hexdigest() != actual.get('original-cv.pdf') or cv['sha256'] != actual.get('original-cv.pdf'):
                issues.append('Original CV source or copy changed; generate a new version')
    except (ValueError, KeyError, TypeError, OSError, AttributeError):
        issues.append('Pack inputs or validation unavailable; generate a new version')
    try:
        history, previous = _history(folder, m)
    except (ValueError, OSError, TypeError):
        history, previous = [], ''
        issues.append('Pack review history is incomplete or corrupt')
    artifact_fp = digest({'manifest': sha256(read_bytes(folder/'pack.json',64000)).hexdigest(),
                          'artifacts': actual, 'current_context': current})
    fingerprint = digest({'artifacts': artifact_fp, 'last_review': previous})
    state = 'pending'
    if issues:
        state = 'blocked'
    elif history and history[-1]['artifact_fingerprint'] == artifact_fp:
        state = history[-1]['decision']
    return {'version_id': version_id, 'directory': str(folder), 'created_at': m['created_at'],
            'job_id': m['job_id'], 'valid': not issues, 'issues': issues, 'review_state': state,
            'review_required': True, 'fingerprint': fingerprint, 'artifact_fingerprint': artifact_fp,
            'cover_content': text, 'cover_evidence': [f for f in side['cover']['evidence'] if isinstance(f,dict) and isinstance(f.get('text'),str) and isinstance(f.get('source'),str)] if isinstance(side,dict) and isinstance(side.get('cover'),dict) and isinstance(side['cover'].get('evidence'),list) else [],
            'validation_report': report, 'evidence_relevance': report.get('relevance') if report else None,
            'saved_evidence_relevance': side['cover'].get('relevance') if isinstance(side,dict) and isinstance(side.get('cover'),dict) else None,
            'original_cv': side.get('original_cv') if isinstance(side, dict) else None,
            'history': history, 'notice': 'Local self-recorded review only; not fact verification, eligibility approval or an application. Back up pack folders separately from the database.'}


def list_packs(store, root, profile_id='default', job_id='', offset=0, limit=50):
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('Invalid pack page')
    root = root_path(root)
    rows = []
    if root.exists():
        for p in root.glob('pack-*'):
            version_id = p.name[5:]
            try:
                _, m = _manifest(root, version_id, profile_id)
                if not job_id or m['job_id'] == job_id:
                    rows.append(m)
            except (ValueError, OSError, TypeError):
                continue  # Never disclose another profile or infer missing owner metadata.
    rows.sort(key=lambda m: (m['created_at'], m['version_id']), reverse=True)
    selected = rows[offset:offset+limit]
    result = []
    for m in selected:
        item = inspect_pack(store, root, m['version_id'], profile_id)
        result.append({k: item[k] for k in ('version_id','created_at','job_id','review_state','valid','issues')})
    return {'packs': result, 'offset': offset, 'limit': limit, 'has_more': len(rows)>offset+limit,
            'notice': 'Only readable format-1 versions for this profile are listed. Older/unowned/corrupt-manifest folders are untouched; inspect and back them up manually.'}


def review_pack(store, root, version_id, decision, fingerprint, confirmed=False, checks=None, profile_id='default'):
    if decision not in ('reviewed','needs_changes') or confirmed is not True:
        raise ValueError('Explicitly confirm a reviewed or needs_changes decision')
    if not isinstance(checks, dict) or set(checks) != set(CHECKS) or any(type(v) is not bool for v in checks.values()):
        raise ValueError('Provide all four boolean review checks')
    if decision == 'reviewed' and not all(checks.values()):
        raise ValueError('Confirm facts, target, original CV selection/absence and manual submission checks')
    _manifest(root, version_id, profile_id)
    with locked(root, version_id + '-review'):
        preview = inspect_pack(store, root, version_id, profile_id)
        if not preview['valid']:
            raise ValueError('Pack is changed or stale; inspect it and generate a new version')
        if not isinstance(fingerprint, str) or fingerprint != preview['fingerprint']:
            raise ValueError('Review preview changed; inspect again before recording a decision')
        if len(preview['history']) >= MAX_REVIEWS:
            raise ValueError('Pack review limit reached')
        folder, m = _manifest(root, version_id, profile_id)
        rows, previous = _history(folder, m)
        directory = folder/'reviews'
        directory.mkdir(exist_ok=True)
        event = {'sequence': len(rows)+1, 'version_id': version_id, 'profile_id': profile_id,
                 'recorded_at': now(), 'decision': decision, 'confirmed': True, 'checks': checks,
                 'preview_fingerprint': fingerprint, 'artifact_fingerprint': preview['artifact_fingerprint'],
                 'previous_sha256': previous, 'actor': 'local user self-record'}
        path = directory/f'{len(rows)+1:06d}.json'
        if path.exists() or path.is_symlink():
            raise ValueError('Review event already exists; no history overwritten')
        write_json(path, event)
        return inspect_pack(store, root, version_id, profile_id)
