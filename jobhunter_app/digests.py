"""Explicit manual digest delivery; previews never contact Telegram."""
import hashlib
import json
import math
import os
import re
from datetime import datetime,timedelta,timezone
from filelock import FileLock
from .store import now
from .workflow import settings,report
from .followups import digest


def destination():
    chat=os.environ.get('TELEGRAM_CHAT_ID','')
    if not chat:return None
    if len(chat)>200 or any(ord(c)<33 for c in chat):raise ValueError('Invalid Telegram destination configuration')
    return 'telegram:'+hashlib.sha256(chat.encode()).hexdigest()[:16]


def bot_key():
    token=os.environ.get('TELEGRAM_BOT_TOKEN','')
    return 'telegram-bot:'+hashlib.sha256(token.encode()).hexdigest()[:24] if token else None


def preview(store,profile_id='default',today=None):
    config=settings(store,profile_id)
    inbox=digest(store,profile_id,today,config['days'],limit=1000)
    stats=report(store,profile_id,inbox['today'])
    # Use SQL filtering, not the first 200 jobs or status changes inferred from notes.
    with store.connect() as db:
        matches=[]
        for row in db.execute('''SELECT j.id,j.title,j.company,j.url,m.data FROM jobs j JOIN matches m ON m.job_id=j.id AND m.profile_id=?
         LEFT JOIN applications a ON a.job_id=j.id AND a.profile_id=m.profile_id
         WHERE COALESCE(a.status,'discovered') IN ('discovered','saved','reviewing','preparing','ready') ORDER BY j.id''',(profile_id,)):
            data=json.loads(row['data']);score=data.get('score_percent')
            if type(score) in (int,float) and 0<=score<=100 and math.isfinite(score) and score>=config['threshold'] and data.get('eligibility')!='excluded_by_config':
                matches.append({k:row[k] for k in ('id','title','company','url')})
    text=(f'JobHunter · {inbox["today"]}\nManual local digest; no application is sent.\n'
          f'Due through {inbox["through"]}: {inbox["total"]} items '
          f'({inbox["counts"]["overdue"]} overdue, {inbox["counts"]["today"]} today, {inbox["counts"]["upcoming"]} upcoming).\n'
          f'{len(matches)} active jobs at or above {config["threshold"]}% configured skill mentions; not eligibility scores.\n'
          f'{stats["currently_applied"]} currently marked applied; {stats["ever_marked_applied"]} ever marked applied by you.')
    if inbox['invalid_dates']:text+=f'\nWarning: {inbox["invalid_dates"]} invalid stored dates omitted; inspect the local inbox.'
    details=0;seen=set();omitted=0
    if config['include_job_details']:
        candidates=[{'id':r['job_id'],'title':r['job_title'],'company':r['company'],'url':r['url']} for r in inbox['items']]+matches
        for job in candidates:
            if job['id'] in seen:continue
            seen.add(job['id'])
            if details>=config['max_items']:omitted+=1;continue
            item='\n\n'+job['title'][:120]+' — '+job['company'][:120]+'\n'+job['url']
            if len(text)+len(item)>3300:omitted+=1;continue
            text+=item;details+=1
        text+=f'\n\nJob details shown: {details}; other items may exist. Open the local inbox for all items.'
    else:text+='\nCounts only. Job titles, employers, URLs, notes and candidate evidence are not included.'
    channel=destination()
    payload=json.dumps({'profile':profile_id,'channel':channel,'bot':bot_key(),'settings':config,'text':text},sort_keys=True,ensure_ascii=False)
    fingerprint=hashlib.sha256(payload.encode()).hexdigest()
    return {'today':inbox['today'],'through':inbox['through'],'message':text,'fingerprint':fingerprint,
            'destination_fingerprint':channel,'destination_configured':bool(channel),'sender_configured':bool(re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]+',os.environ.get('TELEGRAM_BOT_TOKEN',''))),'enabled':config['enabled'],
            'include_job_details':config['include_job_details'],'details_shown':details,'detail_items_omitted_from_selection':omitted,
            'counts':{'invalid_dates':inbox['invalid_dates'],'due_items':inbox['total'],'matching_active_jobs':len(matches),'currently_applied':stats['currently_applied']},
            'notice':'Preview only. Sending requires this current fingerprint and explicit confirmation. No notes, custom follow-up titles, CV content or candidate facts are sent. Manual local-date snapshot; no background scheduler. A configured destination is not verified ownership or a live delivery test.'}


def retry_seconds(value):
    if isinstance(value,str):
        try:value=float(value)
        except ValueError:
            try:
                from email.utils import parsedate_to_datetime
                parsed=parsedate_to_datetime(value)
                if parsed.tzinfo is None:parsed=parsed.replace(tzinfo=timezone.utc)
                value=(parsed-datetime.now(timezone.utc)).total_seconds()
            except (ValueError,TypeError,OverflowError):value=60
    if type(value) not in (int,float) or not 0<=value<=604800:
        return 604801 if type(value) in (int,float) and value>604800 else 60
    return max(60,int(math.ceil(value)))


def telegram_digest_send(text):
    """One bounded official POST. Sanitized result only; no raw exception surfaces."""
    token=os.environ.get('TELEGRAM_BOT_TOKEN','');chat=os.environ.get('TELEGRAM_CHAT_ID','')
    if not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]+',token) or not destination():raise ValueError('Configure TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID locally')
    from urllib.request import Request,build_opener
    from urllib.error import HTTPError
    from .sources import NoRedirect
    request=Request('https://api.telegram.org/bot'+token+'/sendMessage',data=json.dumps({'chat_id':chat,'text':text,'disable_web_page_preview':True}).encode(),headers={'Content-Type':'application/json'},method='POST')
    try:
        with build_opener(NoRedirect()).open(request,timeout=15) as response:
            raw=response.read(65537)
            if len(raw)>65536:return {'delivered':False,'status':'invalid_response'}
            value=json.loads(raw)
            return {'delivered':response.status==200 and value.get('ok') is True,'status':'delivered' if response.status==200 and value.get('ok') is True else 'rejected'}
    except HTTPError as error:
        retry=0
        if error.code==429:
            try:retry=json.loads(error.read(65536)).get('parameters',{}).get('retry_after',0)
            except Exception:pass
            retry=max(retry_seconds(retry),retry_seconds(error.headers.get('Retry-After','60') if error.headers else 60))
        error.close()
        return {'delivered':False,'status':'rate_limited' if error.code==429 else 'authorization_failed' if error.code in (401,403) else 'provider_error','retry_after':retry}
    except Exception:return {'delivered':False,'status':'delivery_unconfirmed'}


def send(store,fingerprint,confirmed=False,profile_id='default',today=None,sender=None):
    if confirmed is not True or not isinstance(fingerprint,str) or not re.fullmatch('[0-9a-f]{64}',fingerprint):raise ValueError('Explicit confirmation of a current digest preview is required')
    if sender is None and not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]+',os.environ.get('TELEGRAM_BOT_TOKEN','')):raise ValueError('Configure TELEGRAM_BOT_TOKEN locally first')
    sender=sender or telegram_digest_send
    with FileLock(str(store.path)+'.notify.lock',timeout=0):
        view=preview(store,profile_id,today);channel=view['destination_fingerprint']
        if view['fingerprint']!=fingerprint:raise ValueError('Digest or destination changed; preview again before confirming')
        if not view['enabled']:raise ValueError('Enable manual digests in workflow preferences first')
        if not channel:raise ValueError('Configure a Telegram destination locally first')
        with store.connect() as db:
            if db.execute('SELECT 1 FROM digest_deliveries WHERE profile_id=? AND channel=? AND fingerprint=?',(profile_id,channel,fingerprint)).fetchone():return {'status':'already_delivered','sent':0}
            row=db.execute('SELECT MAX(not_before) FROM notification_gates WHERE channel IN (?,?)',(channel,bot_key())).fetchone()
            if row and row[0] and row[0]>now():return {'status':'retry_later','sent':0,'not_before':row[0]}
        try:result=sender(view['message'])
        except Exception:result={'delivered':False,'status':'delivery_unconfirmed'}
        if not isinstance(result,dict) or type(result.get('delivered')) is not bool:result={'delivered':False,'status':'invalid_response'}
        success=result['delivered'];status='delivered' if success else result.get('status')
        if status not in {'delivered','invalid_response','rejected','rate_limited','authorization_failed','provider_error','delivery_unconfirmed'}:status='delivery_unconfirmed'
        with store.connect() as db:
            if success:db.execute('INSERT OR IGNORE INTO digest_deliveries VALUES(?,?,?,?)',(profile_id,channel,fingerprint,now()))
            elif status=='rate_limited':
                retry=result.get('retry_after',60)
                if type(retry) not in (int,float) or not 0<=retry<=604800:
                    until=datetime.max.replace(tzinfo=timezone.utc).isoformat() if type(retry) in (int,float) and retry>604800 else (datetime.now(timezone.utc)+timedelta(seconds=60)).isoformat()
                else:until=(datetime.now(timezone.utc)+timedelta(seconds=max(60,int(retry)))).isoformat()
                for key in {channel,bot_key()}-{None}:
                    db.execute('INSERT INTO notification_gates VALUES(?,?) ON CONFLICT(channel) DO UPDATE SET not_before=MAX(not_before,excluded.not_before)',(key,until))
            store.audit(db,'manual_digest_delivery',{'profile_id':profile_id,'status':status,'fingerprint':fingerprint})
        return {'status':status,'sent':int(success),'notice':'No automatic retry. Unconfirmed delivery may have reached Telegram; check the destination before retrying. A process interruption after provider success but before the local commit can also cause duplicates.'}
