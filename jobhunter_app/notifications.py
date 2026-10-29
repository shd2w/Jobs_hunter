"""Explicit, deduplicated manual Telegram notifications. No candidate facts sent."""
from __future__ import annotations
import hashlib
from html import escape
import json
import os
import urllib.request
from filelock import FileLock
from .store import now


def telegram_send(text: str) -> bool:
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
    if not token or not chat_id:
        raise ValueError('Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID explicitly in the environment')
    import re
    if not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]+', token):
        raise ValueError('Invalid Telegram token format')
    request = urllib.request.Request('https://api.telegram.org/bot'+token+'/sendMessage',
        data=json.dumps({'chat_id': chat_id, 'text': text[:3800], 'parse_mode':'HTML', 'disable_web_page_preview':True}).encode(),
        headers={'Content-Type':'application/json'}, method='POST')
    # No retry loop or raw exception logging: request URLs contain a secret.
    from .sources import NoRedirect
    opener=urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(request, timeout=15) as response:
            data=response.read(65536)
            return response.status==200 and json.loads(data).get('ok') is True
    except Exception:
        return False


def notify(store, threshold=60, profile_id='default', sender=telegram_send, channel=None):
    if type(threshold) not in (int,float) or not 0 <= threshold <= 100:
        raise ValueError('Notification threshold must be 0–100 skill-mention percent')
    if channel is None:
        chat_id=os.environ.get('TELEGRAM_CHAT_ID','')
        if not chat_id:
            raise ValueError('Set TELEGRAM_CHAT_ID for a configured destination')
        channel='telegram:'+hashlib.sha256(chat_id.encode()).hexdigest()[:16]
    result={'sent':0,'failed':0,'already_delivered':0,'below_threshold_or_unmatched':0}
    with FileLock(str(store.path)+'.notify.lock',timeout=0):
        with store.connect() as db:
            from .digests import bot_key
            gate=db.execute('SELECT MAX(not_before) FROM notification_gates WHERE channel IN (?,?)',(channel,bot_key())).fetchone()
        if gate and gate[0] and gate[0]>now():return {**result,'status':'retry_later','not_before':gate[0]}
        offset=0
        while True:
            jobs=store.jobs(profile_id=profile_id,limit=1000,offset=offset)
            for job in jobs:
                match=job.get('match') or {}
                score=match.get('score_percent')
                if score is None or score<threshold or match.get('eligibility')=='excluded_by_config' or job['status'] in ('applied','rejected','withdrawn','archived'):
                    result['below_threshold_or_unmatched']+=1;continue
                text=(f'<b>{escape(job["title"])}</b> — {escape(job["company"])}\n'
                      f'{score}% configured skill mentions (not an eligibility assessment).\n'
                      f'{escape(job["url"])}\nReview and apply manually.')[:3800]
                fingerprint=hashlib.sha256(text.encode()).hexdigest()
                with store.connect() as db:
                    exists=db.execute('SELECT 1 FROM notification_deliveries WHERE profile_id=? AND job_id=? AND channel=? AND fingerprint=?',
                        (profile_id,job['id'],channel,fingerprint)).fetchone()
                if exists:
                    result['already_delivered']+=1;continue
                try: delivered=sender(text) is True
                except Exception: delivered=False
                if delivered:
                    with store.connect() as db:
                        db.execute('INSERT OR IGNORE INTO notification_deliveries VALUES(?,?,?,?,?)',
                            (profile_id,job['id'],channel,fingerprint,now()))
                    result['sent']+=1
                else: result['failed']+=1
            if len(jobs)<1000:break
            offset+=len(jobs)
        with store.connect() as db: store.audit(db,'manual_notifications',result)
    return result
