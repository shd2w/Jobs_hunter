# Dashboard / CLI discrepancy audit

Baseline: `eaf0907c25b974435f44e3961a92786567674072`. Audit performed against implementation, not the earlier autonomy proposals. No credentials or live AI calls used. This is an implementation ledger, not a claim of provider availability.

## Comparison matrix (pre-repair)

| Feature | Dashboard | CLI / legacy | Shared boundary | Verified difference / resolution |
|---|---|---|---|---|
| Local matching | `web.py:Handler.do_POST /api/match` → `Store.evaluate` | `run_local.main match`; `run_all.main` pending match | `matching.match_job` | Already shared, but NOT legacy AI suitability. Keep explicit lexical ranking and raw matches contract. |
| AI evaluation | No endpoint or display | `run_evaluate.evaluate_job` → `agents.evaluator.Evaluator.evaluate` → `SmartRouter.evaluate` | None at application layer | Add explicit opt-in AI evaluation service, SQLite results and actual method display; share weights and German policy with legacy runner. |
| Candidate context | Strict SQLite profile, verified/unverified facts (`Store.save_profile`) | YAML + cv.md (`Evaluator.__init__`) | Different input contracts | Explicit context adapter; never silently read private cv.md for dashboard profiles. Unknown education/languages remain unknown. |
| Scoring | Lexical skill % / weighted preference % (`matching.match_job`) | AI weighted 1–5: skills .30, education .20, location .20, language .20, growth .10 | None | Preserve distinct scales; no conversion of lexical % to AI 1–5. Threshold 3.5 is AI-only. |
| Exclusions | Local title/company/location constraints | German policy only in `run_evaluate.evaluate_job` | None | Apply local hard exclusions before AI in new service, share explicit German policy; legacy retains document/Telegram adapters. |
| Evaluation durability | `matches` table | `utils.evaluation_store.append_evaluation`, Markdown/report files | Distinct legacy outputs | Add backed-up versioned evaluation history extension; preserve legacy JSON/tracker/export contracts. Results fingerprint input and expose staleness. |
| Profile search | `AutomaticDiscovery._profile_search` → `discovery_run.run` | `run_local discover` → same runner | Finite intent orchestration, defaults 12 attempts/120s | Already same core; HTTP button has no CLI override controls. Do not call different presentation defaults full option parity. |
| Source scan | `web.py` asynchronous task → `sources.scan` / `source_health.batch` | `run_local scan`, `scan-batch` | Same adapters, gates, intake, checkpoints | Manual scans do not automatically match; automatic worker calls `_match_if_needed`. Preserve retrieval/local matching as distinct stages and expose this boundary. |
| Original pipeline | Optional Markdown/cache mirror | `run_scan.py`, `run_all.py`, `run_evaluate.py` | Registry / compatibility mirror | Legacy file queue is not SQLite job state; do not destructively migrate history or pretend all side effects identical. |
| Pagination | `static/discovery.js` interprets bounded selection as “more pages remain” | Adapter booleans `coverage_complete`, `bounded_selection` | `Collection`, `sources._scan_locked` | Invalid implication: JobSpy reports bounded regardless of actual next page. Introduce evidence-based state and backend messages. |
| Native pagination | Source health shows one generic label | `collection.collect` | Jobicy cursor, Arbeitnow links, USAJOBS total, SmartRecruiters pending details | Missing metadata currently confused with exhaustion in some adapters. Separate explicit end / total / next / unknown / pending details. |
| Other collectors | Same registered sources | Scrapling fixed HTML, structured HTML, authorized boards, Workday, official social API | Collection → shared intake | Recipe continuation and remaining detail work differ from provider-confirmed next pages. Fixed page bounds do not prove market completeness. |
| Dedupe | `Store.ingest`, canonical URL/aliases/sightings | Same for local CLI; legacy cache/history remains separate | `store.py`, `opportunity_identity.py` | Canonical inserts ≠ independently verified unique opportunities. Correct labels, preserve historical aliases. |
| Run management | In-memory manual task; persisted source runs; separate automatic coordinator | Synchronous local commands; finite search tables; legacy lock | Scan file lock / gates; discovery run tables | Durable source/search outcomes exist, generic HTTP task is not durable run history. No fabricated percent progress. |
| Error reporting | Discovery tab suppresses structured failure hints | Source metrics include safe code/stage/http/hint | `sources._scan_locked` | Render structured diagnostic hints; failed retrieval must not become successful empty results. |
| Batch result | List of source results/errors and cancel flag | Same service | `source_health.batch` | No authoritative overall status/counts. Add summary without removing original fields. |
| Exports / notifications | Local manual adapters | Local CLI same; legacy evaluator triggers Telegram/cover letters/JSON/queue | Existing export modules | Keep opt-in evaluation separate from document generation, notifications and submission. Do not introduce automatic paid delivery. |
| Other local workflows | API handlers | CLI handlers | `followups`, `workflow`, `digests`, `documents`, `pack_management`, `calendar_export`, `learning`, `saved_searches` | Shared module functions already exist. No evidence justifies rewriting these unrelated business rules. |

## Source-by-source continuation evidence

- `collection.py:collect`: Jobicy validates mandatory hasMore + bounded nextCursor and refuses repeated/expired cursor. Arbeitnow validates increasing next page. SmartRecruiters persists offset/pending detail IDs and total; HN persists seen IDs. USAJOBS uses Page/ResultsPerPage and reported total. Missing metadata is not proof of end.
- `expanded_sources.py:collect`: JobSpy offset/page budgets are local; response list has no confirmed total or next token. Public RemoteOK/WWR responses are snapshots, not the whole vacancy universe.
- `scrapling_engine.py:collect`, `authorized_boards.py:collect`, `structured_source.py:collect`: configured page recipes, extracted next links and pending details differ; inspect checkpoint before offering continuation. Never treat any nonempty checkpoint as sufficient.
- `workday_source.py:collect`: existing direct scanner bounded to five listing pages/100 details; wrapper does not expose provider continuation receipt. Mark unknown, do not fabricate a cursor.
- `platform_posts.py:collect`: official API cursor where supplied; Telegram update offset is not evidence of more job listings. Imported posts are not automatically verified vacancies.

## Failure and data constraints

`Store` schema remains v5; preserve existing DB and migration tests. New optional evaluation storage needs a backup before first DDL and must not be initialized by GET. `Evaluator` currently writes a report before legacy durable JSON commit; tracker only updates after persistence. Legacy JD fetch handles expired/401/403/429 distinctly. Preserve that behavior and original-CV prohibition. Tests must use controlled provider responses, not independently nondeterministic live model calls.

Live provider access, user Codespace runtime, real AI routing/quotas, Windows and all-source market coverage remain unverified. Installed JobSpy/Scrapling versions prove installation only.

## Implemented resolutions / follow-up evidence

See `dashboard_cli_consistency.md` for actual ownership and `dashboard_cli_progress.md` for validation. Additional defects found after the initial matrix:
- `static/discovery.js` called staging-only `/api/posts/stage` while presenting automatic processing. New process endpoint and UI now match CLI posts-process; explicit staging remains.
- CLI feed-import omitted `auto_add=True` and selected profile while HTTP passed both. Corrected and tested against independent equivalent DBs.
- `static/app.js:scanSummary` also asserted more pages from bounded_selection; replaced alongside both source-health views.
- `run_all._run_pipeline` accepted returned unsuccessful evaluation records and still exported/printed completion; it now propagates failure, preserves partial scan status and stops misleading queue publication.
- `pipeline.export_uaa` only saw historical evaluations; it now explicitly projects current nonstale shared AI receipts, never lexical/fallback values or an older score superseded by a current nonexportable result.

Preserved distinctions: CLI advanced search controls, legacy YAML/CV and file delivery workflow, new per-job HTTP evaluation and SQLite profile are explicit interfaces with different optional capabilities. Controlled equivalent-input parity is verified; claiming all legacy options/delivery surfaces or live providers fully equivalent would exceed this evidence.
