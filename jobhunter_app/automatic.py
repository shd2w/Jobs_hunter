"""Automatic, bounded discovery while the single-user server is running.

No credentials or paid providers are added. Existing approvals, provider-wide
cooldowns, Retry-After gates, checkpoints, scan locking and cancellation apply.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json
import time
from threading import Event, Lock, Thread
from filelock import FileLock, Timeout
from .store import dump, now
from .sources import Source, scan
from .source_health import health

KEY = 'automatic_discovery'
STARTERS = (('jobicy', 'remote'), ('arbeitnow', 'de'), ('remotive', 'remote'),
            ('remoteok', 'remote'), ('weworkremotely', 'remote'),
            ('jobspy_linkedin', 'configured'), ('jobspy_indeed', 'configured'),
            ('jobspy_bayt', 'configured'), ('jobspy_google', 'configured'),
            ('jobspy_glassdoor', 'configured'), ('jobspy_zip_recruiter', 'configured'),
            ('jobspy_naukri', 'configured'), ('jobspy_bdjobs', 'configured'),
            ('jobspy_hellowork', 'configured'))
SEED_KEY = 'scraper_registry_revision'
SEED_REVISION = 2
LABELS = {'jobicy:remote': 'Jobicy · worldwide remote', 'arbeitnow:de': 'Arbeitnow · Germany',
          'remotive:remote': 'Remotive · worldwide remote',
          'remoteok:remote': 'Remote OK · remote', 'weworkremotely:remote': 'We Work Remotely · remote',
          'jobspy_indeed:configured': 'Indeed · original regional searches',
          'jobspy_linkedin:configured': 'LinkedIn jobs · original regional searches',
          'jobspy_bayt:configured': 'Bayt · regional searches',
          'jobspy_google:configured': 'Google Jobs · upstream unavailable',
          'jobspy_glassdoor:configured': 'Glassdoor · DE/AT/CH and remote',
          'jobspy_zip_recruiter:configured': 'ZipRecruiter · US/Canada remote',
          'jobspy_naukri:configured': 'Naukri · India remote',
          'jobspy_bdjobs:configured': 'BDJobs · Bangladesh work-from-home',
          'jobspy_hellowork:configured': 'HelloWork · France remote'}


def _read(db, profile_id):
    row = db.execute('SELECT data FROM workflow_settings WHERE profile_id=?', (profile_id,)).fetchone()
    try: data = json.loads(row[0]) if row else {}
    except (ValueError, TypeError): raise ValueError('Invalid settings; preserve a backup, no reset attempted') from None
    if not isinstance(data, dict): raise ValueError('Invalid settings; no reset attempted')
    value = data.get(KEY)
    if KEY in data and (not isinstance(value, dict) or set(value) != {'version', 'enabled'}
            or type(value['version']) is not int or value['version'] != 1 or type(value['enabled']) is not bool):
        raise ValueError('Invalid automatic discovery settings; no reset attempted')
    return data, value


def configure(store, profile_id='default', enabled=None):
    if enabled is not None and type(enabled) is not bool: raise ValueError('Use a true or false discovery choice')
    with store.connect() as db:
        exists = db.execute('SELECT 1 FROM profiles WHERE id=?', (profile_id,)).fetchone()
    if not exists: store.save_profile({'name': '', 'skills': [], 'facts': []}, profile_id)
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        data, value = _read(db, profile_id)
        if value is None:
            # Insert only. Never reapprove an existing paused/blocked source.
            for kind, identifier in STARTERS:
                source = Source(kind, identifier)
                db.execute('INSERT OR IGNORE INTO sources(id,kind,identifier,approved) VALUES(?,?,?,1)',
                           (source.id, kind, identifier))
            value = {'version': 1, 'enabled': True}
        if data.get(SEED_KEY) != SEED_REVISION:
            # Add missing sources on upgrade, without overwriting any approval,
            # pause, checkpoint, profile, existing job or unrelated setting.
            for kind, identifier in STARTERS:
                source = Source(kind, identifier)
                db.execute('INSERT OR IGNORE INTO sources(id,kind,identifier,approved) VALUES(?,?,?,1)',
                           (source.id, kind, identifier))
            data[SEED_KEY] = SEED_REVISION
            db.execute('INSERT INTO workflow_settings VALUES(?,?,?) ON CONFLICT(profile_id) DO UPDATE SET data=excluded.data,updated_at=excluded.updated_at',
                       (profile_id, dump({**data, KEY: value}), now()))
        new = {**value, **({'enabled': enabled} if enabled is not None else {})}
        if data.get(KEY) != new:
            data[KEY] = new
            db.execute('INSERT INTO workflow_settings VALUES(?,?,?) ON CONFLICT(profile_id) DO UPDATE SET data=excluded.data,updated_at=excluded.updated_at',
                       (profile_id, dump(data), now()))
            store.audit(db, 'automatic_discovery_configured', {'profile_id': profile_id, 'enabled': new['enabled']})
        return new


class _Cancellation:
    """Observe pauses saved by another server before committing a response."""
    def __init__(self, owner): self.owner = owner
    def is_set(self):
        if self.owner.cancel.is_set() or self.owner.closed.is_set(): return True
        try:
            with self.owner.store.connect() as db: _, config = _read(db, self.owner.profile_id)
            return not config['enabled']
        except (ValueError, TypeError): return True


class AutomaticDiscovery:
    def __init__(self, store, profile_id='default', interval=60):
        self.store, self.profile_id, self.interval = store, profile_id, max(1, interval)
        configure(store, profile_id)
        self.legacy_restore = None
        self.legacy_restore_error = ''
        try:
            from scanners.compat import restore_existing_legacy
            self.legacy_restore = restore_existing_legacy(store, profile_id)
        except (ValueError, OSError) as exc:
            # Do not discard sources or jobs if an old file needs manual repair.
            self.legacy_restore_error = type(exc).__name__ + ': legacy restoration needs review; files unchanged'
        self.cancel, self.wake, self.closed = Event(), Event(), Event()
        self.lock = Lock(); self.control = Lock(); self.thread = None
        self.state = {'phase': 'starting', 'current_source': '', 'revision': 0, 'last_cycle': None, 'error': ''}

    def _state(self, **changes):
        with self.lock:
            self.state.update(changes); self.state['revision'] += 1

    def start(self):
        if self.thread is None:
            self.thread = Thread(target=self._loop, name='jobhunter-discovery', daemon=True); self.thread.start()

    def stop(self):
        with self.control:
            self.closed.set(); self.cancel.set(); self.wake.set()
        if self.thread: self.thread.join(timeout=22)

    def choice(self, enabled):
        with self.control:
            result = configure(self.store, self.profile_id, enabled)
            if not enabled: self.cancel.set()
            # Resume clears cancellation only at the next cycle boundary.
            # An in-flight cancelled response must never be imported.
        self._state(phase='waiting' if enabled else 'paused'); self.wake.set()
        return result

    def check(self):
        # This wakes the coordinator, not a quota-bypassing forced scan.
        self.wake.set(); return {'requested': True, 'notice': 'Checking sources that are due; provider cooldowns remain in force.'}

    def status(self):
        with self.store.connect() as db: _, config = _read(db, self.profile_id)
        with self.lock: state = dict(self.state)
        sources = []
        current = datetime.now(timezone.utc)
        for row in health(self.store):
            due = not row['next_allowed_at'] or datetime.fromisoformat(row['next_allowed_at']) <= current
            setup = row.get('platform_setup', {}).get('missing_configuration', [])
            state_name = ('scanning' if state['current_source'] == row['id'] else
                          'needs_setup' if setup else 'paused' if not config['enabled'] or not row['approved'] else
                          'cooldown' if not due else 'queued')
            metrics = row['last_metrics']
            sources.append({'id': row['id'], 'label': LABELS.get(row['id'], row['id']), 'state': state_name,
                            'health': row['health'], 'approved': bool(row['approved']), 'error': row['last_error'],
                            'last_completed_at': row['last_completed_at'], 'next_allowed_at': row['next_allowed_at'],
                            'new_jobs': metrics.get('new_unique_jobs', 0), 'invalid': metrics.get('invalid', 0)})
        return {'available': True, 'enabled': config['enabled'], **state, 'sources': sources,
                'legacy_restore': self.legacy_restore, 'legacy_restore_error': self.legacy_restore_error,
                'has_profile': bool(self.store.profile(self.profile_id).get('skills')),
                'total_jobs': self.store.summary(self.profile_id)['total_jobs'],
                'scope': 'Original configured JobSpy searches: Egypt, Oman, UAE, Germany, Switzerland, Austria and remote; English/German. Public remote feeds also run automatically. Provider access may fail; see each source. Approved custom sources join automatically. '
                         'Account-dependent channels need setup; no paid access is added. Runs only while this server is running.'}

    def cycle(self):
        with self.control:
            with self.store.connect() as db: _, config = _read(db, self.profile_id)
            if not config['enabled'] or self.closed.is_set(): self._state(phase='paused'); return
            self.cancel.clear()
        self._state(phase='scanning', error='')
        # Re-read each source immediately before scanning; another source/process may consume its provider gate.
        rows = [x for x in health(self.store) if x['approved']]
        order = list(LABELS)
        rows.sort(key=lambda x: (datetime.fromisoformat(x['last_run']) if x['last_run'] else datetime.min.replace(tzinfo=timezone.utc),
                                order.index(x['id']) if x['id'] in order else len(order), x['id']))
        ids = [x['id'] for x in rows]
        attempted = 0
        for identity in ids:
            with self.store.connect() as db: _, current_config = _read(db, self.profile_id)
            if not current_config['enabled'] or self.cancel.is_set() or self.closed.is_set(): break
            row = next((x for x in health(self.store) if x['id'] == identity), None)
            if not row or not row['approved'] or row.get('platform_setup', {}).get('missing_configuration'): continue
            if row['next_allowed_at'] and datetime.fromisoformat(row['next_allowed_at']) > datetime.now(timezone.utc): continue
            if attempted >= 10: break
            self._state(current_source=identity)
            try:
                # Expired public cursors cannot be resumed. Restart a due pass,
                # retaining all jobs and every approval/cooldown/provider gate.
                if identity == 'jobicy:remote':
                    with self.store.connect() as db:
                        checkpoint = db.execute('SELECT data FROM source_checkpoints WHERE source_id=?', (identity,)).fetchone()
                    checkpoint = json.loads(checkpoint[0]) if checkpoint else {}
                    if checkpoint.get('cursor') and not checkpoint.get('complete') and time.time()-checkpoint.get('started',time.time()) >= 86400:
                        from .source_health import reset
                        reset(self.store, identity)
                scan(self.store, identity, cancel_event=_Cancellation(self), profile_id=self.profile_id)
                self._match_if_needed()
            except ValueError:
                pass  # Structured per-source health explains failures. One failure never blocks other feeds.
            finally:
                attempted += 1; self._state(current_source='')
        if not self.cancel.is_set(): self._match_if_needed()
        self._state(phase='paused' if self.cancel.is_set() else 'waiting', last_cycle=now())

    def _match_if_needed(self):
        p = self.store.profile(self.profile_id)
        summary = self.store.summary(self.profile_id)
        if (p.get('skills') or p.get('facts') or p.get('matching') or p.get('excluded_title_terms')) and summary['matched_jobs'] < summary['total_jobs']:
            self.store.evaluate(self.profile_id)

    def _loop(self):
        identity = sha256(self.profile_id.encode()).hexdigest()[:16]
        owner = FileLock(str(self.store.path)+'.automatic-'+identity+'.lock', timeout=0)
        while not self.closed.is_set():
            self.wake.clear()
            try:
                with owner: self.cycle()
            except Timeout:
                self._state(phase='waiting', error='Another server is checking this workspace; scan locks and cooldowns remain active.')
            except Exception:
                # Do not put raw exceptions, provider bodies or private profile values into the UI/log.
                self._state(phase='error', current_source='', error='Automatic discovery could not complete. Existing data is preserved; inspect source health.')
            self.wake.wait(self.interval)
