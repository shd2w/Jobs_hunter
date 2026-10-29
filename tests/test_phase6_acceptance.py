"""Integrated preparation/learning acceptance with disposable, synthetic records.

Uses real loopback HTTP. No provider, publisher, model or message calls are allowed.
The PDF fixture is opaque test bytes, not a claim of PDF rendering validation.
"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import shutil
import socket
import pytest
from jobhunter_app.store import Store
from jobhunter_app import pack_management as pm, learning_progress as lp
from tests.test_phase5_acceptance import Client

PRIVATE_REASON = 'PRIVATE_MAPPING_REASON <img src=x onerror=window.BAD_ACCEPTANCE=1> صلة'
PRIVATE_NOTE = 'PRIVATE_PRACTICE_NOTE <img src=x onerror=window.BAD_ACCEPTANCE=1> Übung'
PROFILE = {
    'name': 'Synthetic Acceptance Candidate', 'skills': ['Python'],
    'facts': [
        {'text': 'I built a Python project.', 'source': 'Synthetic project record', 'verified': True},
        {'text': 'I coordinated a workshop.', 'source': 'Synthetic workshop record', 'verified': True},
        {'text': 'I am an expert in SQL.', 'source': 'Synthetic unverified claim', 'verified': False},
    ],
    'matching': {'excluded_companies': ['Synthetic Excluded Employer']},
}
JOBS = [
    {'title': 'Python Engineer', 'company': 'Synthetic Acceptance Employer',
     'url': 'https://example.org/acceptance/positive',
     'description': '😀 Python required.\nSQL required.\nCoordinate project reviews.\nPython preferred.\nGit not required.'},
    {'title': 'Python Analyst', 'company': 'Synthetic Mixed Employer',
     'url': 'https://example.org/acceptance/mixed',
     'description': 'Python required. SQL required. SQL not required. Docker preferred.'},
    {'title': 'Python Engineer', 'company': 'Synthetic Excluded Employer',
     'url': 'https://example.org/acceptance/excluded', 'description': 'Python required. SQL required.'},
]


def seed(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    cv = directory/'original.pdf'
    cv.write_bytes(b'%PDF-1.4\nSYNTHETIC OPAQUE ORIGINAL; NEVER REWRITE\n')
    s = Store(directory/'workspace.sqlite3')
    s.save_profile({**deepcopy(PROFILE), 'original_cv': str(cv)})
    s.ingest(deepcopy(JOBS)); s.evaluate()
    return s


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    original = socket.create_connection
    def local_only(address, *args, **kwargs):
        assert address[0] in ('127.0.0.1', 'localhost', '::1'), 'External I/O forbidden'
        return original(address, *args, **kwargs)
    monkeypatch.setattr(socket, 'create_connection', local_only)
    # Fail even before a provider/notification function tries network I/O.
    def forbidden(*args, **kwargs):
        raise AssertionError('No provider, model, publisher or message operation in acceptance')
    from jobhunter_app import network, digests
    monkeypatch.setattr(network, 'get', forbidden)
    monkeypatch.setattr(digests, 'telegram_digest_send', forbidden)
    return seed(tmp_path)


def positive(c):
    return next(j for j in c.get('/api/jobs') if j['url'].endswith('/positive'))


def mapped(c, job):
    pr = c.get('/api/cover-evidence?id='+job['id'])
    assert len(pr['facts']) == 2  # Unverified SQL claim is never selectable.
    assert 'original_cv' not in c.get('/api/profile')
    text = 'Coordinate project reviews.'; start = pr['target']['description'].index(text)
    return {'format': 1, 'preview_fingerprint': pr['preview_fingerprint'], 'confirmed': True,
            'links': [{'fact_id': pr['facts'][1]['id'], 'field': 'description',
                       'start': start, 'end': start+len(text), 'quote': text, 'reason': PRIVATE_REASON}]}


def inspect(c, version):
    return c.get('/api/pack-inspect?id='+version['version_id'])


def review(c, v, expected=200):
    return c.post('/api/pack-review', {'id': v['version_id'], 'decision': 'reviewed',
                   'fingerprint': v['fingerprint'], 'confirmed': True,
                   'checks': dict.fromkeys(pm.CHECKS, True)}, expected=expected)


def offer(c, skill='SQL'):
    return next(p for p in c.get('/api/learning')['priorities'] if p['skill'] == skill)


def save_practice(c, p):
    return c.post('/api/learning-save', {'skill': p['skill'],
                    'preview_fingerprint': p['learning_options']['plan_fingerprint']})


def progress(c, item, status='completed', note=PRIVATE_NOTE, attested=True, expected=200):
    return c.post('/api/learning-update', {'id': item['id'], 'revision': item['revision'],
                  'progress': {'status': status, 'notes': note, 'completed_attested': attested}}, expected)


def candidate_state(c):
    jobs = c.get('/api/jobs')
    return {'profile': c.get('/api/profile'), 'jobs': jobs, 'summary': c.get('/api/summary'),
            'history': [c.get('/api/history?id='+j['id']) for j in jobs]}


def pack_bytes(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file() and not p.name.endswith('.lock')}


def lifecycle(s):
    c = Client(s); root = s.path.parent/'preparation-packs'; original = Path(s.profile()['original_cv']).read_bytes()
    try:
        job = positive(c); initial = candidate_state(c); guidance = c.get('/api/learning')
        assert guidance['vacancies_reviewed'] == 2
        sql = offer(c); assert sql['learning_options']['mode'] == 'optional_practice'
        assert offer(c, 'Git')['learning_options']['mode'] != 'optional_practice'
        assert c.get('/api/learning-progress')['items'] == [] and c.get('/api/packs')['packs'] == []
        m = mapped(c, job)
        pack = c.post('/api/pack', {'id': job['id'], 'evidence_mapping': m})
        v = inspect(c, pack); assert v['valid'] and v['review_state'] == 'pending'
        assert v['cover_evidence'] == [PROFILE['facts'][1]] and PRIVATE_REASON not in v['cover_content']
        assert v['evidence_relevance']['links'][0]['reason'] == PRIVATE_REASON
        review(c, v); reviewed = inspect(c, pack); assert reviewed['review_state'] == 'reviewed'
        folder = Path(pack['directory']); assert (folder/'original-cv.pdf').read_bytes() == original
        files = pack_bytes(root)
        item = save_practice(c, sql)
        progress(c, item, attested=False, expected=400)
        item = progress(c, item); assert item['status'] == 'completed' and item['completed_at']
        assert save_practice(c, sql) == item
        progress(c, {**item, 'revision': 1}, status='paused', attested=False, expected=400)
        assert c.get('/api/learning-progress')['items'] == [item]
        assert candidate_state(c) == initial and c.get('/api/learning') == guidance
        assert pack_bytes(root) == files and inspect(c, pack) == reviewed
        # Practice completion does not mint a verified SQL fact or cover claim.
        assert len(c.get('/api/cover-evidence?id='+job['id'])['facts']) == 2
        assert PROFILE['facts'][2]['text'] not in v['cover_content']
        day = c.get('/api/inbox')['today']
        c.post('/api/status', {'id': job['id'], 'status': 'reviewing', 'deadline': day, 'notes': 'PRIVATE_APPLICATION_NOTE'})
        assert inspect(c, pack)['review_state'] == 'reviewed'  # Tracking is not target-content change.
        cal = c.get('/api/calendar-preview?start='+day+'&days=0')
        assert cal['events_in_window'] == 1
        outputs = [c.raw('GET','/api/calendar-export?start='+day+'&days=0&fingerprint='+cal['fingerprint'])[2],
                   c.raw('GET','/api/outcome-export?format=json')[2], c.raw('GET','/api/outcome-export?format=csv')[2],
                   json.dumps(c.get('/api/digest-preview')).encode(), json.dumps(c.get('/api/learning')).encode(),
                   c.raw('GET','/api/export?format=json')[2]]
        for raw in outputs:
            for private in (PRIVATE_REASON, PRIVATE_NOTE): assert private.encode() not in raw
        # Raw job exports intentionally include application notes; they are not aggregate exports.
        assert b'PRIVATE_APPLICATION_NOTE' in outputs[-1]
        backup = Path(c.post('/api/backup', {})['backup']); restored = Store(backup)
        assert restored.profile() == s.profile() and restored.jobs() == s.jobs()
        assert lp.listing(restored)['items'] == [item]
        backup_packs = s.path.parent/'private-pack-backup'; shutil.copytree(root, backup_packs)
        assert pm.inspect_pack(restored, backup_packs, pack['version_id'])['review_state'] == 'reviewed'
        # Backup-only database recovery does not magically recover filesystem packs.
        assert pm.list_packs(restored, s.path.parent/'absent-packs')['packs'] == []
        c.post('/api/learning-delete', {'id': item['id'], 'revision': item['revision'], 'confirmed': True})
        assert lp.listing(restored)['items'] == [item] and c.get('/api/learning-progress')['items'] == []
        assert Path(s.profile()['original_cv']).read_bytes() == original
        with restored.connect() as db: assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        return {'status': 'passed', 'http_operations': len(c.operations), 'local_jobs': 3,
                'included_learning_vacancies': 2, 'reviewed_pack_versions': 1,
                'practice_completion_self_recorded_only': True, 'private_export_boundaries_checked': 6,
                'database_and_separate_pack_backup_reopened': True, 'source_cv_sha256': sha256(original).hexdigest(),
                'real_external_requests': 0, 'data': 'disposable synthetic only'}
    finally: c.close()


def test_integrated_preparation_and_learning_http_lifecycle(workspace):
    assert lifecycle(workspace)['status'] == 'passed'


@pytest.mark.parametrize('change', ['source', 'fact_revocation', 'listing', 'skills'])
def test_changed_inputs_block_old_reviews_without_destroying_practice(workspace, change):
    s = workspace; c = Client(s)
    try:
        job = positive(c); m = mapped(c, job); sql = offer(c)
        pack = c.post('/api/pack', {'id': job['id'], 'evidence_mapping': m})
        preview = inspect(c, pack); review(c, preview)
        item = progress(c, save_practice(c, sql)); original = Path(s.profile()['original_cv']).read_bytes()
        profile = c.get('/api/profile')
        if change == 'listing':
            c.post('/api/import', {'jobs': [{**job, 'description': job['description']+'\nSQL preferred.'}]})
        else:
            if change == 'source': profile['facts'][1]['source'] += ' updated'
            elif change == 'fact_revocation': profile['facts'][1]['verified'] = False
            else: profile['skills'].append('SQL')
            c.post('/api/profile', {'profile': profile})
        if change == 'skills':
            # Mapping binds identity/facts/target, not unrelated matching preferences.
            assert c.get('/api/cover-evidence?id='+job['id'])['preview_fingerprint'] == m['preview_fingerprint']
        else:
            c.post('/api/pack', {'id': job['id'], 'evidence_mapping': m}, expected=400)
        review(c, preview, expected=400)
        stale = inspect(c, pack); assert not stale['valid'] and stale['review_state'] == 'blocked'
        assert len(stale['history']) == 1 and stale['saved_evidence_relevance']['links'][0]['reason'] == PRIVATE_REASON
        assert c.get('/api/learning-progress')['items'] == [item]
        c.post('/api/learning-save', {'skill': 'SQL', 'preview_fingerprint': sql['learning_options']['plan_fingerprint']}, expected=400)
        c.post('/api/match', {}); assert c.get('/api/learning-progress')['items'] == [item]
        if change == 'skills': assert all(p['skill'] != 'SQL' for p in c.get('/api/learning')['priorities'])
        # New, explicitly selected facts produce a distinct pending version, not inherited approval.
        fresh = mapped(c, positive(c)) if change != 'fact_revocation' else None
        if fresh:
            second = c.post('/api/pack', {'id': job['id'], 'evidence_mapping': fresh})
            assert second['version_id'] != pack['version_id'] and inspect(c, second)['review_state'] == 'pending'
            assert inspect(c, pack)['review_state'] == 'blocked'
        assert Path(s.profile()['original_cv']).read_bytes() == original
        assert all(j['status'] == 'discovered' for j in c.get('/api/jobs'))
    finally: c.close()


def test_cross_profile_and_workspace_restart_preserve_boundaries(workspace):
    s = workspace; c = Client(s)
    try:
        job = positive(c); pack = c.post('/api/pack', {'id': job['id'], 'evidence_mapping': mapped(c, job)})
        review(c, inspect(c, pack)); item = progress(c, save_practice(c, offer(c)))
    finally: c.close()
    s.save_profile({'name': 'Other synthetic profile', 'skills': ['SQL'], 'facts': []}, 'other'); s.evaluate('other')
    root = s.path.parent/'preparation-packs'
    assert lp.listing(s, 'other')['items'] == [] and pm.list_packs(s, root, 'other')['packs'] == []
    with pytest.raises(ValueError): pm.inspect_pack(s, root, pack['version_id'], 'other')
    with pytest.raises(ValueError): lp.delete(s, item['id'], item['revision'], True, 'other')
    restarted = Store(s.path)
    assert lp.listing(restarted)['items'] == [item]
    assert pm.inspect_pack(restarted, root, pack['version_id'])['review_state'] == 'reviewed'
    assert restarted.profile()['facts'] == PROFILE['facts'] and restarted.jobs()[0]['status'] == 'discovered'
