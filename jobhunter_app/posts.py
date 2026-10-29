"""Local source-backed post triage; automatic candidates are never human-verified."""
from __future__ import annotations
from contextlib import nullcontext
from hashlib import sha256
import json
import re
from .store import dump, now
from .validation import public_url, normalize_job

LABELS = {
 'title': r'role|job title|position|stelle|المسمى الوظيفي|الوظيفة',
 'company': r'company|employer|unternehmen|الشركة',
 'location': r'location|standort|الموقع',
 'salary': r'salary|gehalt|الراتب',
 'deadline': r'deadline|bewerbungsfrist|آخر موعد',
 'url': r'apply(?: here| now| online)?(?: at| via)?|apply link|application url|bewerbungslink|التقديم|رابط التقديم',
}
HIRING = re.compile(r'\b(hiring|vacancy|vacancies|job opening|we seek|gesucht|stellenangebot|wir suchen)\b|مطلوب|نوظف|فرصة عمل', re.I)
SEEKING = re.compile(r'\b(open to work|looking for (?:a |my )?(?:job|role|work)|seeking (?:a |an )?(?:job|role|opportunity)|suche (?:einen job|arbeit))\b|أبحث عن (?:عمل|وظيفة)', re.I)
URL = re.compile(r'https?://[^\s<>"\)\]]+', re.I)


def extract(body: str, title_hint='') -> dict:
    if not isinstance(body, str) or not body.strip() or len(body) > 100000 or '\x00' in body:
        raise ValueError('Post text must contain 1–100,000 characters')
    if not isinstance(title_hint, str) or len(title_hint) > 500:
        raise ValueError('Invalid title hint')
    fields, evidence, warnings = {}, {}, []
    for field, labels in LABELS.items():
        hits = list(re.finditer(r'^\s*(?:' + labels + r')\s*[:：]\s*(.+?)\s*$', body, re.I | re.M))
        if len(hits) == 1:
            hit = hits[0]
            value = hit.group(1).strip()
            if field == 'url':
                urls = URL.findall(value)
                value = urls[0].rstrip('.,;') if len(urls) == 1 else ''
                if value:
                    try: public_url(value)
                    except ValueError: value = ''
            if value:
                fields[field] = value
                evidence[field] = {'quote': hit.group(1), 'start': hit.start(1), 'end': hit.end(1), 'method': 'explicit_label'}
        elif len(hits) > 1:
            warnings.append(f'Multiple {field} values; select one role manually.')
    # Only accept an explicit, bounded hiring sentence; do not turn authors into employers.
    sentence = re.search(r"(?:we(?:’|')?re|we are) hiring\s+([^\n.!?]{2,160}?)\s+at\s+([^\n.!?]{2,160})(?=[\n.!?]|$)", body, re.I)
    if sentence:
        for field, group in (('title', 1), ('company', 2)):
            if field not in fields:
                fields[field] = sentence.group(group).strip()
                evidence[field] = {'quote': sentence.group(group), 'start': sentence.start(group), 'end': sentence.end(group), 'method': 'hiring_sentence'}
    hiring = bool(HIRING.search(body)) or bool(re.search(r'^\s*(?:' + LABELS['title'] + r')\s*[:：]', body, re.I | re.M))
    seeking = bool(SEEKING.search(body))
    classification = 'possible_vacancy' if hiring else 'not_identified_as_vacancy'
    if seeking:
        classification = 'ambiguous' if hiring else 'job_seeker_post'
        warnings.append('Job-seeker language detected; do not treat this as an employer vacancy without checking.')
    if re.search(r'applications? (?:are )?closed|position (?:is )?filled|expired|تم إغلاق|انتهى التقديم|stelle besetzt', body, re.I):
        warnings.append('Possible closed or expired vacancy; verify with the original source.')
    if re.search(r'pay (?:a |an )?(?:fee|deposit)|bank details|رسوم توظيف|بيانات بنكية', body, re.I):
        warnings.append('Potential fee or financial-information request; independently verify legitimacy.')
    deadline = fields.get('deadline', '')
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', deadline):
        from datetime import date
        try:
            if date.fromisoformat(deadline) < date.today(): warnings.append('Explicit ISO deadline is in the past; verify before proceeding.')
        except ValueError: warnings.append('Invalid explicit deadline; check the original source.')
    requirements = []
    for hit in re.finditer(r'^.*(?:\b(?:must|required|mandatory|preferred|nice to have|erforderlich|wünschenswert)\b|يشترط|مطلوب|يفضل).*$', body, re.I | re.M):
        quote = hit.group(0)
        category = 'preferred' if re.search(r'preferred|nice to have|wünschenswert|يفضل', quote, re.I) else 'requires_review'
        requirements.append({'quote': quote, 'start': hit.start(), 'end': hit.end(), 'category': category})
    if 'url' not in fields: warnings.append('No unambiguous labelled application URL; supply and verify one during review.')
    if not fields.get('company'): warnings.append('Employer unknown; the post author is not assumed to be the employer.')
    if title_hint: warnings.append('Feed title is a hint only, not a verified role or employer.')
    warnings.append('Rule-based extraction may miss negation, multiple roles, language nuances or eligibility restrictions.')
    result={'classification': classification, 'fields': fields, 'evidence': evidence,
            'requirements': requirements[:100], 'warnings': warnings, 'title_hint': title_hint}
    result['automation']=automation(body,result)
    return result


def stage(store, rows, rights_attested=False, dry_run=False, _db=None, _hiring_context=False, _decisions=False):
    if rights_attested is not True and not dry_run:
        raise ValueError('Confirm permission to store and process this supplied content; platform terms still apply')
    if not isinstance(rows, list) or not 1 <= len(rows) <= 500:
        raise ValueError('Supply 1–500 posts')
    report = {'received': len(rows), 'staged': 0, 'duplicates': 0, 'skipped': 0, 'invalid': 0, 'items': [], 'errors': [], 'dry_run': dry_run}
    with (nullcontext(_db) if _db is not None else store.connect()) as db:
        seen = set()
        for i, row in enumerate(rows):
            try:
                if not isinstance(row, dict): raise ValueError('Post must be an object')
                body = row.get('body')
                result = extract(body, row.get('title_hint', ''))
                if _hiring_context and result['classification']=='not_identified_as_vacancy':
                    result['classification']='ambiguous'
                    result['warnings'].append('Collected from a Who is hiring thread; context is not evidence that this individual comment offers a job.')
                    result['automation']={'decision':'review','reasons':['hiring_thread_context_only']}
                if row.get('content_unavailable') is True:
                    result['classification']='ambiguous'
                    result['automation']={'decision':'review','reasons':['non_text_or_content_unavailable']}
                origin = row.get('origin_url', '')
                if origin: origin = public_url(origin)
                label = row.get('source_label', 'Supplied post')
                if not isinstance(label, str) or not label.strip() or len(label) > 300: raise ValueError('Invalid source label')
                published = row.get('published', '')
                if not isinstance(published, str) or len(published) > 200: raise ValueError('Invalid publication value')
                result['published_raw'] = published
                digest = sha256(body.encode()).hexdigest()
                identity = sha256((origin + '\n' + digest).encode()).hexdigest()
                item = {'id': identity, **result}
                report['items'].append(item)
                if result['classification'] in ('not_identified_as_vacancy', 'job_seeker_post') or (_decisions and result['automation']['decision']=='skip'):
                    report['skipped'] += 1
                    continue
                present = identity in seen or db.execute('SELECT 1 FROM discovery_items WHERE id=?', (identity,)).fetchone()
                seen.add(identity)
                report['duplicates' if present else 'staged'] += 1
                if not dry_run:
                    db.execute('''INSERT INTO discovery_items VALUES(?,?,?,?,?,?,?,?,?)
                     ON CONFLICT(id) DO UPDATE SET last_seen=excluded.last_seen''',
                     (identity, origin, label, body, digest, dump(result), now(), now(), 'pending'))
            except (ValueError, TypeError) as exc:
                report['invalid'] += 1
                report['errors'].append({'row': i + 1, 'error': str(exc)})
        if not dry_run: store.audit(db, 'posts_staged', {k: v for k, v in report.items() if k not in ('items','errors')})
    return report


def listing(store, status='pending', offset=0):
    if status not in ('pending', 'accepted', 'dismissed', 'all'): raise ValueError('Invalid review status')
    if type(offset) is not int or offset < 0: raise ValueError('Invalid review offset')
    with store.connect() as db:
        rows = db.execute('SELECT id,origin_url,source_label,extracted,status,last_seen FROM discovery_items WHERE (?=\'all\' OR status=?) ORDER BY last_seen DESC,id LIMIT 100 OFFSET ?', (status, status, offset)).fetchall()
    return [{**dict(r), 'extracted': json.loads(r['extracted'])} for r in rows]


def detail(store, item_id):
    with store.connect() as db:
        row = db.execute('SELECT * FROM discovery_items WHERE id=?', (item_id,)).fetchone()
        if not row: raise ValueError('Unknown post')
        result = {**dict(row), 'extracted': json.loads(row['extracted'])}
        result['linked_jobs'] = [dict(r) for r in db.execute('SELECT j.id,j.title,j.company,j.url FROM jobs j JOIN job_origins o ON o.job_id=j.id WHERE o.item_id=?', (item_id,))]
        # Suggestions only: never merge on fuzzy title/company similarity.
        fields = result['extracted']['fields']
        result['possible_duplicates'] = [dict(r) for r in db.execute('SELECT id,title,company,url FROM jobs WHERE url=? OR (lower(title)=lower(?) AND lower(company)=lower(?)) LIMIT 20', (fields.get('url', ''), fields.get('title', ''), fields.get('company', '')))]
    return result


def accept(store, item_id, fields, confirmed=False, target_job_id=''):
    if confirmed is not True: raise ValueError('Explicit human review confirmation required')
    if not isinstance(item_id, str) or not isinstance(target_job_id, str): raise ValueError('Invalid review identifiers')
    job = normalize_job(fields)
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM discovery_items WHERE id=?', (item_id,)).fetchone()
        if not row: raise ValueError('Unknown post')
        existing = db.execute('SELECT id FROM jobs WHERE url=? UNION SELECT job_id AS id FROM job_aliases WHERE alias_url=?', (job['url'], job['url'])).fetchone()
        if target_job_id:
            target = db.execute('SELECT id FROM jobs WHERE id=?', (target_job_id,)).fetchone()
            if not target: raise ValueError('Unknown duplicate target')
            if existing and existing['id'] != target_job_id: raise ValueError('Application URL already belongs to a different job')
            job_id = target_job_id
        elif existing:
            job_id = existing['id']
        else:
            result = store.ingest([job], source='reviewed-post', _db=db)
            if result['invalid']: raise ValueError('Invalid reviewed job')
            job_id = sha256(job['url'].encode()).hexdigest()
        authoritative_url = db.execute('SELECT url FROM jobs WHERE id=?', (job_id,)).fetchone()['url']
        if job['url'] != authoritative_url:
            db.execute('INSERT INTO job_aliases VALUES(?,?,?) ON CONFLICT(alias_url) DO NOTHING', (job['url'], job_id, now()))
        extracted = json.loads(row['extracted'])
        review = {'fields': job, 'human_confirmed': True, 'linked_existing': bool(existing or target_job_id),
                  'human_overrides': [k for k, v in job.items() if v and v != extracted['fields'].get(k)]}
        # Idempotent review preserves application history and authoritative job data.
        db.execute('INSERT INTO job_origins VALUES(?,?,?,?) ON CONFLICT(job_id,item_id) DO UPDATE SET review_data=excluded.review_data,reviewed_at=excluded.reviewed_at', (job_id, item_id, dump(review), now()))
        db.execute('UPDATE discovery_items SET status=? WHERE id=?', ('accepted', item_id))
        store.audit(db, 'post_reviewed', {'item_id': item_id, 'job_id': job_id})
    return {'job_id': job_id, 'linked_existing': bool(existing or target_job_id), 'notice': 'Reviewed locally; no application was submitted.'}


def dismiss(store, item_id):
    with store.connect() as db:
        row = db.execute('SELECT status FROM discovery_items WHERE id=?', (item_id,)).fetchone()
        if not row: raise ValueError('Unknown post')
        if row['status'] == 'accepted': raise ValueError('Accepted provenance cannot be dismissed; archive the job instead')
        db.execute('UPDATE discovery_items SET status=? WHERE id=?', ('dismissed', item_id))
        store.audit(db, 'post_dismissed', {'item_id': item_id})
    return {'dismissed': True}


def origins(store, job_id):
    with store.connect() as db:
        rows = db.execute('''SELECT p.id,p.origin_url,p.source_label,p.body,p.extracted,o.review_data,o.reviewed_at
          FROM discovery_items p JOIN job_origins o ON o.item_id=p.id WHERE o.job_id=? ORDER BY o.reviewed_at''', (job_id,)).fetchall()
    return [{**dict(r), 'extracted': json.loads(r['extracted']), 'review_data': json.loads(r['review_data'])} for r in rows]


def automation(body, extracted):
    """Conservative textual triage, not an AI confidence or authenticity score."""
    from urllib.parse import urlsplit
    reasons=[]
    cls=extracted['classification'];fields=extracted['fields']
    if cls in ('not_identified_as_vacancy','job_seeker_post'):
        return {'decision':'skip','reasons':[cls]}
    if re.search(r"\b(?:not hiring|no (?:job )?vacancies|not a (?:real )?(?:job|vacancy)|applications? (?:are )?closed|position (?:is )?filled|vacancy expired|we (?:are not|aren.t) hiring)\b|لا نوظف|لا توجد (?:وظائف|شواغر)|تم إغلاق|انتهى التقديم|stelle besetzt",body,re.I):
        return {'decision':'skip','reasons':['closed_negated_or_not_a_real_vacancy']}
    if cls!='possible_vacancy':reasons.append('ambiguous_vacancy_signal')
    for key in ('title','company','url'):
        if not fields.get(key) or key not in extracted['evidence']:reasons.append('missing_source_backed_'+key)
    if re.search(r'synthetic|fixture|sample (?:post|vacancy)|example only|test (?:post|job)|مثال تجريبي',body,re.I):reasons.append('test_or_example_content')
    for w in extracted['warnings']:
        if w.startswith(('Multiple ','Potential fee','Possible closed','Explicit ISO deadline','Invalid explicit deadline')):reasons.append('warning_requires_review')
    if re.search(r'pay (?:a |an )?(?:fee|deposit)|bank details|رسوم توظيف|بيانات بنكية|<script',body,re.I):reasons.append('suspicious_content')
    if fields.get('url'):
        if urlsplit(fields['url']).hostname in ('t.co','bit.ly','tinyurl.com','lnkd.in','cutt.ly'):reasons.append('shortened_application_link_requires_review')
    return {'decision':'review' if reasons else 'auto_add','reasons':list(dict.fromkeys(reasons))}


def processing_mode():
    import os
    value=os.environ.get('JOBHUNTER_POST_MODE','auto')
    if value not in ('auto','review'):raise ValueError('JOBHUNTER_POST_MODE must be auto or review')
    return value


def process(store,rows,rights_attested=False,dry_run=False,_db=None,_hiring_context=False,profile_id='default'):
    """Classify -> preserve evidence -> auto-add safe complete candidates -> match.

    Existing authoritative jobs, application state and dismissed decisions are not
    overwritten. Automatic discovery never claims human confirmation.
    """
    from .matching import match_job
    mode=processing_mode()
    lookup={}
    if isinstance(rows,list):
        for row in rows:
            if isinstance(row,dict) and isinstance(row.get('body'),str) and isinstance(row.get('origin_url',''),str):
                lookup[sha256((row.get('origin_url','')+'\n'+sha256(row['body'].encode()).hexdigest()).encode()).hexdigest()]=row
    with (nullcontext(_db) if _db is not None else store.connect()) as db:
        if _db is None and not dry_run:db.execute('BEGIN IMMEDIATE')
        report=stage(store,rows,rights_attested,dry_run,_db=db,_hiring_context=_hiring_context,_decisions=True)
        report.update(auto_added=0,linked_existing=0,needs_review=0,would_auto_add=0,evaluated=0,
                      post_mode=mode,automatic_human_verified=False,classification_method='conservative source-backed rules v1')
        seen=set();profile=db.execute('SELECT data FROM profiles WHERE id=?',(profile_id,)).fetchone()
        report['evaluation_status']='available' if profile else 'profile_required'
        evaluated_ids=set()
        def evaluate(job_id,job):
            if profile and job_id not in evaluated_ids:
                result=match_job(job,json.loads(profile['data']))
                db.execute('INSERT INTO matches VALUES(?,?,?,?) ON CONFLICT(profile_id,job_id) DO UPDATE SET data=excluded.data,updated_at=excluded.updated_at',(profile_id,job_id,dump(result),now()))
                report['evaluated']+=1;evaluated_ids.add(job_id)
        for item in report['items']:
            iid=item['id']
            if iid in seen:continue
            seen.add(iid)
            if item['automation']['decision']=='skip':continue
            saved=db.execute('SELECT * FROM discovery_items WHERE id=?',(iid,)).fetchone()
            if saved and saved['status']=='dismissed':continue
            if saved and saved['status']=='accepted':
                if mode=='auto' and not dry_run:
                    for j in db.execute('SELECT j.id,j.data FROM jobs j JOIN job_origins o ON o.job_id=j.id WHERE o.item_id=?',(iid,)).fetchall():evaluate(j['id'],json.loads(j['data']))
                continue
            origin=saved['origin_url'] if saved else lookup[iid].get('origin_url','')
            if mode=='review' or item['automation']['decision']!='auto_add' or not origin:
                report['needs_review']+=1
                if not origin:item['automation']={'decision':'review','reasons':item['automation']['reasons']+['source_permalink_required']}
                if not dry_run:db.execute('UPDATE discovery_items SET extracted=? WHERE id=?',(dump({k:v for k,v in item.items() if k!='id'}),iid))
                continue
            raw={**item['fields'],'description':saved['body'] if saved else lookup[iid]['body'],
                 'attribution':saved['source_label'] if saved else 'Supplied post',
                 'source_notice':'Automatically extracted from a source post; not human-verified. Check the original vacancy and eligibility before applying.'}
            try:job=normalize_job(raw)
            except (ValueError,TypeError):report['needs_review']+=1;continue
            existing=db.execute('SELECT id,data FROM jobs WHERE url=? UNION SELECT j.id,j.data FROM jobs j JOIN job_aliases a ON a.job_id=j.id WHERE a.alias_url=?',(job['url'],job['url'])).fetchone()
            if existing:
                prior=json.loads(existing['data'])
                if any(prior[k].strip().casefold()!=job[k].strip().casefold() for k in ('title','company')):
                    report['needs_review']+=1;item['automation']={'decision':'review','reasons':['conflicting_existing_job_identity']}
                    if not dry_run:db.execute('UPDATE discovery_items SET extracted=? WHERE id=?',(dump({k:v for k,v in item.items() if k!='id'}),iid))
                    continue
                job_id=existing['id'];stored_job=prior
            else:job_id=sha256(job['url'].encode()).hexdigest();stored_job=job
            if dry_run:
                report['would_auto_add']+=1;continue
            if not existing:
                result=store.ingest([job],source='auto-post',_db=db)
                if result['invalid']:raise ValueError('Automatic post normalization failed')
            record={'human_confirmed':False,'automatically_added':True,'classification_method':report['classification_method'],
              'fields':job,'human_overrides':[],'linked_existing':bool(existing),'source_permalink':origin}
            db.execute('INSERT INTO job_origins VALUES(?,?,?,?) ON CONFLICT(job_id,item_id) DO NOTHING',(job_id,iid,dump(record),now()))
            db.execute('UPDATE discovery_items SET status=? WHERE id=?',('accepted',iid))
            report['linked_existing' if existing else 'auto_added']+=1
            evaluate(job_id,stored_job)
        report['inserted']=report['auto_added'];report['updated']=0
        report['notice']='Clear source-backed vacancies added automatically, never human-verified; ambiguous posts need review. No application submitted.'
        if not dry_run:store.audit(db,'posts_automatically_processed',{k:report[k] for k in ('auto_added','linked_existing','needs_review','evaluated','post_mode')})
        return report
