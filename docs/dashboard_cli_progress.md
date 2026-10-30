# CLI/dashboard repair progress

Baseline: eaf0907. Release build: dashboard-cli-consistency-1.

## Completed implementation stages

- [x] Inspect clean working tree and repository/release instructions; preserve unrelated files.
- [x] Trace CLI, HTTP, automatic worker, legacy evaluator, storage, scanner families and UI; save discrepancy matrix **before** application edits.
- [x] Shared evaluation service, validated options/context, legacy scoring/German-policy core, explicit local/AI/fallback/pending/failure status and versioned backed-up SQLite receipts.
- [x] HTTP and real CLI adapters, actual method/model/scale in opportunity dialog, consent gate, input staleness and interrupted/persistence/lock behavior.
- [x] Source-specific pagination receipts, unknown/explicit-next/end/limits, valid cursor resume and preserved checkpoints on failure/cancellation; truthful backend messages in all three source-result displays.
- [x] Shared batch outcomes and manual task timestamps/status; no successful aggregate after returned legacy evaluation failures; partial scan preserved.
- [x] Correct post-processing and feed-import interface discrepancies while retaining explicit staging route/command.
- [x] Extend existing queue projection to current shared AI receipts; no lexical conversion, stale-score resurrection, document invention or destructive migration.
- [x] Save ownership/configuration/status/test/deployment documentation.

## Verification performed

- Before edits: **1,800 passed** with external Python networking guarded.
- Final application tree: **1,850 passed** with the same guard (62.32 seconds). No existing tests removed or weakened. Exact build-label assertion updated; legacy export tests extended.
- Focused evaluation/pagination/processing/legacy set: 55 passed before the final queue-projection test; final full suite includes that additional case.
- Queue/evaluation/history compatibility set: 96 passed.
- Integrated synthetic preparation/learning smoke passed, database and separate pack backup reopened, original synthetic CV hash preserved, **zero external requests**.
- Local Chromium fixture check passed: local evaluation, no-consent pending, actual deterministic AI model/dimensions/scale, page-budget message without asserted next page, no JavaScript errors, CSP preserved. Repeated against final code. This is not a live AI claim.
- Python compile, JavaScript syntax checks and git diff whitespace checks passed.

## Explicit open qualification / scope boundaries

- Real AI credentials/account/model/quotas and paid usage not authorized or exercised. Live AI is **not** a passing test.
- No claim that all remote sources are accessible; provider failures, Google Jobs upstream limitations, access permissions and installation requirements still apply.
- No direct access to the user's private Codespace runtime. Source publication does not pull/restart their server.
- Legacy YAML/CV + Markdown/JSON delivery is preserved as an explicit compatibility adapter, not silently migrated into SQLite profiles. Dashboard per-job evaluation does not trigger legacy JD-fetch/cover-letter/Telegram batch delivery. Different optional actions and different candidate inputs are not claimed identical.
- The finite dashboard profile-search action exposes common defaults, not every advanced CLI override. No exhaustive UI-control parity or operational autonomy claim.
- Manual HTTP task envelope remains in-memory; durable source/search/evaluation receipts are the recovery record. No new durable background AI job queue introduced.
- Live all-provider, Windows and representative performance qualification remain open. Controlled tests demonstrate shared behavior, not all-source coverage or unknown-site autonomy.

Publication and CI status are recorded in the associated pull request/release handoff, rather than fabricated before remote checks finish.
