"""Optional cover-letter PDF renderer. All CV generation is retired."""
from pathlib import Path
from html import escape
import yaml


def generate_cv_pdf(*args, **kwargs):
    return {'success': False, 'error': 'CV generation is retired; provide an original PDF unchanged.'}


def _md_to_html_cv(*args, **kwargs):
    raise RuntimeError('CV generation is prohibited')


def _deny_external_resource(url, *args, **kwargs):
    raise ValueError('External resource loading is disabled')


def _md_to_html_cover_letter(md_content, candidate_name='', company='', role='', contact=''):
    body = '\n'.join('<p>' + escape(p).replace('\n', '<br>') + '</p>' for p in md_content.split('\n\n'))
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><style>
    @page {{size:A4;margin:22mm}} body {{font:11pt/1.5 Arial,sans-serif;color:#2c2c2b}}
    h1 {{font-size:18pt}} .meta {{color:#555;margin-bottom:24px}} p {{margin:0 0 14px}}
    </style></head><body><h1>{escape(candidate_name)}</h1><div class="meta">{escape(contact)}<br>
    {escape(role)} — {escape(company)}</div>{body}</body></html>'''


def generate_cover_letter_pdf(md_content, output_path, company='', role=''):
    try:
        from weasyprint import HTML
    except ImportError:
        return {'success': False, 'error': 'Optional WeasyPrint is not installed; use the text draft'}
    path = Path('config/profile.yml')
    profile = yaml.safe_load(path.read_text(encoding='utf-8')) or {} if path.exists() else {}
    candidate = profile.get('candidate', {})
    try:
        html = _md_to_html_cover_letter(md_content, candidate.get('full_name', ''), company, role)
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        HTML(string=html, url_fetcher=_deny_external_resource).write_pdf(output)
        return {'success': True, 'output_path': str(output), 'size_bytes': output.stat().st_size}
    except Exception as exc:
        return {'success': False, 'error': f'Optional PDF generation failed ({type(exc).__name__})'}
