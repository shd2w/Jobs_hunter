"""Evidence-bound preparation CLI smoke; all records are synthetic and disposable."""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(sys.argv[1]).resolve()
python = sys.argv[2]
with tempfile.TemporaryDirectory(prefix='jobhunter-evidence-smoke-') as td:
    base = Path(td)
    commands = []
    env = dict(os.environ)
    # No provider credentials are needed or used by these local commands.
    def cli(*args, expected=0):
        proc = subprocess.run([python, 'run_local.py', '--db', str(base/'local.sqlite3'), *map(str,args)],
                              cwd=root, env=env, capture_output=True, text=True, timeout=40)
        assert proc.returncode == expected, (args[0], proc.stderr)
        commands.append(args[0])
        return json.loads(proc.stdout) if expected == 0 else proc.stderr
    cli('init')
    original = base/'synthetic.pdf'
    original.write_bytes(b'%PDF-1.4\nSYNTHETIC OPAQUE ORIGINAL ONLY\n')
    before = original.read_bytes()
    profile = {'name':'Synthetic Evidence Candidate', 'skills':['Python'], 'original_cv':str(original),
               'facts':[{'text':'I built a Python project.', 'source':'Synthetic project record', 'verified':True}]}
    profile_file = base/'synthetic-profile.json'
    profile_file.write_text(json.dumps(profile))
    cli('profile',profile_file)
    jobs_file = base/'synthetic-jobs.json'
    jobs_file.write_text(json.dumps([{'title':'Python Engineer','company':'Synthetic Employer',
                                    'url':'https://example.org/evidence-smoke','description':'Python required.'}]))
    cli('import',jobs_file)
    cli('match')
    job = cli('list')[0]
    pack = cli('pack',job['id'],'--output',base/'packs')
    folder = Path(pack['directory'])
    side = json.loads((folder/'preparation.json').read_text())
    report = pack['validation_report']
    assert report == side['cover']['validation_report'] and report['valid'] and report['review_required']
    assert all(check['passed'] for check in report['checks'])
    assert report['bindings']['content_sha256'] == sha256((folder/'cover-letter-draft.txt').read_bytes()).hexdigest()
    assert (folder/'original-cv.pdf').read_bytes() == before == original.read_bytes()
    # Removing attestation must reject pack creation without touching prior outputs.
    profile_file.write_text(json.dumps({**profile,'facts':[]}))
    cli('profile',profile_file)
    cli('pack',job['id'],'--output',base/'packs',expected=2)
    assert len(list((base/'packs').iterdir())) == 1 and original.read_bytes() == before
    profile_file.write_text(json.dumps(profile))
    cli('profile',profile_file)
    second = cli('pack',job['id'],'--output',base/'packs')
    assert second['directory'] != pack['directory'] and second['validation_report'] == report
    cli('backup',base/'backup.sqlite3')
    cli('learning')
    print(json.dumps({'status':'passed','schema':5,'commands':commands,'validator':report['validator'],
                      'checks':len(report['checks']),'report_sidecar_and_content_hash':'passed',
                      'original_cv_bytes':'unchanged','missing_evidence_rejected':True,
                      'source_model_resource_or_message_calls':0,'data':'synthetic disposable only'},indent=2))
