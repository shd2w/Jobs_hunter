"""Truthful, local cover-letter drafts from explicitly verified profile facts."""
import json
from hashlib import sha256
from pathlib import Path
import yaml
from jobhunter_app.documents import cover_draft


class CoverLetterWriter:
    def __init__(self, cv_path='cv.md', output_dir='output', profile_path='config/profile.yml'):
        self.output_dir = Path(output_dir)
        self.profile_path = Path(profile_path)

    def generate(self, job, evaluation=None, evidence_mapping=None):
        config = yaml.safe_load(self.profile_path.read_text(encoding='utf-8')) or {} if self.profile_path.exists() else {}
        candidate = config.get('candidate', {})
        profile = {'name': candidate.get('full_name', ''), 'facts': config.get('verified_facts', [])}
        try:
            result = cover_draft(job, profile, evidence_mapping)
        except (ValueError, KeyError, TypeError) as exc:
            return {'success': False, 'error': str(exc)}
        from jobhunter_app.pack_management import stage_version, publish_version, write_json, now
        import shutil
        key = sha256((job.get('url', '') + job['company'] + job['title']).encode()).hexdigest()[:20]
        version_id, stage = stage_version(self.output_dir)
        try:
            path = stage / f'{key}-cover.md'
            path.write_text(result['content'], encoding='utf-8', newline='\n')
            write_json(path.with_suffix('.evidence.json'), result)
            write_json(stage/'draft-version.json', {'format': 1, 'version_id': version_id,
                       'created_at': now(), 'kind': 'legacy-cover-draft', 'review_required': True,
                       'artifacts': {p.name: sha256(p.read_bytes()).hexdigest() for p in stage.iterdir()}})
            folder = publish_version(self.output_dir, stage, version_id, 'cover')
        except Exception:
            shutil.rmtree(stage, ignore_errors=True)
            raise
        return {**result, 'success': True, 'output_path': str(folder / path.name),
                'version_id': version_id, 'review_state': 'pending', 'model_used': 'local-grounded-template'}
