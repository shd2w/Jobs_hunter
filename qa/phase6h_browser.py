"""Disposable integrated UI acceptance; needs pytest + Python Playwright + Chromium.

Usage: python qa/phase6h_browser.py --output /PRIVATE/qa-results --chromium /path/to/chromium
No live accounts, providers, publishers, models, messages or supplied personal data.
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile
from threading import Thread
import pytest
from playwright.sync_api import sync_playwright, expect
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.test_phase6_acceptance import workspace, PRIVATE_REASON, PRIVATE_NOTE
from jobhunter_app.web import make_server


def run(output, executable):
    output.mkdir(parents=True, exist_ok=True)
    states, errors = [], []
    with tempfile.TemporaryDirectory(prefix='jobhunter-phase6h-ui-') as td, pytest.MonkeyPatch.context() as patch:
        store = workspace.__wrapped__(Path(td), patch)
        original = Path(store.profile()['original_cv']).read_bytes()
        server = make_server(store, 0); thread = Thread(target=server.serve_forever, daemon=True); thread.start()
        base = 'http://127.0.0.1:'+str(server.server_port)
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(executable_path=executable, headless=True, args=['--no-sandbox'])
                try:
                    p = browser.new_page(viewport={'width': 1440, 'height': 1100})
                    p.on('pageerror', lambda e: errors.append(str(e)))
                    p.on('request', lambda r: errors.append('Unexpected external request: '+r.url) if not r.url.startswith(base+'/') else None)
                    def shot(name):
                        metrics = p.evaluate('''() => ({width:innerWidth,actual:document.documentElement.scrollWidth,
                          dialogOverflow:document.querySelector('#job-dialog').open && document.querySelector('#job-dialog').scrollWidth>document.querySelector('#job-dialog').clientWidth})''')
                        states.append({'name': name, **metrics}); p.screenshot(path=str(output/(name+'.png')))
                    def get(path): return p.evaluate('(path)=>api(path)', path)
                    def post(path, data): return p.evaluate('([path,data])=>api(path,data)', [path, data])
                    def open_target():
                        p.get_by_role('button', name='Opportunities', exact=True).click()
                        p.locator('article.job').filter(has_text='Synthetic Acceptance Employer').get_by_role('button', name='Review opportunity', exact=True).click()
                        p.wait_for_selector('.evidence-link')
                    p.goto(base); open_target()
                    assert p.locator('.evidence-link').count() == 2
                    fact = p.locator('.evidence-link').nth(1)
                    fact.get_by_label('Use this verified fact').check()
                    fact.locator('textarea').nth(0).fill('Coordinate project reviews.')
                    fact.locator('textarea').nth(1).fill(PRIVATE_REASON)
                    p.locator('#evidence-confirmed').check(); p.locator('#evidence-mapping').scroll_into_view_if_needed(); shot('explicit-mapping-desktop')
                    p.locator('#pack').click(); expect(p.locator('#pack-state')).to_contain_text('pending')
                    version = p.locator('#pack-version').input_value()
                    assert PRIVATE_REASON not in p.locator('#pack-content').text_content()
                    for field in ['facts','target','original-cv','manual-submission']: p.locator('#pack-'+field).check()
                    p.once('dialog', lambda d: d.accept()); p.locator('#pack-reviewed').click()
                    expect(p.locator('#pack-state')).to_contain_text('reviewed')
                    p.locator('#pack-state').scroll_into_view_if_needed(); shot('reviewed-pack-desktop')
                    p.locator('#close-dialog').click(); p.get_by_role('button',name='Skill priorities',exact=True).click()
                    card = p.locator('.learning-card').filter(has=p.get_by_role('heading',name='SQL',exact=True))
                    card.locator('.learning-practice summary').click(); card.get_by_role('button',name='Save SQL practice',exact=True).click()
                    expect(p.locator('#learning-progress-select')).not_to_have_value('')
                    p.locator('#learning-progress-status').select_option('completed')
                    p.locator('#learning-progress-save').click()
                    assert get('/api/learning-progress')['items'][0]['status'] == 'planned'
                    p.locator('#learning-progress-notes').fill(PRIVATE_NOTE); p.locator('#learning-progress-attested').check()
                    p.locator('#learning-progress-save').click()
                    expect(p.locator('#learning-progress-message')).to_contain_text('Manual practice progress saved')
                    item = get('/api/learning-progress')['items'][0]; assert item['status'] == 'completed'
                    p.set_viewport_size({'width':390,'height':844}); p.locator('#learning-progress-form').scroll_into_view_if_needed(); shot('completed-practice-mobile')
                    p.emulate_media(color_scheme='dark'); p.locator('#learning-progress-form').scroll_into_view_if_needed(); shot('completed-practice-dark-mobile')
                    assert get('/api/pack-inspect?id='+version)['review_state'] == 'reviewed'
                    profile = get('/api/profile'); assert not any(f.get('verified') and 'expert in SQL' in f['text'] for f in profile['facts'])
                    profile['facts'][1]['source'] += ' changed in synthetic UI acceptance'; post('/api/profile', {'profile':profile})
                    p.evaluate('async()=>await refresh()'); open_target()
                    p.locator('#pack-version').select_option(version)
                    expect(p.locator('#pack-state')).to_contain_text('blocked')
                    assert p.locator('#pack-reviewed').is_disabled()
                    assert PRIVATE_REASON in p.locator('#pack-relevance').text_content()
                    p.locator('#pack-state').scroll_into_view_if_needed(); shot('changed-source-blocked-pack-dark-mobile')
                    assert get('/api/learning-progress')['items'] == [item]
                    assert all(j['status']=='discovered' for j in get('/api/jobs'))
                    assert Path(store.profile()['original_cv']).read_bytes() == original
                    assert not p.evaluate('window.BAD_ACCEPTANCE||0')
                    assert not errors and all(s['actual']<=s['width'] and not s['dialogOverflow'] for s in states), (errors,states)
                    result={'status':'passed','states':states,'errors':errors,'external_browser_requests':0,
                            'unchanged_original_cv':True,'practice_not_candidate_evidence':True,
                            'completion_requires_attestation':True,'practice_preserved_after_source_change':True,
                            'old_review_blocked_after_source_change':True,'literal_private_markup':True,
                            'runtime':'local Chromium and real loopback HTTP; not remote Codespaces'}
                    (output/'browser-qa.json').write_text(json.dumps(result,indent=2)); print(json.dumps(result,indent=2))
                finally: browser.close()
        finally: server.shutdown(); server.server_close(); thread.join(3)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True); parser.add_argument('--chromium',required=True)
    args=parser.parse_args(); run(args.output,args.chromium)
