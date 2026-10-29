"""Bounded read-only official post APIs. No account discovery or token issuance."""
import json
import os
import re
from urllib.parse import urlencode, urlsplit, parse_qs, quote
from urllib.error import HTTPError
from .collection import Collection

KINDS = ('linkedin','x','reddit','telegram','discord')
DOCS = {
 'linkedin':'https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api',
 'x':'https://docs.x.com/x-api/posts/timelines/introduction',
 'reddit':'https://www.reddit.com/dev/api/',
 'telegram':'https://core.telegram.org/bots/api#getupdates',
 'discord':'https://docs.discord.com/developers/resources/message',
}
HINTS = {'linkedin':'Authorized organization numeric ID','x':'Authorized public user numeric ID',
 'reddit':'Approved subreddit name, without r/','telegram':'channels (dedicated bot + public-channel allowlist)',
 'discord':'Authorized guildID-channelID (numeric IDs)'}
REQUIRED = {'linkedin':('JOBHUNTER_LINKEDIN_TOKEN','JOBHUNTER_LINKEDIN_VERSION','JOBHUNTER_LINKEDIN_ACCESS_APPROVED'),
 'x':('JOBHUNTER_X_BEARER','JOBHUNTER_X_ACCESS_APPROVED','JOBHUNTER_X_COST_APPROVED'),
 'reddit':('JOBHUNTER_REDDIT_TOKEN','JOBHUNTER_REDDIT_USER_AGENT','JOBHUNTER_REDDIT_API_APPROVED'),
 'telegram':('JOBHUNTER_TELEGRAM_READ_BOT_TOKEN','JOBHUNTER_TELEGRAM_CHANNELS','JOBHUNTER_TELEGRAM_DEDICATED_BOT'),
 'discord':('JOBHUNTER_DISCORD_BOT_TOKEN','JOBHUNTER_DISCORD_ACCESS_APPROVED')}

class SetupRequired(ValueError):
    pass

def validate_identifier(kind, value):
    patterns={'linkedin':r'[1-9][0-9]{0,19}','x':r'[1-9][0-9]{0,19}',
      'reddit':r'[A-Za-z0-9_]{3,21}','telegram':r'channels','discord':r'[1-9][0-9]{0,19}-[1-9][0-9]{0,19}'}
    if not isinstance(value,str) or not re.fullmatch(patterns[kind],value):
        raise ValueError(HINTS[kind])

def setup(kind):
    missing=[k for k in REQUIRED[kind] if not os.environ.get(k)]
    flags=[k for k in REQUIRED[kind] if k.endswith(('APPROVED','DEDICATED_BOT'))]
    missing += [k for k in flags if os.environ.get(k) and os.environ[k]!='1']
    return {'state':'setup_required' if missing else 'configured_not_live_verified',
      'required_environment':list(REQUIRED[kind]),'missing_configuration':list(dict.fromkeys(missing)),
      'identifier_hint':HINTS[kind],'live_verified':False,
      'scope':'Explicitly registered authorized source only; not all platform posts or memberships.'}

def _env(name,pattern=r'[!-~]{1,2000}'):
    value=os.environ.get(name,'')
    if not re.fullmatch(pattern,value):raise SetupRequired('Missing/invalid local setting: '+name)
    return value

def _cursor(value, pattern=r'[A-Za-z0-9_-]{1,500}'):
    if not isinstance(value,str) or not re.fullmatch(pattern,value):raise ValueError('Invalid platform pagination cursor')
    return value

def _num(value):
    if not isinstance(value,str) or not re.fullmatch(r'[1-9][0-9]{0,19}',value):raise ValueError('Invalid platform post identifier')
    return value

def validate_request_scope(kind,url,headers):
    """Called by network.get before attaching any service credentials."""
    p=urlsplit(url)
    patterns={
      'linkedin':('api.linkedin.com',r'/rest/posts',{'Authorization','Linkedin-Version','X-Restli-Protocol-Version','X-RestLi-Method'}),
      'x':('api.x.com',r'/2/users/[1-9][0-9]{0,19}/tweets',{'Authorization'}),
      'reddit':('oauth.reddit.com',r'/r/[A-Za-z0-9_]{3,21}/new',{'Authorization','User-Agent'}),
      'telegram':('api.telegram.org',r'/bot[0-9]{5,20}:[A-Za-z0-9_-]{20,100}/getUpdates',set()),
      'discord':('discord.com',r'/api/v10/channels/[1-9][0-9]{0,19}/messages',{'Authorization'}),
    }
    if kind not in patterns:raise ValueError('Unknown credential scope')
    host,path,keys=patterns[kind]
    if p.scheme!='https' or p.netloc!=host or p.fragment or not re.fullmatch(path,p.path) or set(headers)!=keys:
        raise ValueError('Platform credentials restricted to its documented read endpoint')
    if any(not isinstance(v,str) or not re.fullmatch(r'[ -~]{1,2200}',v) for v in headers.values()):
        raise ValueError('Invalid platform credential header')
    if 'Authorization' in keys and not headers['Authorization'].startswith('Bot ' if kind=='discord' else 'Bearer '):
        raise ValueError('Invalid platform authorization scheme')
    if kind=='linkedin' and (not re.fullmatch(r'20[0-9]{2}(?:0[1-9]|1[0-2])',headers['Linkedin-Version']) or headers['X-Restli-Protocol-Version']!='2.0.0' or headers['X-RestLi-Method']!='FINDER'):
        raise ValueError('Invalid LinkedIn API version/protocol')

def collect(source,checkpoint=None,cancel_event=None):
    from .network import get
    kind=source.kind; ident=source.identifier;validate_identifier(kind,ident)
    readiness=setup(kind)
    if readiness['missing_configuration']:
        raise SetupRequired('Configure authorized post access locally: '+', '.join(readiness['missing_configuration']))
    if cancel_event and cancel_event.is_set():raise InterruptedError('Collection cancelled')
    state=checkpoint or {}
    if not isinstance(state,dict):raise ValueError('Invalid platform checkpoint')
    page_index=state.get('page_index',1)
    if type(page_index) is not int or not 1<=page_index<=100:raise ValueError('Platform page bound reached; review/reset explicitly')
    cursor=state.get('cursor');params={};headers={};allowed=None
    if cursor is not None:_cursor(cursor)
    if kind=='x':
        url='https://api.x.com/2/users/'+ident+'/tweets';params={'max_results':50,'exclude':'retweets,replies','tweet.fields':'created_at'}
        if cursor:params['pagination_token']=cursor
        headers={'Authorization':'Bearer '+_env('JOBHUNTER_X_BEARER')}
    elif kind=='reddit':
        url='https://oauth.reddit.com/r/'+ident+'/new';params={'limit':50,'raw_json':1}
        if cursor:params['after']=_cursor(cursor,r't3_[A-Za-z0-9]{1,30}')
        headers={'Authorization':'Bearer '+_env('JOBHUNTER_REDDIT_TOKEN'),'User-Agent':_env('JOBHUNTER_REDDIT_USER_AGENT',r'[ -~]{1,200}')}
    elif kind=='linkedin':
        url='https://api.linkedin.com/rest/posts';params={'author':'urn:li:organization:'+ident,'q':'author','count':50,'sortBy':'LAST_MODIFIED','start':int(cursor or 0)}
        if not str(params['start']).isdigit() or not 0<=params['start']<=5000:raise ValueError('LinkedIn page bound reached; review/reset explicitly')
        headers={'Authorization':'Bearer '+_env('JOBHUNTER_LINKEDIN_TOKEN'),'Linkedin-Version':_env('JOBHUNTER_LINKEDIN_VERSION',r'20[0-9]{2}(?:0[1-9]|1[0-2])'),'X-Restli-Protocol-Version':'2.0.0','X-RestLi-Method':'FINDER'}
    elif kind=='discord':
        guild,channel=ident.split('-');url='https://discord.com/api/v10/channels/'+channel+'/messages';params={'limit':50}
        if cursor:params['before']=_num(cursor)
        headers={'Authorization':'Bot '+_env('JOBHUNTER_DISCORD_BOT_TOKEN')}
    else:
        allowed=set(_env('JOBHUNTER_TELEGRAM_CHANNELS',r'[A-Za-z0-9_,]{5,1000}').lower().split(','))
        if not all(re.fullmatch(r'[a-z][a-z0-9_]{4,31}',v) for v in allowed):raise SetupRequired('JOBHUNTER_TELEGRAM_CHANNELS must contain explicit public channel usernames without @')
        token=_env('JOBHUNTER_TELEGRAM_READ_BOT_TOKEN',r'[0-9]{5,20}:[A-Za-z0-9_-]{20,100}')
        url='https://api.telegram.org/bot'+token+'/getUpdates';params={'limit':50,'timeout':0,'allowed_updates':json.dumps(['channel_post','edited_channel_post'],separators=(',',':'))}
        if cursor:params['offset']=_num(cursor)
    url+='?'+urlencode(params)
    body,typ=get(url,credentials=headers,credential_scope=kind)
    if 'json' not in typ:raise ValueError('Expected platform JSON, not a challenge page')
    try:data=json.loads(body)
    except (ValueError,UnicodeError):raise ValueError('Malformed platform JSON') from None
    rows=[];next_cursor=None;unreadable=0;filtered=0
    def row(text,origin,published=''):
        nonlocal unreadable
        if not isinstance(text,str):raise ValueError('Malformed platform post text')
        unavailable=not text.strip()
        if unavailable:unreadable+=1;text='Non-text post or content unavailable; manual inspection required.'
        rows.append({'body':text,'origin_url':origin,'source_label':kind+':'+ident,'published':str(published)[:200],
          'content_unavailable':unavailable})
    if kind=='x':
        if not isinstance(data,dict) or data.get('errors'):raise ValueError('X API returned errors; checkpoint not advanced')
        meta=data.get('meta')
        if not isinstance(meta,dict) or type(meta.get('result_count')) is not int:raise ValueError('Unexpected X metadata')
        entries=data.get('data',[])
        if not isinstance(entries,list) or len(entries)>50 or meta['result_count']!=len(entries):raise ValueError('Unexpected X page/result count')
        for p in entries:row(p['text'],'https://x.com/i/web/status/'+_num(p['id']),p.get('created_at',''))
        next_cursor=data.get('meta',{}).get('next_token')
    elif kind=='reddit':
        root=data.get('data') if isinstance(data,dict) else None
        if not isinstance(root,dict) or not isinstance(root.get('children'),list) or len(root['children'])>50:raise ValueError('Unexpected Reddit listing')
        for p in root['children']:
            if p.get('kind')!='t3':raise ValueError('Expected Reddit submissions only')
            p=p['data']
            if p.get('subreddit','').casefold()!=ident.casefold():raise ValueError('Reddit scope mismatch')
            if p.get('removed_by_category') or p.get('selftext') in ('[removed]','[deleted]'):filtered+=1;continue
            post_id=_cursor(p['id'],r'[A-Za-z0-9]{1,30}')
            row(p.get('title','')+'\n'+p.get('selftext',''),'https://www.reddit.com/r/'+ident+'/comments/'+post_id+'/',p.get('created_utc',''))
        next_cursor=root.get('after')
    elif kind=='linkedin':
        entries=data.get('elements') if isinstance(data,dict) else None
        if not isinstance(entries,list) or len(entries)>50:raise ValueError('Unexpected LinkedIn posts page')
        for p in entries:
            if p.get('author')!='urn:li:organization:'+ident:raise ValueError('LinkedIn author scope mismatch')
            if p.get('visibility')!='PUBLIC' or p.get('lifecycleState')!='PUBLISHED':filtered+=1;continue
            if not re.fullmatch(r'urn:li:(?:share|ugcPost):[0-9]{1,20}',p.get('id','')):raise ValueError('Unexpected LinkedIn post identifier')
            row(p.get('commentary',''),'https://www.linkedin.com/feed/update/'+p['id']+'/',p.get('publishedAt',''))
        # Follow only a provider-supplied next index; do not manufacture continuation from page length.
        links=data.get('paging',{}).get('links',[])
        if not isinstance(links,list):raise ValueError('Invalid LinkedIn pagination')
        for link in links:
            if link.get('rel')=='next':
                p=urlsplit(link.get('href',''))
                if p.scheme!='https' or p.netloc!='api.linkedin.com' or p.path!='/rest/posts':raise ValueError('Unsafe LinkedIn next link')
                q=parse_qs(p.query)
                if q.get('author')!=['urn:li:organization:'+ident] or len(q.get('start',[]))!=1:raise ValueError('LinkedIn next scope mismatch')
                candidate=_cursor(q['start'][0],r'[0-9]{1,4}')
                if not int(cursor or 0)<int(candidate)<=5000:raise ValueError('Invalid LinkedIn next index')
                if next_cursor and next_cursor!=candidate:raise ValueError('Ambiguous LinkedIn next index')
                next_cursor=candidate
    elif kind=='discord':
        if not isinstance(data,list) or len(data)>50:raise ValueError('Unexpected Discord messages page')
        for p in data:
            if p.get('channel_id')!=channel or (p.get('guild_id') and p['guild_id']!=guild):raise ValueError('Discord channel scope mismatch')
            row(p.get('content',''),'https://discord.com/channels/'+guild+'/'+channel+'/'+_num(p['id']),p.get('timestamp',''))
        if len(data)==50:next_cursor=str(min(int(_num(p['id'])) for p in data))
    else:
        if not isinstance(data,dict) or data.get('ok') is not True:
            code=data.get('error_code') if isinstance(data,dict) else None
            if code in (401,403,429):
                retry=str(data.get('parameters',{}).get('retry_after',''))[:200]
                raise HTTPError('https://api.telegram.org/[redacted]',code,'Bot API rejected',{'Retry-After':retry},None)
            raise ValueError('Telegram bot API error; dedicated bot must not have an active webhook')
        updates=data.get('result')
        if not isinstance(updates,list) or len(updates)>50:raise ValueError('Unexpected Telegram update page')
        ids=[]
        for update in updates:
            uid=update.get('update_id')
            if type(uid) is not int or uid<0:raise ValueError('Invalid Telegram update identifier')
            ids.append(uid)
            p=update.get('channel_post') or update.get('edited_channel_post');chat=p.get('chat',{}) if isinstance(p,dict) else {}
            name=chat.get('username','').lower()
            if chat.get('type')!='channel' or name not in allowed:filtered+=1;continue
            row(p.get('text') or p.get('caption',''),'https://t.me/'+name+'/'+_num(str(p['message_id'])),p.get('date',''))
        next_cursor=str(max(ids)+1) if ids else cursor
    if next_cursor is not None:
        _cursor(next_cursor)
        if next_cursor==cursor and (kind!='telegram' or rows):raise ValueError('Repeated platform cursor; checkpoint not advanced')
        if cursor and kind in ('discord','telegram'):
            if (kind=='discord' and int(next_cursor)>=int(cursor)) or (kind=='telegram' and int(next_cursor)<int(cursor)):raise ValueError('Non-monotonic platform cursor; checkpoint not advanced')
    next_index=page_index+1 if next_cursor and kind!='telegram' else 1
    if next_index>100:raise ValueError('100-page platform bound reached; review/reset explicitly')
    return Collection(rows,{'cursor':next_cursor,'page_index':next_index}, {'requests':1,'transport':'official_api','platform':kind,
      'coverage_complete':False,'bounded_selection':len(updates)==50 if kind=='telegram' else bool(next_cursor),'page_exhausted':len(updates)<50 if kind=='telegram' else not bool(next_cursor),
      'live_verified':False,'non_text_or_unavailable':unreadable,'filtered_out_of_scope_or_removed':filtered,
      'source_scope':'One explicitly approved source, one page of at most 50 posts; not whole-platform coverage.'},True)
