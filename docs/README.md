# JobHunter documentation index

**Start here:** [FINAL_SYSTEM_STRATEGY_AND_DESIGN.md](FINAL_SYSTEM_STRATEGY_AND_DESIGN.md) (consolidated strategy, decisions, open decisions, audit, executive report).

## Reading order
| # | Document | Use it for |
|---|---|---|
| 1 | [FINAL_SYSTEM_STRATEGY_AND_DESIGN](FINAL_SYSTEM_STRATEGY_AND_DESIGN.md) | what the product is, key decisions AD-1…AD-23, open decisions OT-0…OT-19, validation audit |
| 2 | [01 Existing system assessment](01_EXISTING_SYSTEM_ASSESSMENT.md) | evidence, defects DEF-01…DEF-15, capability matrix (point-in-time + §8 addendum) |
| 3 | [02 Decision traceability](02_DECISION_TO_ARCHITECTURE_TRACEABILITY.md) | Decision Log D1–D10 → architecture; conflicts RC-1…RC-11 |
| 4 | [03 Target architecture](03_TARGET_ARCHITECTURE.md) | layers, services, diagrams, CLI/UI parity, guard states (§14) |
| 5 | [04 Data and integration](04_DATA_AND_INTEGRATION_DESIGN.md) | schema (§4, §10, §11), adapter contract, lifecycle, migration |
| 6 | [05 UX and workflows](05_USER_EXPERIENCE_AND_WORKFLOWS.md) | screens, onboarding, journeys, document workflow |
| 7 | [06 Quality, security, operations](06_QUALITY_SECURITY_AND_OPERATIONS.md) | tests, gates G1–G11, security/privacy, dependencies |
| 8 | [07 Implementation roadmap](07_IMPLEMENTATION_ROADMAP.md) | phases P0–P16, release plan R1–R4, acceptance criteria |
| 9 | [08 Revision 1](08_REVISION_1_PLATFORM_SCOPE_AND_REVIEW_RESPONSE.md) | platform scope, EN/DE only, instruction ledger, new designs |
| 10 | [09 Review and methodology](09_REVIEW_AND_METHODOLOGY_SPECIFICATION.md) | 18 review findings; methodology B1–B15 (discovery at scale etc.) |
| 11 | [10 Feasibility review](10_METHODOLOGY_FEASIBILITY_REVIEW.md) | experiments, 15 findings, feasibility verdicts, release R1 cut |
| — | [PROMPT.md](PROMPT.md) | working contract pasted at the start of every implementation session |
| — | [governance/](governance/00_project_charter.md) | **operating contract suite** (GOV-00…GOV-07): charter, architecture contract with invariants, decision log (DEC/PCD), security, 73 work packages, validation matrix, execution plan, pilot/demo track; generated from this design suite (rev 4) |
| — | [feasibility/](feasibility/) | reproducible experiment scripts (E1–E3) |

## Authority rule
Numbered revisions are cumulative: **a later document wins over an earlier one** (10 > 09 > 08 > 01–07). Superseded text has been patched in place; the table below lists the substantive supersessions. `PROMPT.md` carries the session rules and must agree with the roadmap (it was updated in Revision 4).

## Revision history
| Rev | Date | Change |
|---|---|---|
| 0 | 2026-11-01 | primary document and docs 01–07 (assessment, traceability, architecture, data, UX, quality, roadmap) |
| 1 | 2026-11-02 | doc 08: platform scope (any user/country, EN+DE, profession-agnostic), red-team response, comparison findings |
| 2 | 2026-11-02 | doc 09: adversarial review, methodology specification, discovery funnel |
| 3 | 2026-11-02 | doc 10: feasibility experiments; guard v2, detector limits, seniority fixes, library-risk rule, release R1 |
| 4 | 2026-11-03 | propagation of all findings into every document, `PROMPT.md`, this index; P3 added to R1; OT-18/OT-19 assumed accepted |

## Substantive supersessions (old → new)
| Old statement | New | Where |
|---|---|---|
| automatic CV creation as opt-in setting | no automatic creation; setting removed in P1 | `PROMPT.md` §3, 02 RC-1 |
| local-only, no multi-user | local mode plus staged hosted track P13–P16 | 08, 07 |
| Arabic postings | removed; EN/DE only | 08 |
| Stage 3 MinHash dedup, `datasketch` | deferred | 08 §4.12 |
| source promotion rules (3 runs, ±50 %) | `validating → active` on green fixtures + one canary | 04 §5.3 |
| build an ATS recognizer | reuse `resolve_careers_url` + policy gate | 09 B2 |
| harvest employer links from LinkedIn | LinkedIn exposes none; seven-channel funnel | 09 A1, B1 |
| retire `scanners/ats.py` after parity | kept as tested fallback until ≥ 4 weeks live verification | 10 F5 |
| guard: baseline from complete runs only | re-baselining (v2) | 10 F1, 09 B6 |
| anomaly detection per board | per board only at ≥ 20 jobs; cohort detector otherwise | 10 F2, 09 B12 |
| years ≥ 10 ⇒ `lead_exec`; title-only ⇒ `unknown` | executive title/scope rule; `seniority_hint` | 10 F3, 09 B10 |
| CT logs for tenant discovery | demoted (wildcard certificates); Common Crawl PoC | 10 F7, 09 B1 |
| R1 without P3 | P3 included | 10 §5, 07 §7 |

## Open owner decisions
Binding answers needed: OT-1, OT-2, OT-5, OT-6 and C-1…C-5 (doc 08 §2.3) before P1/P5; OT-12, OT-13, OT-14 before P13. OT-18 and OT-19 are **assumed accepted** (recommended defaults) until the owner says otherwise.
