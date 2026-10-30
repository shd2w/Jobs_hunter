"""Evidence-based pagination receipt v1. Unknown is None, never inferred false.

A cursor/offset recipe can be available without proof another page exists.
Remaining detail work is not a next listing page. Receipt scope is one search/pass.
"""

def state(*, has_next_page=None, continuation_available=False, page_limit_reached=False,
          result_limit_reached=False, source_exhausted=None, partial=False, failed=False,
          cancelled=False, evidence='unavailable', pages_retrieved=None, pending_details=0):
    for x in (has_next_page,source_exhausted):
        if x is not None and type(x) is not bool: raise ValueError('Expected explicit pagination evidence or unknown')
    for x in (continuation_available,page_limit_reached,result_limit_reached,partial,failed,cancelled):
        if type(x) is not bool: raise ValueError('Invalid pagination flag')
    if has_next_page is True and source_exhausted is True: raise ValueError('Conflicting pagination evidence')
    if source_exhausted is True and continuation_available: raise ValueError('Exhausted source cannot continue this pass')
    messages=[]
    if failed: messages.append('Scan failed before continuation could be established.')
    elif cancelled: messages.append('Scan interrupted; only previously committed progress can be resumed.')
    elif partial: messages.append('Scan partially completed; review source errors or invalid records.')
    if has_next_page is True: messages.append('Additional pages confirmed.' if continuation_available else 'Additional pages confirmed; continuation not currently available.')
    if page_limit_reached: messages.append('Scan stopped at the configured page limit.')
    if result_limit_reached: messages.append('Result limit reached; further results have not been verified.' if has_next_page is not True else 'Configured result limit reached.')
    if source_exhausted is True: messages.append('No additional pages reported by the source for this search/pass.')
    if pending_details: messages.append(f'{pending_details} observed detail records remain; not evidence of another listing page.')
    unknown = has_next_page is None and source_exhausted is None
    if unknown and not failed and not cancelled: messages.append('Continuation information unavailable.' if not continuation_available else 'A continuation request is possible; additional results are not confirmed.')
    return {'schema_version':1,'has_next_page':has_next_page,'continuation_available':continuation_available,
            'page_limit_reached':page_limit_reached,'result_limit_reached':result_limit_reached,
            'source_exhausted':source_exhausted,'continuation_unknown':unknown,'partial':partial,
            'failed':failed,'cancelled':cancelled,'evidence':evidence,'pages_retrieved':pages_retrieved,
            'pending_details':pending_details,'message':' '.join(messages)}


def receipt(source, collected):
    if collected is None: return state()
    m=collected.metrics; cp=collected.checkpoint
    if 'pagination' in m: return dict(m['pagination'])
    kind=source.kind
    if kind.startswith('jobspy_'):
        return state(continuation_available=bool(m.get('offset_continuation')),
                     page_limit_reached=bool(m.get('page_limit_reached')),
                     result_limit_reached=bool(m.get('result_limit_reached')),
                     evidence='local_offset_recipe_only; provider exposes no next-page receipt',pages_retrieved=1)
    if kind in ('smartrecruiters','jobicy','arbeitnow','usajobs'):
        # Collectors provide their own validated metadata receipt; old/injected
        # Collections lacking it must not inherit inferred completeness.
        return state(pages_retrieved=None,evidence='collector supplied no pagination receipt')
    if kind in ('structured_html','scrapling_jobicy','scrapling_arbeitnow','wuzzuf','naukrigulf'):
        pending=len(cp.get('pending',[]))
        next_link=bool(cp.get('next_page')) or bool(cp.get('page') and not cp.get('complete') and not pending)
        return state(has_next_page=True if next_link else None,
                     continuation_available=bool(pending or next_link),pending_details=pending,
                     evidence='validated observed detail IDs / configured page recipe; missing next link is not proof of end')
    if kind in ('reddit','discord','linkedin','x','telegram'):
        cursor=bool(cp.get('cursor'))
        return state(has_next_page=True if cursor and kind!='telegram' else None,
                     continuation_available=cursor,evidence='official API cursor' if kind!='telegram' else 'update offset, not proof of additional vacancies')
    if kind=='hn':
        pending=max(0,int(m.get('pending_comments',0)))
        return state(continuation_available=pending>0,pending_details=pending,evidence='observed thread comment IDs')
    return state(evidence='bounded response snapshot; whole-source pagination not established')
