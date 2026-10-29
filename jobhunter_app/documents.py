"""Grounded preparation packs. CV bytes are copied, never rendered or rewritten."""
from __future__ import annotations
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import shutil


TEMPLATE_VERSION = 'grounded local template v2'
VALIDATOR_VERSION = 'deterministic cover contract v3'


def _text(value, limit, multiline=False):
    """Bound strings, reject hidden controls; preserve authorized text verbatim."""
    import unicodedata
    return (isinstance(value, str) and bool(value.strip()) and len(value) <= limit
            and not any((unicodedata.category(c).startswith('C') or c in '\u2028\u2029')
                        and not (multiline and c in '\n\t') for c in value))


def _authorized(profile):
    facts = profile.get('facts', [])
    if not isinstance(facts, list) or len(facts) > 100:
        return []
    # One unambiguous, stable first source record per exact text. No paraphrases.
    seen, records = set(), []
    for fact in facts:
        if (isinstance(fact, dict) and fact.get('verified') is True
                and _text(fact.get('text'), 2000, multiline=True)
                and _text(fact.get('source'), 2000, multiline=True)
                and fact['text'] not in seen):
            records.append(fact)
            seen.add(fact['text'])
    return records


def _render_cover(job, name, facts):
    """The sole supported prose contract; factual text is quoted, never expanded."""
    return (f'Dear Hiring Team,\n\nI am applying for the {job["title"]} position at {job["company"]}.\n\n'
            'The following source-backed examples from my background are provided for your review:\n\n' +
            '\n\n'.join('“' + text + '”' for text in facts) +
            '\n\nI would welcome the opportunity to discuss how my background could contribute to this role. '
            'Thank you for considering my application.\n\nKind regards,\n' + name)


def _digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(',', ':')).encode('utf-8')).hexdigest()


def validate_cover_report(content, job, profile, selected_facts, evidence_mapping=None):
    """Validate ONLY the exact supported template, not arbitrary natural language.

    A valid report binds this content to current user-attested evidence/targets.
    It is a reproducible snapshot, not a signature, truth or relevance verdict.
    Call again with current inputs after any edit; human review is always needed.
    """
    checks, issues = [], []
    passed_messages = {
        'candidate_identity': 'Candidate name satisfies the supported label contract',
        'application_target': 'Exact expected role/employer opening paragraph checked',
        'selected_evidence': 'One to three distinct authorized evidence texts selected',
        'exact_quotations': 'Selected evidence appears as exact quotations',
        'supported_template': 'Entire draft matches the supported template and signature',
        'word_limit': 'Draft is nonempty and within 350 words',
        'target_context': 'Supplied job context is Unicode text',
        'evidence_relevance': 'Evidence connection checked within its declared scope; human review required',
    }
    def check(code, passed, message):
        checks.append({'id': code, 'passed': bool(passed),
                       'message': passed_messages[code] if passed else message})
        if not passed:
            issues.append(message)
    objects = isinstance(job, dict) and isinstance(profile, dict)
    job = job if isinstance(job, dict) else {}
    profile = profile if isinstance(profile, dict) else {}
    name = profile.get('name')
    identity_ok = objects and _text(name, 300)
    check('candidate_identity', identity_ok, 'Cover drafts require a nonblank single-line candidate name')
    target_ok = objects and _text(job.get('title'), 1000) and _text(job.get('company'), 1000)
    # Require the target in its dedicated opening paragraph, never anywhere else.
    paragraphs = content.split('\n\n') if isinstance(content, str) else []
    opening = (f'I am applying for the {job["title"]} position at {job["company"]}.'
               if target_ok else None)
    check('application_target', target_ok and len(paragraphs) > 1 and paragraphs[1] == opening,
          'Employer or role mismatch')
    authorized = {f['text']: f for f in _authorized(profile)}
    selection_ok = (isinstance(selected_facts, list) and 1 <= len(selected_facts) <= 3
                    and all(isinstance(f, str) and f in authorized for f in selected_facts))
    selection_ok = selection_ok and len(set(selected_facts)) == len(selected_facts)
    check('selected_evidence', selection_ok,
          'Unsupported candidate claim: select one to three distinct source-backed, explicitly verified facts')
    quotations_ok = (selection_ok and isinstance(content, str)
                     and all('“' + f + '”' in content for f in selected_facts))
    check('exact_quotations', quotations_ok, 'Selected evidence must appear as exact quotations')
    expected = (_render_cover(job, name.strip(), selected_facts)
                if identity_ok and target_ok and selection_ok else None)
    check('supported_template', isinstance(content, str) and expected is not None and content == expected,
          'Draft differs from the supported template; added, removed or edited prose is not validated')
    word_count = len(content.split()) if isinstance(content, str) else 0
    check('word_limit', isinstance(content, str) and 0 < word_count <= 350,
          'Draft exceeds 350 words or is empty; shorten source facts')
    target = {k: job.get(k, '') for k in ('title', 'company', 'url', 'description')}
    context_ok = all(isinstance(v, str) and not any(0xD800 <= ord(c) <= 0xDFFF for c in v)
                     for v in target.values())
    check('target_context', context_ok, 'Job URL and description must be valid Unicode text when supplied')
    relevance = None
    relevance_ok = False
    try:
        from .evidence_mapping import resolve, automatic
        linked, relevance = (resolve(job,profile,evidence_mapping) if evidence_mapping is not None
                             else automatic(job,profile,selected_facts))
        relevance_ok = selection_ok and [f['text'] for f in linked] == selected_facts
    except (ValueError,TypeError,KeyError,UnicodeError):
        pass
    check('evidence_relevance', relevance_ok, 'Evidence connection is missing, stale or invalid; review an explicit evidence map')
    bindings = None
    if not issues:
        evidence = [{'text': f, 'source': authorized[f]['source'], 'verified': True} for f in selected_facts]
        bindings = {'content_sha256': sha256(content.encode('utf-8')).hexdigest(),
                    'target_sha256': _digest(target), 'candidate_sha256': _digest(name.strip()),
                    'evidence_sha256': _digest(evidence), 'relevance_sha256': _digest(relevance), 'selected_count': len(evidence),
                    'contract_sha256': _digest({'template': TEMPLATE_VERSION, 'validator': VALIDATOR_VERSION,
                                               'target': target, 'name': name.strip(), 'evidence': evidence, 'relevance': relevance})}
    return {'validator': VALIDATOR_VERSION, 'supported_template': TEMPLATE_VERSION,
            'valid': not issues, 'review_required': True,
            'truth_status': 'Source-backed user attestation; not independent fact or relevance verification',
            'checks': checks, 'issues': issues, 'word_count': word_count, 'bindings': bindings, 'relevance': relevance}


def validate_cover(content, job, profile, selected_facts, evidence_mapping=None):
    """Compatibility wrapper: empty list means supported-contract validation passed."""
    return validate_cover_report(content, job, profile, selected_facts, evidence_mapping)['issues']


def cover_draft(job: dict, profile: dict, evidence_mapping=None) -> dict:
    """Conservative English template, exact evidence binding and required review."""
    if not isinstance(job, dict) or not isinstance(profile, dict):
        raise ValueError('Cover drafts require job and profile objects')
    name = profile.get('name')
    verified = _authorized(profile)
    if not _text(name, 300) or not verified:
        raise ValueError('Cover drafts require a candidate name and source-backed, explicitly verified facts')
    if not _text(job.get('title'), 1000) or not _text(job.get('company'), 1000):
        raise ValueError('Employer or role mismatch')
    from .evidence_mapping import resolve, automatic
    ranked, relevance = (resolve(job,profile,evidence_mapping) if evidence_mapping is not None else automatic(job,profile))
    facts = [f['text'] for f in ranked]
    content = _render_cover(job, name.strip(), facts)
    report = validate_cover_report(content, job, profile, facts, evidence_mapping)
    if not report['valid']:
        raise ValueError('; '.join(report['issues']))
    return {'content': content, 'method': TEMPLATE_VERSION, 'review_required': True,
            'evidence': ranked, 'evidence_mapping': deepcopy(evidence_mapping), 'relevance': relevance, 'validation': 'Supported template and exact evidence binding checked; candidate review still required',
            'validation_report': report, 'word_count': report['word_count']}


def prepare_pack(store, job_id: str, root: Path, profile_id='default', evidence_mapping=None):
    job = store.job(job_id)
    profile = store.profile(profile_id)
    from .posts import origins
    from .pack_management import digest as snapshot_digest
    post_origins = origins(store, job_id)
    snapshot = snapshot_digest({'job': job, 'profile': profile, 'post_origins': post_origins})
    draft = cover_draft(job, profile, evidence_mapping)
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    from .pack_management import stage_version, seal_pack, publish_version, context
    version_id, folder = stage_version(root)
    original = profile.get('original_cv')
    original_metadata = None
    try:
        if original:
            path = Path(original).expanduser().resolve()
            if path.suffix.lower() != '.pdf' or not path.is_file() or path.stat().st_size > 20 * 1024 * 1024:
                raise ValueError('Original CV must be an existing PDF of at most 20 MiB; no conversion is permitted')
            with path.open('rb') as stream:
                if stream.read(5) != b'%PDF-':
                    raise ValueError('Original CV is not a PDF')
            copied = folder / 'original-cv.pdf'
            shutil.copyfile(path, copied)
            digest = sha256(path.read_bytes()).hexdigest()
            if sha256(copied.read_bytes()).hexdigest() != digest:
                raise ValueError('Original CV copy integrity check failed')
            original_metadata = {'filename': copied.name, 'sha256': digest, 'unchanged': True}
        (folder / 'cover-letter-draft.txt').write_text(draft['content'], encoding='utf-8', newline='\n')
        from .matching import match_job
        data = {'post_origins': post_origins, 'job': job, 'match': match_job(job, profile), 'cover': draft,
                'original_cv': original_metadata,
                'checklist': ['Confirm employer and vacancy are still open', 'Review mandatory requirements and uncertainties',
                              'Review cover letter facts and language', 'Select original CV manually if absent',
                              'Apply manually; this program never submits applications']}
        (folder / 'preparation.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        seal_pack(folder, version_id, job_id, profile_id, snapshot, original_metadata is not None)
        if context(store, job_id, profile_id) != snapshot:
            raise ValueError('Pack inputs changed during creation; generate again manually')
        folder = publish_version(root, folder, version_id)
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    return {'directory': str(folder), 'original_cv': original_metadata, 'review_required': True,
            'validation_report': draft['validation_report'], 'version_id': version_id, 'review_state': 'pending'}
