# F-05 - PDF CV generation

## Purpose and scope
Render a tailored or original CV as an ATS-friendly A4 PDF with WeasyPrint.

## Users and triggers
The CV tailoring flow and the app's Use my CV as is action.

## Normal workflow
Markdown CV -> HTML -> PDF with right-aligned dates via table layout (README Pipeline Step 5).

## Alternate and failure workflows
If WeasyPrint or its system libraries are missing, PDF generation fails; the Setup tab shows whether PDF support works (README easy mode).

## Requirements and acceptance criteria
Must remain functional (docs/PROMPT.md section 2). Only created on explicit user action.

## UI states
Not a user interface feature. No UI states apply.

## Data contracts and side effects
Writes PDF files under `output/`. No network.

## Architecture and files
Registered files (see FILE_REGISTRY.yml):
- `utils/pdf_generator.py`
- `CV_Example.py`

Work packages that mention these files: WP-00-03. Decisions: DEC-019. Gates: G5, G7.

## Security and privacy
Output PDFs contain S3/S4 personal data and stay local, untracked (`output/` is ignored).

## Tests and evidence
- `tests/test_ui_integration.py`

Evidence: no evidence records exist for this feature yet. Test results of the review container are in MEMORY/KNOWN_ISSUES.md (KI-001); no baseline run was made.

## Known limitations and open decisions
- WeasyPrint needs a GTK runtime on Windows; the Windows result is unverified (PCD-011, WP-00-03).
- CV_Example.py is a stand-alone sample script with the owner's contact details (KI-004); it is not part of the pipeline.

## Provenance
Drafted 2026-11-10 by claude-code / claude-sonnet-5-5 from README.md, docs/PROMPT.md, module docstrings, test headers, the file registry and the governance suite. The code was not read line by line and nothing here was run; status: unreviewed draft. Work-package links are derived by name mention in GOV-04 rows, not confirmed by the owner.
