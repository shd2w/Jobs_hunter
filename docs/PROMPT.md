# JobHunter — working prompt (contract version)

Paste this at the start of every session. It replaces the long "master prompt". Rules are short on purpose: a rule you can't test is a wish.

## 1. What this project is
JobHunter finds jobs, scores them with AI (1–5, five weighted dimensions), tailors a CV and writes a cover letter per job, notifies via Telegram, tracks everything in Excel/JSON, and exports `data/application_queue.jsonl` for UniversalAutoApplier. The owner applies by hand; the tool prepares.

## 2. MUST KEEP (do not delete, stub, rename or "retire" — ever)
| Feature | Where | Guard |
|---|---|---|
| Scan (JobSpy, Workday, extra ATS boards + feeds) → filter → dedup | `run_scan.py`, `scanners/`, `utils/filters.py`, `utils/dedup.py` | `tests/test_filters.py`, `test_dedup.py`, `test_bridge.py`, `test_extra_sources.py` |
| AI scoring, 5 dimensions 30/20/20/20/10, German policies | `agents/evaluator.py`, `run_evaluate.py` | `tests/test_german_policy.py` |
| Multi-provider routing, key rotation (up to 4 OpenRouter + 2 Google) | `agents/smart_router.py`, `*_client.py` | add tests, never remove keys support |
| **CV tailoring** (AI JSON-patch; dates/education/languages never touched) | `agents/cv_tailor.py` | must remain functional |
| **PDF generation** (WeasyPrint, ATS layout) | `utils/pdf_generator.py` | must remain functional |
| Cover letters | `agents/cover_letter.py` | must remain functional |
| Telegram, Excel DB, JD cache | `utils/telegram.py`, `excel_export.py`, `jd_cache.py` | |
| UAA queue contract + identity hashes | `utils/queue_exporter.py` | `test_queue_exporter.py`, `test_identity_golden_contract.py`, `test_export_queue_wq2.py` |
| Original CLI: `run_scan/evaluate/all/export_queue/health.py` flags | root | flags unchanged |

A change that touches a MUST-KEEP file needs: a one-line reason, the failing test or bug it fixes, and a before/after line count in the report. **Any file that shrinks by more than 20% is a stop-and-ask.**

## 3. Decisions already made (do not ask again)
- The owner **chooses per job** whether to create a CV (tailored or as-is) and a cover letter. **There is no automatic creation**: documents are created only by an explicit per-job user action. The earlier opt-in setting `evaluation.create_cv` / `auto_cv_threshold` is deprecated and removed in phase P1 (see docs/02 RC-1).
- Ranking is required: best score first, ties by skills match, then newest posting; user can re-weight the five dimensions.
- Local mode: 127.0.0.1 only, no accounts, no paid services, stdlib server. A hosted multi-user mode is a **staged track** (P13–P16 in docs/07) that starts only after the owner says go. New dependencies need an approved decision: the approved set is docs/02 D7 plus `tldextract` in offline mode (OT-18).
- Private data (`.env`, `cv.md`, `data/`, `output/`, `reports/`, `logs/`) is never committed and never printed.
- The AI never invents experience, dates, employers, skills or language levels. Tailoring may only rephrase bullets, reorder skills and select projects.
- Do not use any browser/stealth tricks to bypass a job site's blocking; log it and move on.

## 4. OPEN decision for the owner (ask once, then record the answer here)
- `agents/evaluator.py` hard-codes the candidate's languages ("German C1, never penalize German"). The CV/profile says German B2 (certified), C1 (self-assessed). Choose: keep as is / read levels from `config/profile.yml`. **Answer: ____**
- Other open owner decisions are tracked in docs/FINAL_SYSTEM_STRATEGY_AND_DESIGN.md §9 (OT-0…OT-19) and docs/08 §2.3 (C-1…C-5). Answers recorded there are binding for the next session.

## 5. How a session runs
1. **Read-only first.** Run `git status`, `python -m pytest -q`, list what you will touch. No edits yet.
2. Work on **one stage** from section 7 on its own branch. Small commits.
3. After each commit run the full test suite. Original tests must pass **unchanged**.
4. If you do not know something (a provider's current limits or error codes, a site's HTML, a library API), say "I don't know", read the official docs or the code, or ask. Never guess and never write a plausible-looking answer.
5. If a test cannot be run here (needs real API keys, Telegram, live sites), say so. A mocked test is labelled **mocked**, never "verified".
6. Do not mark anything done unless you ran it and show the output.

## 6. Report format (every session, max one page)
- `git diff --stat main..HEAD` and the list of files **deleted or shrunk >20%**.
- Tests: total / passed / new; the exact command.
- Done / Not done / Not verifiable here (three short lists).
- Anything you changed that was not asked for, with reason.

## 7. Stages (S1–S5 below are a summary of the first bug-fix scope only; the authoritative plan is the phased roadmap P0–P16 in docs/07_IMPLEMENTATION_ROADMAP.md; one phase per session; do not start the next until the owner says go)
- **S1 AI reliability.** In `smart_router.py` and clients: classify HTTP 429 vs 5xx vs 4xx vs malformed JSON; exponential backoff with jitter for transient only; cooldown per key; never retry permanent errors; clear error text surfaced in the UI. Tests with mocked responses for each class and for retry exhaustion.
- **S2 Data safety.** Atomic writes for `pipeline.md`, `jd_cache.json`, Excel; backup before rewrite; no duplicate rows; test a crash mid-write.
- **S3 App polish.** (Base app exists in `jobhunter_ui/`.) First-run wizard, clearer errors, undo for status changes, bulk actions (select several → create CVs), saved filters, export ranked list to CSV. Browser test for every flow.
- **S4 Scoring quality.** Explainable scores (which JD phrases drove each dimension), configurable weights saved in profile, re-score a job on demand, flag stale/expired postings.
- **S5 Operations.** Docker/scheduler parity with the app, health page in the UI, log rotation, README for a second person to install from scratch on Windows and Linux.

## 8. Stop conditions
Stop and ask if: a MUST-KEEP file would shrink >20%, a test must be changed or deleted to pass, a new dependency is needed, a secret might be printed, or the stage needs more than one session.
