import pytest
from jobhunter_app.notifications import notify
from jobhunter_app.store import Store
from tests.test_local_store import JOB,PROFILE

@pytest.fixture
def store(tmp_path):
    s=Store(tmp_path/'notify.sqlite3');s.save_profile(PROFILE);s.ingest([JOB]);s.evaluate();return s


def test_notification_is_manual_idempotent_and_redacted(store):
    calls=[]
    def sender(message):calls.append(message);return True
    r=notify(store,sender=sender,channel='test')
    assert r['sent']==1 and len(calls)==1
    assert PROFILE['name'] not in calls[0] and PROFILE['facts'][0]['text'] not in calls[0]
    assert notify(store,sender=sender,channel='test')['already_delivered']==1
    assert len(calls)==1


def test_failure_is_retryable(store):
    assert notify(store,sender=lambda _:False,channel='test')['failed']==1
    assert notify(store,sender=lambda _:True,channel='test')['sent']==1


def test_applied_not_notified(store):
    store.set_status(store.jobs()[0]['id'],'applied')
    assert notify(store,sender=lambda _:True,channel='test')['sent']==0


def test_no_match_not_notified(store):
    store.save_profile(PROFILE)
    assert notify(store,sender=lambda _:True,channel='test')['sent']==0


def test_notification_html_escaped(store):
    store.ingest([{**JOB,'title':'<script>x</script> Python'}]);store.evaluate();messages=[]
    notify(store,sender=lambda m:messages.append(m) or True,channel='test')
    assert '&lt;script&gt;' in messages[0] and '<script>' not in messages[0]

@pytest.mark.parametrize('threshold',[-1,101,float('nan'),True,'60'])
def test_bad_threshold(store,threshold):
    with pytest.raises(ValueError):notify(store,threshold,sender=lambda _:True,channel='test')
