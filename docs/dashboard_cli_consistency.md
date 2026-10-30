# Dashboard / CLI consistency

Build: `dashboard-cli-consistency-1`. This document describes implemented behavior, not a live-provider qualification claim. Baseline audit: [dashboard_cli_audit.md](dashboard_cli_audit.md). Progress and limits: [dashboard_cli_progress.md](dashboard_cli_progress.md).

## Ownership / architecture

```text
HTTP POST /api/evaluate ─┐
                        ├─ evaluation_service.evaluate(Store, job, profile, options)
run_local.py evaluate ───┘       ├─ explicit candidate context (no ambient CV read)
                                ├─ local_result → matching.match_job
                                ├─ evaluate_prepared → Evaluator.from_context → SmartRouter
                                ├─ weighted_score + apply_policy
                                └─ versioned SQLite receipt + local matches (when applicable)

legacy run_evaluate.evaluate_job
  → cache / permitted JD retrieval
  → same evaluation_service.evaluate_prepared + weighted_score + apply_policy
  → compatibility delivery, JSON evaluation store, tracker / Markdown

HTTP profile-search → AutomaticDiscovery queue ─┐
                                               ├─ discovery_run.run → sources.scan
run_local.py discover ──────────────────────────┘
HTTP manual scan / batch ───────────────────────┐
                                               ├─ sources.scan / source_health.batch
run_local.py scan / scan-batch ─────────────────┘
  → same approval, cooldown, family gate and scan lock
  → source adapter → Collection + source-specific metadata
  → pagination.receipt → atomic Store.ingest + committed checkpoint + run receipt
```

Relevant anchors:
- `jobhunter_app/evaluation_service.py`: `EvaluationOptions`, `candidate_context`, `evaluate_prepared`, `evaluate`, `local_batch`, `latest`, `summary`.
- `agents/evaluator.py`: `from_context`, `evaluate` (strict model JSON validation, shared recomputed weighted score). Existing `SmartRouter.evaluate` remains the single provider-routing implementation.
- `Store.evaluate` delegates to `local_batch`; raw `matches` and schema v5 remain compatible. Local semantic reranking remains a separate explicitly local feature, not AI suitability.
- `jobhunter_app/pagination.py`: `state` validates tri-state evidence and generates all continuation messages; `receipt` adapts registered collection families.
- `jobhunter_app/collection.py:collect`: explicit Jobicy cursor/hasMore, Arbeitnow links.next, SmartRecruiters known total/pending details, USAJOBS reported total. HN pending comments are remaining detail work.
- `expanded_sources.collect`: JobSpy budgets and valid offset recipe are separate from next-page evidence. No upstream next token/total is invented.
- `source_health.health/batch`, `runtime_status.status`, `AutomaticDiscovery.status`: expose the shared receipt. `static/discovery.js`, `automatic.js` and `app.js` render backend messages, not inferred next pages.

## Evaluation inputs, methodology and configuration

Both new interfaces call exactly `evaluate` with the same Store profile, normalized job and `EvaluationOptions`. Defaults: local method; provider consent false; fallback false; AI threshold 3.5; German policy accept_all. Unknown options, non-boolean flags and nonfinite/out-of-range thresholds are rejected. CLI and HTTP use the same option validator; the UI passes values, never calculates scores.

SQLite context uses explicit skills/languages/preferred roles/locations and **verified** fact text only. Unverified facts and original CV filesystem paths are not sent. Unknown education/languages stay unknown. Legacy YAML/CV input remains a deliberately different, explicit compatibility context: identical filenames do not establish identical candidate inputs. The arbitrary Oman/Muscat/Remote prompt default was removed. No profile is silently merged with a private cv.md.

AI dimensions remain skills .30, education .20, location .20, language .20, growth .10. Model-reported global score is retained for diagnosis but recomputed from validated 1–5 dimensions. German policy is applied once by the service; rejection is explicitly marked, pre-policy score preserved, compatibility score 0/recommendation skip_german retained. The bilingual policy only tests vacancy text mentions, not candidate proficiency or legal eligibility. Local hard exclusions short-circuit AI in the SQLite service.

Lexical ranking percentages have **no** conversion to AI 1–5. `method`, `requested_method`, `score_scale`, `classification`, policy, threshold and actual model remain visible. AI output validation is unchanged and strict. Fallback is per-request opt-in and never occurs without provider consent merely because fallback is checked. Failed provider responses contain no persisted raw body or credential-bearing exception text.

Provider routing/models continue to resolve in `agents/smart_router.py` and its existing local configuration/environment. Both CLI and HTTP use that same resolver; no provider credentials are accepted by the browser and GET does not instantiate clients. Installing JobSpy/Scrapling does not configure AI. No AI calls run from the automatic discovery timer. This repair does not grant permission for paid usage.

## Commands and HTTP

```bash
# Global arguments precede the command. No provider call:
python run_local.py --db data/jobhunter.sqlite3 --profile-id default evaluate JOB_ID --method local

# Explicit provider authorization; may incur provider costs:
python run_local.py --db data/jobhunter.sqlite3 --profile-id default evaluate JOB_ID \
  --method ai --allow-provider --threshold 3.5 --german-policy accept_all

# Optional local fallback is distinctly labeled:
python run_local.py --db data/jobhunter.sqlite3 evaluate JOB_ID --method ai --allow-provider --fallback
python run_local.py --db data/jobhunter.sqlite3 evaluation JOB_ID
```

`POST /api/evaluate`: `{ "id": "JOB_ID", "options": { "method": "ai", "allow_provider": true, "fallback": false, "threshold": 3.5, "german_policy": "accept_all" } }`. Existing Host/Origin/CSRF protections apply. `GET /api/evaluation?id=...` is read-only. The opportunity dialog displays persisted receipt/method/model/scale and explicit consent; changing opportunity clears consent. Requests are synchronous per job; the dialog shows waiting, not fictitious percentage progress. A concurrent evaluation is rejected consistently via the shared file lock. A second browser tab may read the durable running receipt. No automatic retry of an AI request.

CLI `evaluate` returns exit 2 for pending, failed or partial results, while emitting the structured receipt; successful AI/local/explicit fallback returns 0. HTTP returns the receipt with its explicit processing status (200 means request handled, not AI success). Input/lock conflicts are errors, not successful empty evaluations.

## Persistence and recovery

Original Store schema stays v5. The first explicit evaluation action, under a cross-process evaluation lock, creates a unique online backup before adding `evaluation_meta(version=1)` and `evaluations`. GET never creates the extension. History is append-per-request; start is committed before provider use, completion and local-match projection commit together. Failure to persist completion propagates instead of claiming success. A running receipt with no lock owner is exposed as interrupted/partial; the next authorized action closes interrupted receipts without inventing a result.

Fingerprints cover job input, profile (except the unused original-CV path), service version and resolved options. Latest reads expose `stale`; changes during a provider call result in partial/stale instead of a current recommendation. Profile changes and semantic job updates invalidate raw local matches through the existing Store contract. AI receipts never overwrite lexical match data with a 1–5 value.

`Store.summary()['evaluations']` separates latest current status counts, stale receipts and jobs never requested. These are not “all AI evaluated” counts. `pipeline.export_uaa` accepts current completed nonstale shared AI receipts or legacy historical evaluations; current local/fallback/failed/stale results cannot resurrect an older AI score. Existing original-PDF/document/identity/threshold restrictions and nonclobber publication remain enforced; evaluation does not manufacture missing documents. Legacy JSON/tracker/Telegram/cover-letter adapters remain compatible and separate from new per-job evaluation.

## Pagination / continuation semantics

| Field | Meaning |
|---|---|
| has_next_page | true/false only from explicit source evidence; null otherwise |
| continuation_available | validated committed token/offset/recipe or observed remaining detail work can be requested; does not prove more vacancies |
| page_limit_reached | observed configured page budget consumed; does not prove next page |
| result_limit_reached | returned result budget consumed; does not prove more results |
| source_exhausted | explicit end metadata for this search/pass, never all vacancies worldwide |
| continuation_unknown | neither next-page nor explicit-end evidence available |
| partial / failed / cancelled | separate source/error/interruption state |
| pages_retrieved | observed listing pages, or null if not instrumented; detail requests are not listing pages |
| pending_details | already observed detail/comment work, not proof of another listing page |

JobSpy offsets are a local recipe, not provider-confirmed continuation. Arbeitnow without links.next and USAJOBS without total are unknown, not explicit last page. SmartRecruiters missing total is not proof of exhaustion; detail-only resumption records zero listing pages. HTML next links/recipes establish only configured-route behavior. Workday's existing bounded direct scanner does not expose a verifiable next receipt: unknown is preserved. Public feeds/API responses are snapshots. Official post cursors are source-specific; Telegram update offsets do not establish additional job listings.

Old `coverage_complete` / `bounded_selection` remain for compatibility. They are not authoritative pagination fields and no UI uses them to assert that more pages remain. Historical runs without a v1 receipt display unknown, not inferred success. Failed/cancelled scans preserve the last committed checkpoint; their latest attempt does not pretend a failed request established new continuation evidence. Existing gates are not bypassed by reset/reapproval.

## Run status and reporting

Finite profile-search state remains persisted in search_runs/search_tasks. Manual HTTP source task adds status and start/finish timestamps while durable source runs remain authoritative; the in-memory HTTP task envelope is not a durable execution queue. Source scan results now carry the persisted source status. Batch summary reports requested/attempted/failed/partial/deferred and distinguishes failed/partial/cancelled/success. Valid sources continue after a sibling failure.

Legacy `run_all` no longer exports a new queue or prints full completion after a returned failed evaluation. Partial scan status survives final pipeline results; command exit is nonzero for partial/failed. `run_evaluate` also exits nonzero on returned evaluation failures. Already persisted successful evaluations remain available; unsuccessful jobs remain pending.

Counters distinguish received/raw/valid/invalid, filtered title/location, canonical inserts, existing observations, requests and duration where the adapter measured them. A canonical URL insert is not proof of a unique relevant vacancy. Unknown page counts remain unknown. Source-health detail displays safe failure code/stage/HTTP/hint; normal UI does not dump exception bodies. Manual scan does retrieval; optional matching remains an explicit stage, with automatic search's local pending matching reported separately. Neither path silently claims cloud evaluation.

## Additional parity corrections

`POST /api/posts/process` and CLI `posts-process` call the same processor; dashboard now uses process, not the staging-only route its old copy misrepresented. `POST /api/posts/stage` and CLI `posts-import` remain staging-only compatibility actions. CLI `feed-import` now uses the same auto-add/process/profile resolution as HTTP feed-import. Rights attestation and dry-run contracts are preserved. The remaining local workflow features already share module-level services; no duplicate implementation was introduced.

## Verification / adding features

- `tests/test_evaluation_parity.py`: real CLI handler and real HTTP server, deterministic actual SmartRouter boundary + actual Evaluator JSON validation/weighting, unfamiliar title, missing candidate facts/JD, exclusions, local, AI, failure/fallback, persistence, stale inputs, lock/running/interrupted receipts, queue projection, actual legacy runner policy.
- `tests/test_pagination_receipts.py`: explicit next/end/total, valid stored cursor, missing metadata, page/result limits, interrupted/failed next requests, committed checkpoint preservation, mixed batch failure and injected legacy booleans.
- `tests/test_processing_interface_parity.py`: separate equivalent databases, real command and HTTP-worker paths for source scan, feed and post processing.
- Existing regression suite, original scanners/gates/persistence/exports/profile/schema tests remain; only the exact build-label assertion changes to reflect this release. Added returned-failure/partial-scan regression tests to legacy export integration.
- Controlled local Chromium check: UI local result, no-consent pending, deterministic AI model/scale/dimensions, page-limit unknown continuation, no JS errors, CSP unchanged. Not live AI proof.

Add business rules to services, not HTTP handlers, argument handlers or JavaScript. Add new source pagination receipts only when evidence exists; extend controlled fixtures for unknown/error paths first. For new evaluation methodologies add a distinct method/scale/version and tests—never silently reinterpret stored scores.

## Explicit remaining limits / nonclaims

Real AI account selection/quotas/paid access and every live provider are not qualified by fixture tests. User private Codespace restart and installed dependency environment remain a separate deployment check. Legacy YAML/CV and Markdown/JSON queues are explicit compatibility adapters, not automatically merged SQLite profiles/history; different candidate inputs legitimately differ. Legacy JD fetch/notification/document delivery is not automatically triggered by the per-job dashboard evaluation endpoint. The dashboard is not an AI batch/delivery control panel, and the finite search button does not expose every advanced CLI search override. These are intentional boundaries, not claims of exhaustive UI-option or operational parity. Unknown-source autonomy and provider availability require their own real retrieval evidence.

## Source-response recovery follow-up

Build `source-recovery-1` adds backend-owned response outcomes, snapshot receipt
scope and source/provider wait reasons. See [SOURCE_RECOVERY.md](SOURCE_RECOVERY.md)
for ownership, tests, backoff behavior and remaining external provider limitations.
Do not interpret zero canonical inserts as an empty or failed response; use the
backend outcome and raw/valid/existing/filtered counts. No UI control overrides a
publisher gate, and a snapshot completion is not proof of whole-site coverage.
