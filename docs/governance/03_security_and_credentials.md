# 03 — Security and Credentials

Status: **binding**. Derived from the source's own security-relevant requirements (DEC-019, DEC-033, DEC-034, DEC-039, DEC-045, DEC-046) and the design suite's security chapter (SRC design doc 06 §5). Where the source is silent the item is a pending decision (PCD), not an invented policy.

## 1. Security principles

Least privilege; fail closed (a blocked source, failed AI call or partial sync changes nothing and says so); deterministic authorisation and state changes; data minimisation toward external services; no bypass of third-party protections (DEC-033); auditability of user actions; secure defaults (everything restricted is off until acknowledged).

## 2. Data classification

| Class | Examples | Storage | Logs | Cache | External services | AI |
| ----- | -------- | ------- | ---- | ----- | ----------------- | -- |
| **S0 Public job data** | job text, company, location, salary as stated | database; raw payload 30 days | counts only, no text | allowed | n/a (it comes from there) | allowed |
| **S1 Operational data** | run records, metrics, breaker state, key states by alias | database | allowed | allowed | no | no |
| **S2 User activity** | applications, events, feedback, saved searches, notes | database, per user | ids only | allowed per user | Telegram: title, company, score, link only | no |
| **S3 Personal profile and documents** | profile versions, skills and levels, experience, education, preferences, CV originals, drafts, imports | database and read-only files by hash, per user | never content | per user only | only the minimised subset the AI task needs and only under consent | consent-gated, contact data excluded |
| **S4 Restricted** | contact details, nationalities, work-authorisation details, credentials and API keys | contact and nationality in the profile only; credentials in `.env` or a managed secret store, never in the database | **never** | never | **never** (credentials only as request headers to their own provider) | **never** |

Handling rules: S3 and S4 never enter fixtures, test data, error messages or analytics (G12). A new data field must be classified when it is added (reviewer checklist, GOV-05 §9).

## 3. Identity and access control

| Mode | Identity | Rules |
| ---- | -------- | ----- |
| Local | one owner, no accounts | the server binds 127.0.0.1 only; per-session CSRF token on every mutation; no remote access feature |
| Hosted (staged, blocked by PCD-012, PCD-022, PCD-026) | `user` (own rows only); `operator` (access to user data **undefined, none assumed**: PCD-022); service identities `scheduler`, `worker`, `notifier` with no access to S3/S4 beyond what their task needs | every per-user repository method takes a user context (INV-23); isolation tests enumerate all methods (G18) |

Privileged operations (each writes an audit event; each needs an explicit user action): enable a restricted source or set `authorized`; confirm a skill or language level; request a document; export documents; export the queue file; change AI keys or consent; restore a backup; delete all data.

## 4. Credential rules

| Topic | Rule |
| ----- | ---- |
| Storage | `.env` file (local) or a managed secret store (hosted, technology open: PCD-013); never in the repository, database, fixtures, logs, notifications or screenshots |
| Handling | keys referenced by alias everywhere; write-only fields in the UI; never returned by an API; shown only as present or missing |
| Scope | AI provider keys, messaging bot token and chat id are the credentials named in the source; none others are introduced without a decision |
| Rotation | owner-initiated; per-key cooldown state is stored by alias without the key; multi-key quota rotation is kept configurable and logged pending PCD-010 |
| CI | secret and PII scan on every change (G12); a failing scan blocks merge |
| Contact data | real contact details live in an untracked profile file; a tracked example file replaces it (WP-00-02) |
| Logging | no secrets, no tokens, no full URLs containing tokens, no personal data (G12) |

## 5. Sensitive-data boundaries

| Data | May exist | May not exist | Logged | Cached | Sent externally | Enter AI |
| ---- | --------- | ------------- | ------ | ------ | --------------- | -------- |
| Contact data | profile table, untracked config | fixtures, logs, tracked files, notifications, AI inputs | no | no | no | no |
| Nationality, work authorisation | profile tables | AI inputs, notifications | no | per user | no | no (verdict is computed locally) |
| CV text | read-only original, extraction drafts, generated drafts | logs, notifications, tracked files | no | per user | only to the configured AI provider under consent | consent-gated, minus contact data |
| Job text | database | none | no | yes | no | yes |
| Recruiter e-mail addresses in postings | nowhere | database, logs | no | no | no | no |
| API keys | `.env` or secret store | everything else | never | never | provider header only | never |
| Application notes and feedback | per-user rows | logs, notifications | ids only | per user | no | no |

## 6. External integrations

| Integration | Security requirement |
| ----------- | -------------------- |
| ATS and feed endpoints | https only; host allow-list; no redirects; size and time caps; no credentials; classify 401/403/429 as blocked (breaker); attribution kept (DEC-033, INV-12) |
| Aggregator boards via the pinned library | restricted tier; off by default; owner acknowledgement per provider; no proxies; recruiter e-mails dropped (DEC-006, DEC-012, DEC-017) |
| Government portals | terms and permitted use are pending (PCD-029); local personal use only until reviewed |
| AI providers | minimised payload; consent; schema-validated output; no tools; keys by alias (GOV-01 §7) |
| Messaging (Telegram) | token in `.env`; messages contain title, company, score and link only |
| Auto-applier hand-off | file only; contract byte-identical; no network call (DEC-035) |
| Inbound e-mail (hosted, staged) | per-user address; HTML sanitised; attachments ignored; links not followed (DEC-026) |
| Libraries | pinned and hash-locked; contract tests on upgrade; vendoring option; blocked packages listed (DEC-041, DEC-015) |
| Plugins, external agents, MCP-style tools | **none in scope**; any proposal is a new PCD |

## 7. AI security

* **Prompt injection:** job and CV text are delimited data; instructions inside them are ignored by rule and, more importantly, cannot act because models have no tools and scores and states come from deterministic code (INV-03).
* **Hallucination boundaries:** every extracted requirement needs a verbatim quote found in the input; documents may not change protected facts (dates, employers, education, language levels); a facts-check list is shown at review.
* **Data exfiltration:** no personal data in prompts beyond the minimised subset; no URLs fetched on the model's instruction.
* **Untrusted retrieved content:** all job text is untrusted (B7).
* **Output validation:** schema, quote check, one repair attempt, else `failed` (INV-04).
* **Sensitive-data exposure:** contact data and nationality excluded by construction in the input builder (INV-08); a payload-capture test proves it.

## 8. Source-compliance security

No CAPTCHA, login or paywall handling; no stealth or TLS-impersonation adapters; no retry through a block; no proxy; redirect and tracking links never followed; robots.txt honoured for non-API pages; per-domain request budgets; crawler identifies itself honestly (DEC-033). Provider terms are recorded per source with a review date; sources without a review are local-personal-use only (PCD-014, PCD-029).

## 9. Supply chain

Hash-locked dependency files installed by group; exact pins for `ats-scrapers` and `python-jobspy`; contract tests on every upgrade (G11); monthly upgrade review, never automatic; block-list test (G3); `pip-audit` in CI where available; vendored copies only under an explicit decision (DEC-041); no package with stealth or anti-detect purpose.

## 10. Dependency and approval rules

Approved set: DEC-013 packages. Interim default (PCD-018): `tldextract` in offline mode. After PCD-009 is answered: `pypdf` and `python-docx`. Anything else needs a new DEC.

## 11. Failure behaviour (fail closed)

| Failure | Required behaviour |
| ------- | ------------------ |
| Source returns 401, 403 or 429 | breaker opens, source `blocked`, no retry through another route, shown to the user |
| Source returns less than half its median or zero | run `partial`, nothing closes, recovery rule INV-11 |
| More than half of sources fail in a cycle | no lifecycle change in that cycle; health alert |
| AI call fails or output invalid | `failed` state, no score, matching continues without AI |
| Upload fails validation | rejected with a specific reason; nothing stored |
| Migration verification fails | no authority flag changes; backup untouched; rollback documented |
| Policy test fails | merge blocked |

## 12. Security gates

| Stage | Must be proven |
| ----- | -------------- |
| **Merge** | G1, G3, G12 for every package; the package's own gates from GOV-04; reviewer checklist signed by someone other than the implementer (G21 for packages of type Security or AI) |
| **Release to a user (local)** | G6, G7, G13, G20 for every source claimed; no blocking PCD open for the released scope |
| **Hosted staging and production** | G18, G19, G21; PCD-005, PCD-012, PCD-013, PCD-022, PCD-026 answered; restore from encrypted backup verified |
