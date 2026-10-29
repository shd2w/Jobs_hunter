"""Audit characterization plus strict expected failures for known unfixed gaps."""
import json
from pathlib import Path
import pytest,yaml
from jobhunter_app.documents import cover_draft,validate_cover,prepare_pack
from jobhunter_app.store import Store
from agents.cover_letter import CoverLetterWriter
from tests.test_local_store import JOB,PROFILE

@pytest.fixture
def store(tmp_path):
 s=Store(tmp_path/'audit.sqlite3');s.save_profile(PROFILE);s.ingest([JOB]);s.evaluate();return s

def test_validator_rejects_extra_claim():
 draft=cover_draft(JOB,PROFILE)
 assert validate_cover(draft['content']+'\nI have a doctorate in aerospace engineering.',JOB,PROFILE,[PROFILE['facts'][0]['text']])

def test_validator_requires_selected_evidence():
 assert validate_cover(f'I am applying for {JOB["title"]} at {JOB["company"]}.',JOB,PROFILE,[])

def test_validator_rejects_negated_wrong_target():
 content=f'I am not applying for the {JOB["title"]} role at {JOB["company"]}. I apply to Another Employer.\n'+PROFILE['facts'][0]['text']
 assert validate_cover(content,JOB,PROFILE,[PROFILE['facts'][0]['text']])

def test_legacy_writer_preserves_previous_edit(tmp_path):
 config=tmp_path/'profile.yml';config.write_text(yaml.safe_dump({'candidate':{'full_name':PROFILE['name']},'verified_facts':PROFILE['facts']}))
 writer=CoverLetterWriter(output_dir=tmp_path/'legacy',profile_path=config);first=writer.generate(JOB);path=Path(first['output_path']);path.write_text('SYNTHETIC PREVIOUS EDIT')
 writer.generate(JOB);assert path.read_text()=='SYNTHETIC PREVIOUS EDIT'

def test_audit_reproductions_and_no_network(monkeypatch):
 import socket
 from qa.phase6_audit import run
 def denied(*args,**kwargs):raise AssertionError('No external I/O in scope audit')
 monkeypatch.setattr(socket,'create_connection',denied)
 result=run(Path(__file__).resolve().parents[1]);assert result['status']=='audit_complete_no_reproduced_scoped_findings'
 assert len(result['findings'])==7 and sum(f['reproduced'] for f in result['findings'])==0
 assert all(not f['reproduced'] for f in result['findings'] if f['id'].startswith('P6-VAL-') or f['id'] in ('P6-PACK-001','P6-LEARN-001','P6-LEARN-002'))
 assert result['existing_safeguards']['original_cv_copy_bytes_and_sha256_equal'] is True
 assert result['external_source_model_resource_or_message_calls']==0

def test_controlled_template_uses_only_verified_selected_fact():
 p={**PROFILE,'facts':PROFILE['facts']+[{'text':'UNVERIFIED INVENTED CLAIM','source':'Synthetic','verified':False}]}
 d=cover_draft(JOB,p);assert PROFILE['facts'][0]['text'] in d['content'] and 'UNVERIFIED' not in d['content']
 assert d['review_required'] is True and d['method']=='grounded local template v2'

@pytest.mark.parametrize('profile',[{}, {'name':'Synthetic','facts':[]}, {'name':'Synthetic','facts':[{'text':'x','source':'Synthetic','verified':False}]}])
def test_controlled_template_refuses_missing_verified_evidence(profile):
 with pytest.raises(ValueError):cover_draft(JOB,profile)

@pytest.mark.parametrize('field',['title','company'])
def test_validator_catches_absent_expected_tokens(field):
 d=cover_draft(JOB,PROFILE);altered=d['content'].replace(JOB[field],'UNRELATED TOKEN')
 assert 'Employer or role mismatch' in validate_cover(altered,JOB,PROFILE,[PROFILE['facts'][0]['text']])

def test_new_core_pack_is_unique_and_original_unchanged(store,tmp_path):
 original=tmp_path/'supplied.pdf';original.write_bytes(b'%PDF-1.4\nSYNTHETIC OPAQUE ORIGINAL\n');before=original.read_bytes();store.save_profile({**PROFILE,'original_cv':str(original)})
 root=tmp_path/'packs';a=prepare_pack(store,store.jobs()[0]['id'],root);first=Path(a['directory']);(first/'cover-letter-draft.txt').write_text('SYNTHETIC PREVIOUS CORE EDIT')
 b=prepare_pack(store,store.jobs()[0]['id'],root);assert a['directory']!=b['directory']
 assert (first/'cover-letter-draft.txt').read_text()=='SYNTHETIC PREVIOUS CORE EDIT'
 assert original.read_bytes()==before==(Path(b['directory'])/'original-cv.pdf').read_bytes()
 meta=json.loads((Path(b['directory'])/'preparation.json').read_text());assert meta['cover']['review_required'] and meta['cover']['evidence']==PROFILE['facts']
 assert meta['match']['fingerprints']['profile'] and meta['post_origins']==[]

def test_invalid_original_cleanup_and_missing_original_explicit(store,tmp_path):
 original=tmp_path/'bad.pdf';original.write_bytes(b'not a PDF');before=original.read_bytes();store.save_profile({**PROFILE,'original_cv':str(original)});root=tmp_path/'packs'
 with pytest.raises(ValueError):prepare_pack(store,store.jobs()[0]['id'],root)
 assert list(root.iterdir())==[] and original.read_bytes()==before
 store.save_profile(PROFILE);pack=prepare_pack(store,store.jobs()[0]['id'],root);assert pack['original_cv'] is None and not (Path(pack['directory'])/'original-cv.pdf').exists()

def test_learning_population_and_profile_isolation(store):
 store.ingest([{**JOB,'url':'https://example.org/second','description':'SQL not required; Python required.'},{**JOB,'url':'https://example.org/excluded','title':'Senior Developer'}])
 store.save_profile({**PROFILE,'excluded_title_terms':['Senior']});store.evaluate();a=store.learning();assert a['vacancies_reviewed']==2
 assert next(x['vacancies'] for x in a['priorities'] if x['skill']=='SQL')==2
 assert 'not mandatory requirements' in a['scope']
 store.save_profile({**PROFILE,'skills':['Python','SQL','Communication']},'other');store.evaluate('other');b=store.learning('other')
 assert b['vacancies_reviewed']==3 and b['priorities']==[]
 assert store.learning()==a
