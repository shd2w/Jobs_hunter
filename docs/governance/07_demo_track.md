# 07 — Pilot, Prototype and Demo Track

Status: **binding for anything that is not production work**. The source contains meaningful prototype and pilot work: three offline experiments (`docs/feasibility/`), a shadow state for sources, pilot-gated methods with kill criteria (WP-11-06 to WP-11-08), staged labelled sets marked directional, and stakeholder walkthroughs of the local application. This track keeps all of that from becoming production architecture by accident.

## 1. Purpose

1. Measure before committing: pilots decide whether a deferred method is built (PCD-025).
2. Demonstrate behaviour to the owner using synthetic data, without claiming it is verified (DEC-047).
3. Reproduce findings (guard lock-in, detector blindness, seniority defects) as regression material.

## 2. Classification (every non-production artefact carries exactly one label)

| Label | Meaning | May be called "verified"? |
| ----- | ------- | ------------------------- |
| **Fixture** | recorded or hand-written input with expected output | no (mocked) |
| **Simulation** | synthetic model of behaviour over time | no (tests a rule, not reality) |
| **Designer-written** | cases written by the designer | no (shows implementability, not accuracy) |
| **Prototype** | throw-away code that explores an idea | no |
| **Demo** | scripted walkthrough for the owner on synthetic data | no |
| **Pilot** | measurement on real sources or real data with a decision outcome and kill criterion | only if run live and dated (G20) |
| **Production** | merged work package passing its gates | yes, per GOV-05 |

## 3. Branch and environment rules

* Pilots and prototypes live on `pilot/<slug>` branches or under `docs/feasibility/`; they are never merged into a phase branch (GOV-06 §2).
* Demos run on synthetic profiles and fixture sources in a **separate data directory**; they never read the owner's real workspace, profile, CV or credentials.
* Pilots that need live access run only on the owner's machine (ASM-007), with the owner's explicit start, and write their records to the verification file.
* Demo and pilot code may import production modules; production code never imports from them.
* Output of any demo or pilot is labelled with the §2 label in its header and in any report.

## 4. Allowed shortcuts

Fixtures instead of live sources; seeded random data; a fake AI provider with canned outputs; synthetic CVs and profiles; single-process scheduling without a lease; hard-coded thresholds marked `[target]`; small labelled sets marked directional; skipping the UI polish; stubbing notifications.

## 5. Forbidden shortcuts (never weakened, even in a demo)

| Area | Rule |
| ---- | ---- |
| Real data | no real candidate data, contact details, CVs or nationalities in demos, fixtures or pilot reports (G12) |
| Credentials | no real keys, tokens or chat ids in any demo or pilot file |
| Source safety | no bypass of blocks, no proxy, no stealth, no following redirects, no robots.txt violation; breaker and budgets stay active (DEC-033, G17) |
| Production endpoints | pilots respect the per-domain budgets; no load testing of third-party sites |
| Authorisation and isolation | hosted-mode demos keep per-user isolation; no shared-account shortcuts (INV-23) |
| Documents | demos create documents only through the explicit per-job action (INV-05) |
| Destructive operations | no deletion, restore or migration against real data in a demo |
| Claims | no demo output described as "working", "verified" or "production" unless §2 allows it |

## 6. Demo and pilot candidates

| Demo / pilot | Goal | Guardrail | Related |
| ------------ | ---- | --------- | ------- |
| D-1 Discovery funnel on fixtures | show candidate → recognised → verified → tier with reasons | fixture URLs only; labelled mocked | WP-05-05, DEC-029 |
| D-2 Guard replay | show the real 60 percent drop and the stable zero outage with and without re-baselining | simulation label; synthetic boards | WP-04-04, G10 |
| D-3 Eligibility walk-through | show eligible, blocked and unknown_check on synthetic profiles and postings | synthetic nationality and authorisation data; no real person | WP-08-04, DEC-023 |
| D-4 Alert-mail import | show paste and .eml import with undo | synthetic e-mail; links not followed | WP-05-04, DEC-026 |
| D-5 Document journey with a fake AI | show draft, diff, facts check, approve, export | fake provider; synthetic CV; originals unchanged | WP-09-01, WP-09-02 |
| D-6 Honest source status | show blocked, partial and zero-result states with reasons | simulated 429 and outage | WP-04-05, DEC-034 |
| D-7 Matching explanation | show signals, confidence, unknown handling on a synthetic profile | designer-written label | WP-08-04 |
| P-1 Live source probe | record what works from the owner's network and which link fields are populated | owner starts it; no credentials; dated record | WP-00-04 |
| P-2 Careers-page probe pilot | measure recall on 100 employer domains | robots honoured; 5 requests per domain per 30 days | WP-11-06, PCD-025 |
| P-3 Common Crawl proof of concept | measure recall and precision against the directory snapshot | read-only public data; no enabling | WP-11-08, PCD-017 |
| P-4 Labelled evaluation | baseline accuracy of enrichment rules | sample sizes stated; directional until a baseline exists | WP-08-06, PCD-023 |
| P-5 Adaptive-cadence replay | test whether the formula saves requests | replay on recorded runs only | WP-12-02, PCD-025 |

## 7. Existing prototypes and their status

| Artefact | Label | Status |
| -------- | ----- | ------ |
| `docs/feasibility/exp1_resolver.py` (34 URL cases) | Designer-written fixture | becomes a permanent fixture table in WP-05-05 |
| `docs/feasibility/exp2_enrichment.py` (35 passing cases) | Designer-written prototype | becomes unit tests in WP-08-01/02; accuracy still unmeasured |
| `docs/feasibility/exp3_guard_sim.py` | Simulation | becomes the regression test in WP-04-04 (G10) |

## 8. Demo review questions

1. Does the demo use only synthetic or fixture data? Is that stated on screen or in the output?
2. Could any shortcut be copied into production by a developer who does not read this file? If yes, mark it with a `DEMO ONLY` comment and keep it out of production packages.
3. Does the demo weaken a boundary in GOV-01 §4 or an invariant in §3? (If so, it must not run.)
4. Is every result labelled with its §2 label, with no "verified" wording?
5. Does it depend on a pending decision (PCD)? Which default does it assume?
6. Would the owner be able to mistake the demo for a statement about real source behaviour?

## 9. Demo-to-product conversion

1. The owner decides a pilot's outcome against its kill criterion (PCD-025) and records it in GOV-02.
2. Useful code is **not** merged from the pilot branch. A new or existing work package (GOV-04) is assigned, written to the production standard (tests, gates, evidence).
3. Fixtures and simulations become permanent tests only after being re-labelled and wired into the gates they support (G8, G10).
4. Anything depending on real data is re-run live and dated (G20) before it is called verified.
5. A pilot that misses its kill criterion is closed with its report; the deferred item stays deferred (GOV-02 §4.3).
