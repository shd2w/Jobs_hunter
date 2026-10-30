import json
import pytest
from jobhunter_app.sources import Source,register,scan
from jobhunter_app.store import Store
from jobhunter_app.structured_source import collect


def test_heldout_structured_publisher_pagination_and_missing_fields(monkeypatch):
    monkeypatch.setattr('time.sleep',lambda *a:None)
    def getter(url,*a,**kw):
        if url.endswith('robots.txt'): return b'User-agent: *\nAllow: /\n','text/plain'
        data={'@type':'JobPosting','title':'Engineer','hiringOrganization':{'name':'Heldout'},'url':'https://heldout.example/jobs/1','description':'Python'}
        extra='<link rel="next" href="https://heldout.example/jobs?page=2">' if '?' not in url else ''
        return ('<script type="application/ld+json">'+json.dumps(data)+'</script>'+extra).encode(),'text/html'
    source=Source('structured_html','https://heldout.example/jobs')
    first=collect(source,getter=getter)
    assert first.payload[0]['company']=='Heldout' and not first.checkpoint['complete']
    assert first.metrics['reusable_source_established']
    assert collect(source,first.checkpoint,getter=getter).checkpoint['complete']
    def unsupported(url,*a,**kw):
        if url.endswith('robots.txt'): return b'User-agent: *\nAllow: /\n','text/plain'
        return b'<p>Not a vacancy</p>','text/html'
    with pytest.raises(ValueError,match='No usable'): collect(source,getter=unsupported)


def test_generic_recipe_requires_approval_and_uses_common_intake(tmp_path,monkeypatch):
    store=Store(tmp_path/'app.db');sid=register(store,'structured_html','https://heldout.example/jobs',False)
    with pytest.raises(ValueError,match='approved'): scan(store,sid)
    from jobhunter_app.collection import Collection
    monkeypatch.setattr('jobhunter_app.structured_source.collect',lambda *a:Collection([
        {'title':'Engineer','company':'Heldout','url':'https://heldout.example/jobs/1','description':'Python'},
        {'title':'missing company','url':'https://heldout.example/jobs/2'}]))
    register(store,'structured_html','https://heldout.example/jobs',True)
    result=scan(store,sid,mirror_legacy=False)
    assert result['inserted']==1 and result['invalid']==1
