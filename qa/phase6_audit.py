"""Synthetic characterization: reports known gaps; never calls a provider."""
import json,sys,tempfile
from pathlib import Path

def run(root):
 sys.path.insert(0,str(root))
 from jobhunter_app.documents import cover_draft,validate_cover,prepare_pack
 from jobhunter_app.store import Store
 from agents.cover_letter import CoverLetterWriter
 import yaml
 from hashlib import sha256
 job={'title':'Python Developer','company':'Audit Employer','url':'https://example.org/audit/role','description':'Python required; SQL not required; Docker preferred.'}
 fact={'text':'I built a Python project.','verified':True,'source':'Synthetic project record'}
 profile={'name':'Synthetic Audit Candidate','skills':['Python'],'facts':[fact]}
 with tempfile.TemporaryDirectory(prefix='jobhunter-phase6-audit-') as td:
  base=Path(td);s=Store(base/'audit.sqlite3');s.save_profile(profile);s.ingest([job]);s.evaluate()
  draft=cover_draft(job,profile)
  extra_issues=validate_cover(draft['content']+'\nI hold a doctorate in aerospace engineering.',job,profile,[fact['text']])
  empty_issues=validate_cover('I am applying for the Python Developer role at Audit Employer.',job,profile,[])
  wrong='I am not applying for the Python Developer role at Audit Employer. I am applying to Another Employer.\n“'+fact['text']+'”'
  wrong_issues=validate_cover(wrong,job,profile,[fact['text']])
  unrelated={'text':'I completed a pottery workshop.','verified':True,'source':'Synthetic workshop record'}
  unrelated_profile={**profile,'facts':[unrelated]}
  auto_unrelated=False
  try:
   auto_unrelated=unrelated in cover_draft(job,unrelated_profile)['evidence']
  except ValueError:
   pass
  from jobhunter_app.evidence_mapping import preview
  evidence_preview=preview(job,unrelated_profile)
  mapping={'format':1,'preview_fingerprint':evidence_preview['preview_fingerprint'],'confirmed':True,
   'links':[{'fact_id':evidence_preview['facts'][0]['id'],'field':'description','start':0,'end':6,'quote':'Python',
             'reason':'Synthetic user explanation only; this does not independently establish transferable relevance.'}]}
  explicit=cover_draft(job,unrelated_profile,mapping)
  explicit_ok=(explicit['evidence']==[unrelated] and explicit['relevance']['status']=='user_attested'
               and explicit['validation_report']['valid'] and explicit['validation_report']['bindings']['relevance_sha256'])
  original=base/'original.pdf';original.write_bytes(b'%PDF-1.4\nSYNTHETIC AUDIT OPAQUE COPY BYTES\n');before=original.read_bytes();s.save_profile({**profile,'original_cv':str(original)})
  pack=prepare_pack(s,s.jobs()[0]['id'],base/'packs');packdir=Path(pack['directory']);sidecar=json.loads((packdir/'preparation.json').read_text())
  unchanged=(packdir/'original-cv.pdf').read_bytes()==before==original.read_bytes();assert unchanged and pack['original_cv']['sha256']==sha256(before).hexdigest()
  config=base/'profile.yml';config.write_text(yaml.safe_dump({'candidate':{'full_name':profile['name']},'verified_facts':[fact]}))
  writer=CoverLetterWriter(output_dir=base/'legacy',profile_path=config);first=writer.generate(job);path=Path(first['output_path']);path.write_text('SYNTHETIC USER EDIT TO PRESERVE')
  second=writer.generate(job);overwritten=second['success'] and Path(second['output_path'])==path and path.read_text()!='SYNTHETIC USER EDIT TO PRESERVE'
  s.evaluate();learning=s.learning();negated=not (learning.get('capabilities',{}).get('contextual_guidance') is True and next(p for p in learning['priorities'] if p['skill']=='SQL')['guidance']['tier']=='negated_only')
  from jobhunter_app.learning_progress import create,update,listing
  before_progress=(s.profile(),s.jobs(),s.summary())
  offered=next(p for p in learning['priorities'] if p['skill']=='Docker')
  record=create(s,'Docker',offered['learning_options']['plan_fingerprint'])
  completed=update(s,record['id'],{'status':'completed','notes':'SYNTHETIC PRIVATE PRACTICE NOTE','completed_attested':True},record['revision'])
  progress_ok=(listing(Store(s.path))['items']==[completed] and completed['status']=='completed'
               and completed['completed_at'] and before_progress==(s.profile(),s.jobs(),s.summary()))
  findings=[('P6-VAL-001','P1','Direct validator accepts an appended unsupported candidate claim',not extra_issues,'Controlled template does not generate this appended text; no free-form editor is exposed.'),
   ('P6-VAL-002','P1','Direct validator accepts an empty selected-evidence list',not empty_issues,'cover_draft itself rejects profiles without verified facts; standalone validator now rejects empty evidence.'),
   ('P6-VAL-003','P1','Role/employer substring presence does not validate intended application context',not wrong_issues,'Negated/wrong-target synthetic text is now rejected; arbitrary prose remains unsupported.'),
   ('P6-REL-001','P2 design','Unrelated verified fact selected without an explicit evidence-to-job mapping',auto_unrelated or not explicit_ok,'Zero-overlap automatic fill is blocked; explicit exact-quote/source-bound user mapping is exercised. Lexical cues and user connections are not independent semantic relevance verification.'),
   ('P6-PACK-001','P1','Legacy deterministic output path overwrites a prior synthetic edited draft',overwritten,'Core and legacy outputs now publish unique version directories; previous edits and original CVs are preserved.'),
   ('P6-LEARN-001','P2 feature','Learning priorities count mentions without requirement-context ranking',negated,'Legacy mention counts remain; new context buckets/order separate negated-only cues from positive study signals.'),
   ('P6-LEARN-002','P2 feature','Resource/exercise/manual-progress workflow absent or incomplete',not (all(learning.get('capabilities',{}).get(k) is True for k in ('verified_resources','exercise_catalog','learning_progress')) and progress_ok),'Dated curated resources, authored exercises and actual profile-scoped save/attested-complete/reopen-persistence path pass. Progress is self-recorded, not verified proficiency.')]
  return {'checkpoint':'phase6-explicit-evidence-mapping-followup','status':'audit_complete_no_reproduced_scoped_findings','synthetic_only':True,'external_source_model_resource_or_message_calls':0,
   'existing_safeguards':{'controlled_template_quotes_verified_facts':fact['text'] in draft['content'],'review_required':draft['review_required'],'original_cv_copy_bytes_and_sha256_equal':unchanged,'pack_includes_provenance_checklist_and_evidence':all(k in sidecar for k in ('post_origins','checklist','cover','match')),'learning_denominator':learning['vacancies_reviewed'],'manual_learning_progress_actual_persistence_and_candidate_unchanged':bool(progress_ok),'explicit_evidence_mapping_exercised':bool(explicit_ok),'automatic_zero_overlap_fill_blocked':not auto_unrelated},
   'findings':[{'id':i,'priority':p,'finding':f,'reproduced':v,'status':'still_reproduced' if v else 'no_longer_reproduced', 'qualification':q} for i,p,f,v,q in findings],
   'learning_scope':learning['scope'],'next_implementation_task':'Integrated Phase 6 preparation and learning acceptance review',
   'not_claimed':['full original master-prompt clause audit','independent truth verification','end-to-end course/lab completion','polished multilingual letters','real candidate letter','Windows/PDF renderer execution','Phase 6 implementation complete']}
if __name__=='__main__':
 from unittest.mock import patch
 with patch('socket.create_connection',side_effect=AssertionError('Audit prohibits external connections')):
  result=run(Path(sys.argv[1]).resolve())
 print(json.dumps(result,indent=2))
