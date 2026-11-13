# 00 — Project Charter

Status: **binding for scope and intent**. Companion documents: GOV-01 architecture contract, GOV-02 decision log and scope, GOV-03 security and credentials, GOV-04 work packages, GOV-05 validation matrix, GOV-06 execution plan, GOV-07 pilot and demo track.

> **Source note.** The authoritative source named for this suite, `revised_system_v2.md`, and the eight reference documents were not available. This suite is derived from the JobHunter design suite (`SRC`: primary document plus design documents 01–10, revision 4) and from the structure demanded by the task description (ASM-001, ASM-002). Every statement below is tagged by origin where it matters: **[SRC]** source requirement, **[DERIVED]** constraint derived from the source, **[REC]** recommendation, **[PCD]** unresolved, **[ASM]** assumption.

## 1. Project identity

| Item | Statement |
| ---- | --------- |
| Name | JobHunter [SRC] |
| Purpose | Find, normalise, evaluate and track job postings for a candidate, and prepare — only on request — job-specific application documents [SRC] |
| Problem | Relevant postings are spread across employer ATS boards, government portals, feeds and boards; they are duplicated, change or disappear, require different eligibility (work authorisation, location, sponsorship), and are described in free text. Existing scoring trusted a model's own total and silently discarded roles. [SRC design doc 01, 08, 09] |
| Target users | Any job seeker in any country; postings in English and German; any profession [SRC owner instruction; DEC-030, DEC-031, DEC-036] |
| Environments | Local single-user application (Windows-first, Python 3.12–3.14, CPU only, SQLite) now; hosted multi-user service later, staged (DEC-036, ASM-006, ASM-008) |
| Boundaries | JobHunter prepares and tracks; it never submits applications (DEC-035). It is not a recruiter tool, not an employer-side product, not a payment product (DEC-040). |

## 2. Goals

### Primary goals
1. **Broad, honest discovery:** reliable sources first (ATS, government, feeds, user imports); consumer boards optional and restricted (DEC-048).
2. **Canonical, deduplicated, lifecycle-aware jobs** with provenance (DEC-005, DEC-009, DEC-010).
3. **Explainable matching** per user with a separate eligibility verdict; failure is explicit, never fabricated (DEC-022, DEC-023, DEC-034).
4. **User-controlled documents:** CV and cover-letter drafts only on an explicit per-job action; originals immutable (DEC-019, DEC-020).
5. **Truthful candidate data:** every level carries provenance; nothing is auto-confirmed (DEC-021).
6. **Preserve what works:** existing CLI, exports, queue contract and tests stay (DEC-002, DEC-042).

### Secondary goals
Application tracking with history; notifications without personal data; feedback loop from the user's own decisions; skill-gap hints; monitoring and recoverability; one scheduler with a lease; a hosted multi-user mode (staged).

### Non-goals (DEC-040)
Recruiter discovery or outreach; automatic application submission; proxy rotation; paid scraping or anti-bot services; employer-side features; payments; scraping competitors' company lists; Arabic-language postings.

## 3. Product scope

| Scope | Content |
| ----- | ------- |
| **V1** (R1–R3, local mode; DEC-043) | everything in GOV-02 §4.1 |
| **Future** | hosted multi-user platform (R4, phases 13–16); German UI; local LLM provider; other notification channels; adaptive cadence; pilot-gated sources |
| **Excluded** | GOV-02 §4.4 (rejected) and §4.2 (not allowed without a decision update) |

## 4. Major capabilities

Source registry with states and policy gates (C-04); source adapters behind one contract (C-05); ingestion with quality rules and visibility (C-06); company catalog funnel (C-07); enrichment for EN/DE (C-08); versioned profile and CV intake (C-09); deterministic matching and optional validated evaluation (C-10); AI routing with explicit failure states (C-11); user-initiated documents (C-12); application tracking, notifications, feedback (C-13); store, migrations and compatibility exports (C-14); health and monitoring (C-15); hosted platform layer (C-16); imports (C-17). Detail: GOV-01.

## 5. Architectural philosophy

Each principle is supported by the source and enforced by a gate (GOV-05).

| Principle | Meaning | Enforced by |
| --------- | ------- | ----------- |
| Strangler, not rewrite | wrap existing code, move only when a package needs it | DEC-002, G1, G2 |
| One brain, two faces | CLI and UI share services; no logic in interfaces | DEC-003, G4, G15 |
| Source-of-truth discipline | one authority per entity; files are exports | DEC-004, INV-21 |
| Deterministic control | scores, eligibility, lifecycle and dedup are code, not model judgment | DEC-022, INV-03 |
| Fail closed | blocked source, failed AI, partial sync never look like success and never change state | DEC-010, DEC-034, INV-04, INV-10, INV-12 |
| Human in the loop | documents, confirmations, merges and enabling restricted sources need a user action | DEC-019, DEC-021, DEC-032 |
| Provenance and auditability | every job, level and document records where it came from | DEC-005, DEC-021 |
| No core dependence on restricted sources | the product works with consumer boards disabled | DEC-048 |
| Local-first, CPU-only, free-first core | no service beyond the app process in local mode | DEC-036 |
| Honest validation | mocked, simulated and designer-written results are labelled | DEC-047, G9 |

## 6. Success criteria

Verifiable outcomes (numeric quality targets are **[PCD-023, PCD-024]** and are set after a measured baseline; none is claimed now):

| # | Criterion | Proof |
| - | --------- | ----- |
| S1 | all pre-existing tests pass unchanged on Linux and Windows with zero skips | G1, G7 |
| S2 | the queue file is byte-identical to the golden file after migration | G6, G13 |
| S3 | no code path creates a document without an explicit per-job action | G5 |
| S4 | a real 60 percent volume drop re-baselines within 3 stable runs; a stable zero outage never does | G10 |
| S5 | a failed source, failed AI call or partial sync is never reported as success and never closes a job | G16, G10, G17 |
| S6 | CLI and UI return identical ranked ids and scores | G15 |
| S7 | every source claimed as working has a dated live record | G20 |
| S8 | no contact data, nationality or secret appears in tracked files, logs, AI payloads or notifications | G12 |
| S9 | R1 delivers usable discovery for one user (35 work packages, DEC-043) | phase exit conditions, GOV-06 §10 |

## 7. Constraints

| Kind | Constraint |
| ---- | ---------- |
| Technical | Python 3.12–3.14; stdlib server and vanilla JS (DEC-038); SQLite locally; pinned, hash-locked dependencies (DEC-013, DEC-041) |
| Operational | single maintainer assumed (ASM-005); live network access only from the owner's machine (ASM-007); one scheduler lease holder (INV-24) |
| Security | GOV-03; no bypass of source protections (DEC-033); no personal data to AI without consent (DEC-045) |
| Regulatory | data-protection obligations for hosted mode are **unresolved** (PCD-026); source terms and redistribution unresolved for several sources (PCD-014, PCD-029) |
| Integration | auto-applier hand-off file stays byte-identical (DEC-035); Telegram payloads carry no personal data (DEC-045) |
| Deployment | local first; hosted target unspecified (ASM-008, PCD-005, PCD-012, PCD-013) |

## 8. Governance

* **Authoritative documents:** GOV-02 (decisions and scope) > GOV-01 (architecture) > GOV-03 (security) > GOV-05 (validation) > GOV-04 (packages) > GOV-06 (procedure) > GOV-07 (pilots) > this charter for intent. Where two disagree the higher one wins and the lower is corrected in the same change.
* **Decision changes:** only through GOV-02 §9; the owner decides.
* **Implementation control:** one work package at a time per implementer on its own branch; a package is complete only when GOV-05 §10 says so; the report format in GOV-06 §7 is mandatory.
* **Scope changes:** new work needs a new or amended work package and, if it touches a decision, a DEC/PCD change first.
* **Relation to the design suite:** the design documents remain the explanatory source; this suite is the operating contract. In a conflict the suite wins until the owner updates the decision log.
