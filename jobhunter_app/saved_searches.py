"""Named local inbox filters, stored in the existing workflow JSON namespace."""
import json
import re
import uuid
from .store import STATES,dump,now

MAX_SEARCHES=20
KEY='saved_searches'

def _id(value):
    if not isinstance(value,str) or not re.fullmatch('[a-f0-9]{32}',value):raise ValueError('Invalid saved search ID')
    return value

def validate(value):
    if not isinstance(value,dict) or set(value)!={'name','query','status'}:raise ValueError('Use name, query and status only')
    name=value['name'];query=value['query'];status=value['status']
    if not isinstance(name,str) or not name.strip() or len(name.strip())>80 or any(ord(c)<32 or ord(c)==127 for c in name):raise ValueError('Search name must be 1–80 characters without control characters')
    if not isinstance(query,str) or len(query)>1000 or any(ord(c)<32 or ord(c)==127 for c in query):raise ValueError('Search keyword must be at most 1,000 characters without control characters')
    if not isinstance(status,str) or status not in ('',*STATES):raise ValueError('Unknown application status')
    return {'name':name.strip(),'query':query,'status':status}

def _read(db,profile_id):
    if not db.execute('SELECT 1 FROM profiles WHERE id=?',(profile_id,)).fetchone():raise ValueError('Configure a profile first')
    row=db.execute('SELECT data FROM workflow_settings WHERE profile_id=?',(profile_id,)).fetchone()
    data=json.loads(row[0]) if row else {}
    if not isinstance(data,dict):raise ValueError('Invalid workflow settings')
    items=data.get(KEY,[])
    if not isinstance(items,list) or len(items)>MAX_SEARCHES:raise ValueError('Invalid saved search collection')
    ids=set();names=set()
    for item in items:
        if not isinstance(item,dict) or set(item)!={'id','name','query','status'}:raise ValueError('Invalid stored saved search')
        _id(item['id']);validate({k:item[k] for k in ('name','query','status')})
        if item['id'] in ids or item['name'].casefold() in names:raise ValueError('Duplicate stored saved search')
        ids.add(item['id']);names.add(item['name'].casefold())
    return data,items

def listing(store,profile_id='default'):
    with store.connect() as db:return list(_read(db,profile_id)[1])

def save(store,value,profile_id='default',search_id=None):
    value=validate(value)
    if search_id is not None:_id(search_id)
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        data,items=_read(db,profile_id)
        if search_id is not None and not any(x['id']==search_id for x in items):raise ValueError('Saved search not found')
        if any(x['name'].casefold()==value['name'].casefold() and x['id']!=search_id for x in items):raise ValueError('A search with that name already exists')
        if search_id is None and len(items)>=MAX_SEARCHES:raise ValueError('At most 20 saved searches per profile')
        item={'id':search_id or uuid.uuid4().hex,**value}
        if search_id is None:items.append(item)
        else:items=[item if x['id']==search_id else x for x in items]
        data[KEY]=items
        db.execute('INSERT INTO workflow_settings VALUES(?,?,?) ON CONFLICT(profile_id) DO UPDATE SET data=excluded.data,updated_at=excluded.updated_at',(profile_id,dump(data),now()))
        store.audit(db,'saved_search_saved',{'profile_id':profile_id,'id':item['id']})
        return item

def delete(store,search_id,profile_id='default'):
    _id(search_id)
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE');data,items=_read(db,profile_id)
        if not any(x['id']==search_id for x in items):raise ValueError('Saved search not found')
        data[KEY]=[x for x in items if x['id']!=search_id]
        db.execute('UPDATE workflow_settings SET data=?,updated_at=? WHERE profile_id=?',(dump(data),now(),profile_id))
        store.audit(db,'saved_search_deleted',{'profile_id':profile_id,'id':search_id})
    return {'deleted':True}

def run(store,search_id,profile_id='default',offset=0):
    _id(search_id)
    item=next((x for x in listing(store,profile_id) if x['id']==search_id),None)
    if item is None:raise ValueError('Saved search not found')
    if type(offset) is not int or offset<0:raise ValueError('Invalid result offset')
    return {'search':item,'jobs':store.jobs(item['query'],item['status'],profile_id,limit=200,offset=offset),'offset':offset,'page_size':200}
