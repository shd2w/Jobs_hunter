"""Disposable first-run acceptance: no live provider traffic or private data.
Run with pytest + Python Playwright; output is deliberately outside the repository.
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile
from threading import Event, Thread
import time
import pytest
from playwright.sync_api import sync_playwright, expect
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from jobhunter_app.store import Store
from jobhunter_app.web import make_server
from tests.test_automatic import payload


def run(output,chromium):
    output.mkdir(parents=True,exist_ok=True);errors=[];shots=[];calls=[]
    first,release,second,finish=Event(),Event(),Event(),Event()
    def get(url,*args,**kwargs):
        calls.append(url)
        if 'jobicy' in url:first.set();assert release.wait(20)
        if 'arbeitnow' in url:
            second.set();assert finish.wait(20);raise ValueError('Fixture source unavailable')
        return json.dumps(payload(url)).encode(),'application/json'
    with tempfile.TemporaryDirectory(prefix='jobhunter-auto-ui-') as d,pytest.MonkeyPatch.context() as patch:
        patch.setattr('jobhunter_app.network.get',get)
        # Offline three-feed UI scenario; expanded registry has separate tests.
        patch.setattr('jobhunter_app.automatic.STARTERS', (('jobicy','remote'),('arbeitnow','de'),('remotive','remote')))
        store=Store(Path(d)/'empty.db');server=make_server(store,0,automatic=True)
        thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_port)
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(executable_path=chromium,headless=True,args=['--no-sandbox'])
                try:
                    page=browser.new_page(viewport={'width':1440,'height':1080})
                    page.on('pageerror',lambda e:errors.append(str(e)))
                    page.on('request',lambda r:errors.append('External browser request') if not r.url.startswith(base+'/') else None)
                    def shot(name):
                        metrics=page.evaluate('() => ({width:innerWidth,actual:document.documentElement.scrollWidth})')
                        assert metrics['width']==metrics['actual'],metrics
                        page.screenshot(path=str(output/(name+'.png')));shots.append({'name':name,**metrics})
                    assert first.wait(5);page.goto(base)
                    expect(page.locator('#auto-heading')).to_contain_text('Finding opportunities')
                    assert page.locator('#skills').input_value()==''
                    shot('first-run-desktop')
                    release.set();assert second.wait(5)
                    expect(page.locator('#job-list .job')).to_have_count(1,timeout=8000)
                    expect(page.locator('#auto-summary')).to_contain_text('Arbeitnow')
                    finish.set()
                    expect(page.locator('#auto-heading')).to_contain_text('2 opportunities',timeout=8000)
                    assert len(calls)==3 and store.profile()['skills']==[]
                    shot('jobs-ready-desktop')
                    page.locator('#auto-details summary').click();shot('source-status-desktop')
                    expect(page.locator('#auto-sources')).to_contain_text('Access or response problem')
                    page.locator('#auto-toggle').click();expect(page.locator('#auto-heading')).to_have_text('Discovery is paused')
                    page.set_viewport_size({'width':390,'height':844});page.evaluate('() => scrollTo(0,0)');shot('paused-mobile-light')
                    page.locator('#auto-toggle').click();expect(page.locator('#auto-heading')).to_contain_text('2 opportunities')
                    page.locator('#auto-check').click();page.wait_for_timeout(2200);assert len(calls)==3
                    page.locator('#auto-details summary').click();page.evaluate('() => scrollTo(0,0)');shot('jobs-ready-mobile-light')
                    page.emulate_media(color_scheme='dark');shot('jobs-ready-mobile-dark')
                    page.get_by_role('button',name='Your evidence',exact=True).click();page.locator('#skills').fill('UNSAVED PRIVATE DRAFT')
                    page.wait_for_timeout(2300);assert page.locator('#skills').input_value()=='UNSAVED PRIVATE DRAFT'
                    page.get_by_role('button',name='Opportunities',exact=True).click()
                    page.locator('#job-list .job').first.get_by_role('button',name='Review opportunity').click()
                    page.locator('#detail-notes').fill('UNSAVED APPLICATION NOTE');page.wait_for_timeout(2300)
                    assert page.locator('#detail-notes').input_value()=='UNSAVED APPLICATION NOTE'
                    page.locator('#close-dialog').click();page.locator('#auto-toggle').click()
                    expect(page.locator('#auto-heading')).to_have_text('Discovery is paused');page.reload()
                    expect(page.locator('#auto-heading')).to_have_text('Discovery is paused')
                    assert len(calls)==3 and not errors,errors
                    assert store.summary()['total_jobs']==2 and store.summary()['matched_jobs']==0
                finally:browser.close()
        finally:
            release.set();finish.set();server.shutdown();server.server_close();thread.join(5)
    result={'passed':True,'screenshots':shots,'provider_requests':0,'fixture_fetches':len(calls),'browser_errors':errors,
            'checks':['zero-input startup','progressive results','failure isolation','pause persists','resume respects cooldowns','profile draft preserved','modal draft preserved','no page overflow','no external browser traffic']}
    (output/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--chromium',required=True);a=p.parse_args();run(a.output,a.chromium)
