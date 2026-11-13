"""Real HTTP round-trips against the local server (fake AI/PDF)."""
import json
import sys
import threading
import time
import urllib.error
import urllib.request

import pytest

from jobhunter_ui import runner as runner_mod
from jobhunter_ui.server import make_server
from tests.test_ui_service import make_ws, jid, URL


@pytest.fixture
def srv(tmp_path, monkeypatch):
    ws = make_ws(tmp_path, monkeypatch)
    s = make_server(tmp_path, "127.0.0.1", 0, workspace=ws)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    s.base = f"http://127.0.0.1:{s.server_address[1]}"
    s.tmp, s.ws = tmp_path, ws
    yield s
    s.shutdown(); s.server_close()


def call(srv, path, body=None, headers=None, method=None):
    h = dict(headers or {})
    data = None
    if body is not None:
        data = json.dumps(body).encode(); h.setdefault("Content-Type", "application/json"); h.setdefault("X-JobHunter", "1")
    req = urllib.request.Request(srv.base + path, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def test_pages_and_security_headers(srv):
    st, body, hd = call(srv, "/")
    assert st == 200 and b"JobHunter" in body
    assert "script-src 'self'" in hd["Content-Security-Policy"] and hd["X-Content-Type-Options"] == "nosniff"
    for f in ("app.js", "style.css", "cv.example.md"):
        assert call(srv, "/static/" + f)[0] == 200
    assert call(srv, "/static/..%2Fservice.py")[0] == 404


def test_html_has_no_inline_script_or_style(srv):
    html = call(srv, "/")[1].decode()
    assert "<script>" not in html and "style=" not in html and " onclick" not in html


def test_jobs_api_ranked(srv):
    st, body, _ = call(srv, "/api/jobs?min=4&hide_german=1")
    d = json.loads(body)
    assert st == 200 and d["jobs"][0]["rank"] == 1 and d["jobs"][0]["company"] == "Acme"
    assert json.loads(call(srv, "/api/jobs?weights=skills_match:100")[1])["custom_weights"] is True


def test_one_click_cv_over_http_and_download(srv):
    i = jid(srv.ws)
    st, body, _ = call(srv, f"/api/jobs/{i}/cv", {"mode": "tailored"})
    d = json.loads(body)
    assert st == 200 and d["artifacts"]["cv"]["pdf"]
    st, pdf, hd = call(srv, "/files/" + d["artifacts"]["cv"]["pdf"])
    assert st == 200 and pdf.startswith(b"%PDF") and hd["Content-Type"] == "application/pdf"
    st, md, hd = call(srv, "/files/" + d["artifacts"]["cv"]["md"] + "?download=1")
    assert st == 200 and "attachment" in hd["Content-Disposition"] and hd["Content-Type"].startswith("text/plain")


def test_errors_are_json_with_message(srv):
    srv.ws.save_keys({"GOOGLE_AI_API_KEY": ""})
    st, body, _ = call(srv, f"/api/jobs/{jid(srv.ws)}/cv", {"mode": "tailored"})
    e = json.loads(body)["error"]
    assert st == 400 and e["code"] == "no_ai" and "Setup" in e["message"]
    assert call(srv, "/api/jobs/aaaaaaaaaaaa")[0] == 404
    assert call(srv, "/api/nope")[0] == 404


def test_csrf_and_host_protection(srv):
    i = jid(srv.ws)
    st, _, _ = call(srv, f"/api/jobs/{i}/status", {"status": "saved"}, headers={"Origin": "https://evil.example"})
    assert st == 403
    req = urllib.request.Request(srv.base + f"/api/jobs/{i}/status", data=b'{"status":"saved"}', headers={"Content-Type": "text/plain"})
    with pytest.raises(urllib.error.HTTPError) as e: urllib.request.urlopen(req)
    assert e.value.code == 403  # missing custom header: a cross-site form cannot send it
    st, _, _ = call(srv, "/api/jobs", headers={"Host": "evil.example"})
    assert st == 403  # DNS-rebinding guard
    assert json.loads(call(srv, "/api/jobs")[1])["jobs"][0]["status"] == "new"


def test_files_cannot_read_secrets(srv):
    (srv.tmp / ".env").write_text("OpenRouter=sk-or-v1-SECRET")
    for p in ("/files/.env", "/files/../.env", "/files/%2e%2e/.env", "/files/data/evaluations.json", "/files/config/profile.yml"):
        assert call(srv, p)[0] == 404, p


def test_setup_endpoints_never_return_key_values(srv):
    st, body, _ = call(srv, "/api/setup/keys", {"values": {"OpenRouter": "sk-or-v1-TopSecret123"}})
    assert st == 200 and b"TopSecret123" not in body
    assert b"TopSecret123" not in call(srv, "/api/setup")[1]


def test_run_streams_output_and_rejects_parallel(srv, monkeypatch):
    (srv.tmp / "fake_task.py").write_text("import time,sys\nprint('hello ü', flush=True)\ntime.sleep(1.5)\nprint('bye')\n", encoding="utf-8")
    monkeypatch.setitem(runner_mod.TASKS, "health", ("Check", "fake_task.py"))
    assert call(srv, "/api/run", {"task": "health"})[0] == 200
    assert call(srv, "/api/run", {"task": "health"})[0] == 409
    deadline = time.time() + 10
    while time.time() < deadline:
        d = json.loads(call(srv, "/api/run?since=0")[1])
        if not d["running"] and d["returncode"] is not None:
            break
        time.sleep(0.2)
    assert d["returncode"] == 0 and d["lines"] == ["hello ü", "bye"]


def test_run_argument_validation(srv):
    for bad in ({"task": "rm -rf"}, {"task": "evaluate", "batch": 0}, {"task": "evaluate", "batch": "x"},
                {"task": "evaluate", "threshold": 9}, {"task": "all", "german_policy": "nope"}):
        assert call(srv, "/api/run", bad)[0] == 400, bad


def test_runner_builds_expected_cli(tmp_path):
    r = runner_mod.Runner(tmp_path)
    a = r.build_args("evaluate", {"batch": 7, "threshold": 4, "german_policy": "reject_b1_plus", "create_cv": False})
    assert a[2].endswith("run_evaluate.py") and a[3:] == ["--threshold", "4.0", "--german-policy", "reject_b1_plus", "--batch", "7", "--no-cv"]
    assert r.build_args("evaluate", {"create_cv": True})[-1] == "--create-cv"
    assert r.build_args("scan", {})[2:] == [str(tmp_path / "run_scan.py")]
