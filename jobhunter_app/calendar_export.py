"""Private, local all-day iCalendar snapshots. No calendar account or network."""
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import re
import unicodedata
from .followups import calendar_day

VERSION = 'calendar-snapshot-1'
MAX_EVENTS = 1000
MAX_BYTES = 8 * 1024 * 1024


def _window(start, days, past_days, include_job_details):
    reference = calendar_day(start) if start is not None else date.today()
    if type(days) is not int or not 0 <= days <= 365:
        raise ValueError('Calendar days must be 0–365')
    if type(past_days) is not int or not 0 <= past_days <= 365:
        raise ValueError('Calendar past days must be 0–365')
    if type(include_job_details) is not bool:
        raise ValueError('Calendar job-detail choice must be an explicit boolean')
    try:
        first, last = reference - timedelta(days=past_days), reference + timedelta(days=days)
    except OverflowError:
        raise ValueError('Calendar date window is out of range') from None
    return reference, first, last


def _text(value):
    # Strip forbidden controls, normalize line endings and escape RFC 5545 TEXT.
    text = str(value).replace('\r\n', '\n').replace('\r', '\n')
    text = ''.join(c for c in text if c == '\n' or unicodedata.category(c) != 'Cc')
    return text.replace('\\', '\\\\').replace('\n', '\\n').replace(';', '\\;').replace(',', '\\,')


def _fold(line):
    chunks, chunk, size = [], '', 0
    for character in line:
        length = len(character.encode('utf-8'))
        if size + length > 75:
            chunks.append(chunk)
            chunk, size = ' ', 1
        chunk += character
        size += length
    chunks.append(chunk)
    return '\r\n'.join(chunks)


def _date(value):
    return f'{value.year:04d}{value.month:02d}{value.day:02d}'


def _render(events):
    stamp = datetime.now(timezone.utc)
    stamp_text = _date(stamp.date()) + f'T{stamp.hour:02d}{stamp.minute:02d}{stamp.second:02d}Z'
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//JobHunter//Manual Calendar 0.3.5b//EN', 'CALSCALE:GREGORIAN']
    for event in events:
        day = calendar_day(event['due'])
        lines.extend(['BEGIN:VEVENT', 'UID:' + event['uid'], 'DTSTAMP:' + stamp_text,
                      'DTSTART;VALUE=DATE:' + _date(day), 'DTEND;VALUE=DATE:' + _date(day + timedelta(days=1)),
                      'SUMMARY:' + _text(event['summary']), 'DESCRIPTION:' + _text(event['description']), 'TRANSP:TRANSPARENT', 'END:VEVENT'])
    lines.append('END:VCALENDAR')
    data = ('\r\n'.join(_fold(line) for line in lines) + '\r\n').encode('utf-8')
    return data


def _snapshot(store, profile_id, start, days, past_days, include_job_details):
    reference, first, last = _window(start, days, past_days, include_job_details)
    events, count, invalid, outside, unrepresentable = [], 0, 0, 0, 0
    # One read statement for reminder data. Never select private task titles/notes.
    with store.connect() as db:
        if not db.execute('SELECT 1 FROM profiles WHERE id=?', (profile_id,)).fetchone():
            raise ValueError('Configure a profile before calendar export')
        rows = db.execute('''SELECT 'deadline' kind,j.id id,a.deadline due,j.title,j.company,j.url
            FROM applications a JOIN jobs j ON j.id=a.job_id
            WHERE a.profile_id=? AND a.deadline<>'' AND a.status IN ('discovered','saved','reviewing','preparing','ready')
            UNION ALL SELECT 'followup',f.id,f.due,j.title,j.company,j.url
            FROM followups f JOIN jobs j ON j.id=f.job_id
            WHERE f.profile_id=? AND f.completed=0 ORDER BY due,kind,id''', (profile_id, profile_id))
        for row in rows:
            try:
                due = calendar_day(row['due'])
            except ValueError:
                invalid += 1
                continue
            if not first <= due <= last:
                outside += 1
                continue
            count += 1
            if due == date.max:
                unrepresentable += 1
            if len(events) >= MAX_EVENTS:
                continue
            uid = hashlib.sha256(json.dumps([profile_id, row['kind'], row['id']], ensure_ascii=False, separators=(',', ':')).encode()).hexdigest() + '@jobhunter.invalid'
            summary = 'Application deadline' if row['kind'] == 'deadline' else 'Personal follow-up'
            description = 'Manual JobHunter snapshot. Calendar day only; verify the original deadline. No application or employer message was sent.'
            if include_job_details:
                summary += ' — ' + row['title'] + ' — ' + row['company']
                description += '\nOriginal listing: ' + row['url']
            events.append({'uid': uid, 'kind': row['kind'], 'due': due.isoformat(), 'summary': summary, 'description': description})
    options = {'start': reference.isoformat(), 'from': first.isoformat(), 'through': last.isoformat(), 'days': days, 'past_days': past_days, 'include_job_details': include_job_details}
    counts = {'events_in_window': count, 'invalid_dates_omitted': invalid, 'outside_window_omitted': outside, 'unrepresentable_dates': unrepresentable}
    payload = json.dumps({'version': VERSION, 'profile': profile_id, 'options': options, 'counts': counts, 'events': events}, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    content = _render(events) if count <= MAX_EVENTS and unrepresentable == 0 else None
    oversized = content is not None and len(content) > MAX_BYTES
    metadata = {'version': VERSION, **options, **counts, 'can_export': count <= MAX_EVENTS and unrepresentable == 0 and not oversized, 'output_limit_exceeded': oversized,
                'output_bytes': len(content) if content is not None else None, 'max_bytes': MAX_BYTES,
                'max_events': MAX_EVENTS, 'fingerprint': hashlib.sha256(payload.encode()).hexdigest(),
                'sample': [{k: e[k] for k in ('kind', 'due', 'summary', 'description')} for e in events[:10]],
                'sample_limit': 10, 'sample_is_complete': count <= 10,
                'notice': 'Local iCalendar snapshot only, not calendar sync, an invitation or a timed closing-date guarantee. Generic summaries by default. Even with job details enabled, candidate evidence, CVs, application/task notes and custom task titles are excluded. Importing or saving this file in a synced calendar may share its contents with that service. Reimport/update/removal behavior depends on your calendar app; completed or rescheduled tasks are not automatically reconciled.'}
    return events, metadata, content


def preview(store, profile_id='default', start=None, days=30, past_days=0, include_job_details=False):
    return _snapshot(store, profile_id, start, days, past_days, include_job_details)[1]


def export(store, profile_id='default', start=None, days=30, past_days=0, include_job_details=False, fingerprint=None):
    if fingerprint is not None and (not isinstance(fingerprint, str) or not re.fullmatch('[0-9a-f]{64}', fingerprint)):
        raise ValueError('Invalid calendar preview fingerprint')
    events, metadata, content = _snapshot(store, profile_id, start, days, past_days, include_job_details)
    if fingerprint is not None and fingerprint != metadata['fingerprint']:
        raise ValueError('Calendar data or options changed; preview again before export')
    if metadata['events_in_window'] > MAX_EVENTS:
        raise ValueError('Calendar export exceeds 1,000 events; narrow the date window. No partial calendar was exported')
    if metadata['unrepresentable_dates']:
        raise ValueError('Calendar cannot represent an all-day end date beyond year 9999')
    if metadata['output_limit_exceeded']:
        raise ValueError('Calendar exceeds the 8-MiB output bound; narrow the date window')
    return content, metadata
