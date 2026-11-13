# 10 — Methodology Feasibility Review

Date: 2026-11-02 · Reviews [09](09_REVIEW_AND_METHODOLOGY_SPECIFICATION.md) Part B. Where this document and doc 09 differ, **this document wins** and doc 09 has been patched (§7).
Design and documentation only; the three experiment scripts live in `docs/feasibility/` and are not part of the product.
Evidence labels as in doc 09: **[verified]** inspected or executed here · **[simulated]** synthetic model, tests the *rule*, not real boards · **[reasoned]** argued, not testable from my sandbox · **[unverified]** no route to the source · **[arithmetic]** · **[target]**.

## 1. Question and method
*Can each methodology in doc 09 actually be built and operated by one maintainer with free-first tooling, and does it behave sensibly?* I (1) executed what could run offline, (2) simulated the rules that carry the most risk, (3) checked the libraries and data the methods depend on, and (4) argued the rest and said so.

## 2. Experiments executed

| # | What | Result | Caveat |
|---|---|---|---|
| E1 `exp1_resolver.py` | `ats_scrapers.resolve.resolve_careers_url` on 34 hand-written URLs (24 positives across 15+ ATS families incl. EU Greenhouse, Workday; 10 negatives: Indeed, LinkedIn, `lnkd.in`, Glassdoor, tracker, employer site, `gh_jid` on a custom domain, junk) | **34/34 as expected** [verified] | URLs are my own shapes, not real tenants: shows the *recognition logic*, not real-world yield |
| E2 `exp2_enrichment.py` | prototype of B10 rules: language scoring, years regexes (EN/DE incl. spelled-out numbers, ranges, "über", "mehrjährig"), evidence-weighted seniority | first run **29/31**; the two misses were flaws in my own rules (see F3); after revision **35/36** (remaining miss is an over-strict test expectation for a bilingual snippet, harmless) | 36 designer-written cases: shows the rules are **implementable**, says nothing about **accuracy** on real postings |
| E3 `exp3_guard_sim.py` | simulation of the closure guard and drift detector on synthetic boards (Poisson hiring, exponential lifetimes, 3-hour scans, 200 seeds per cell) | two serious flaws found (F1, F2); fixes validated [simulated] | synthetic boards; outage-to-zero case not modelled (specified as a test in F1) |
| E4 | PyPI release history: `ats-scrapers`, `python-jobspy`, `tldextract`, `publicsuffix2`, `w3lib` | `ats-scrapers`: **3 releases, first 2026-07-22, latest 0.3.0 on 2026-09-02, one author**; `python-jobspy`: 86 releases but **four minor versions in 21 days** (1.2.0 on 2026-10-02 → 1.4.1 on 2026-10-23); `tldextract` maintained (5.4.0, 2026-10-03, BSD-3) [verified] | release counts are a maturity signal, not a quality verdict |
| E5 | JobSpy 1.4.1 output schema | `JobPost` has **34** output columns, including `skills`, `experience_range`, `job_level`, `emails` [verified] — the Decision Log's "34-column" claim is confirmed | — |

Rerun: `pip install ats-scrapers==0.3.0 beautifulsoup4 html2text && python docs/feasibility/exp1_resolver.py`; `python docs/feasibility/exp2_enrichment.py`; `python docs/feasibility/exp3_guard_sim.py` (E2/E3 need only the standard library).

## 3. Findings

| ID | Finding | Evidence | Sev. | Fix (applied to doc 09) |
|---|---|---|---|---|
| **F1** | **The closure guard locks a source permanently after a real volume drop.** The baseline is "median of the last 7 *complete* runs"; a guarded run is not complete, so after a genuine 60 % drop every later run is still compared with the old median and flagged forever. Jobs that really closed stay open. | [simulated] 60 % hiring freeze at day 30. Board ~200 jobs: **214 of 240 post-freeze runs flagged, 155 stale-open jobs** at day 60. Board ~20: 97 runs flagged, 5.2 stale. | **Critical** | **Re-baseline rule (v2):** after *k* consecutive flagged runs with a stable count (max/min ≤ 1.15) accept the new level. Simulated result: flagged runs **7.9** and stale-open **2.0** (200-job board); 3.6 / 0.05 (~5-job board). **Safety clause:** a drop of more than 80 % (including zero) needs **k = 8 runs spanning ≥ 24 h**, a passing `health_check`, and must not coincide with the global cycle breaker — otherwise a stable *outage* would be re-baselined to zero and close everything. The zero-outage case is **not** in the simulation and must be a fixture (P4). |
| **F2** | **Per-board drift detection is unusable for small boards.** A plain robust-z (MAD only) divides by zero on stable small counts. | [simulated] ~6-job boards: **16.9 % of days raise a false alarm**. With a floor `max(MAD, 5 %·median, 1)`: 0.32 % false alarms but only **7 %** detection of a 50 % drop within 5 days. By board size (floored): ~20 jobs: 2.7 % false alarms, **80 %** detection of a 50 % drop, 51 % of a 30 % drop; ~55: 0.6 % / **97 %** / 73 %; ~200: 0 % / 100 % / 96 %. | High | Per-board detector only when `median ≥ 20`. Small boards rely on the volume guard and error rates. **Cohort detector** (sum of counts per ATS provider and tier) catches adapter or schema breakage, the dominant failure mode — its power is **untested** (standard technique, needs its own simulation in P12). |
| **F3** | **The seniority rule had three defects.** (a) `years ≥ 10 → lead_exec` conflates a very experienced individual contributor with an executive. (b) Title-only evidence (weight 0.15) falls under the 0.30 threshold, so "Senior Backend Engineer (m/w/d)" with no other signal becomes `unknown` and a real signal is discarded. (c) "at least 18 years old" was read as 18 years of experience. | [verified in prototype] (a) the Ericsson-style case produced `lead_exec`; (b) title-only case returned `unknown`; (c) returned 18 | High | (a) years alone never give `lead_exec`; it needs an executive title (`Director, Head of, VP, Chief, Geschäftsführer, Bereichs-/Abteilungsleiter`) **or** a scope cue **and** ≥ 8 years. (b) Emit `seniority_hint` with `evidence=title_only`, low confidence, never used to hide jobs. (c) Ignore sentences matching age statements (`years old`, `years of age`, `Jahre alt`). Company-history sentences ("we have 25 years of experience") are skipped by the sentence-level `we/our/wir/unser` rule when no candidate cue is present; this depends on sectioning quality, which is unmeasured. |
| **F4** | **Language detection separates EN/DE from other languages on my samples, but the policy for `unknown` was missing.** French, Spanish, Dutch and Italian snippets scored below threshold and were classed `unknown` (not `other`, because under 200 tokens), so they would not leak into `en/de`. Titles alone are also `unknown`. | [verified in prototype] 4 non-EN/DE snippets → `unknown`; Dutch scored closest (en 0.062, de 0.031) | Medium | **Policy:** `unknown` with ≥ 40 tokens → hidden as `other`; fewer than 40 tokens → use the provider's `language` field (the `Job` model has one) or the source's country; else visible with a `language_unknown` flag. Dutch, Danish, Swedish and Polish go into the labelled set because they are the nearest confusions. The `bilingual` flag is advisory only: both `en` and `de` are kept, so en↔de confusion does not affect collection. |
| **F5** | **The ATS backbone is a very young single-author library.** D2 makes `ats-scrapers` the base for dozens of adapters; it has existed for ~14 weeks, has 3 releases and `0.x` versioning, and none of its adapters has been run live by this project. | [verified] release history; adapters not exercised live | **High** | (1) Adopt now only the low-risk, pure-function parts (the resolver; E1). (2) **Do not retire `scanners/ats.py`** (Greenhouse, Lever, Ashby parsers, 24 mocked tests) until the library's adapters have passed live verification and run clean for ≥ 4 weeks; this reverses the "retire after parity" line in doc 02/03. (3) Pin the exact version with hashes; copy the used modules into `third_party/` (MIT permits) if upstream goes quiet; contract tests with recorded fixtures per adapter (OT-19). |
| **F6** | **JobSpy is changing fast.** Four minor versions in 21 days; our scanner was written against `1.1.x`; the schema is now 34 columns. | [verified] release dates, columns | Medium | Pin an exact version with hash; contract test on `JobPost.model_fields` and on `attrs["errors"]`; monthly upgrade review; never auto-upgrade. |
| **F7** | **Certificate Transparency enumeration (C7) is probably infeasible for the providers that matter.** Multi-tenant ATS providers typically serve all customer subdomains under a **wildcard certificate**, so CT logs would show `*.provider.com`, not individual tenants. | [reasoned]; not testable from my sandbox | Medium | Demote CT to *rejected pending proof*. Keep **Common Crawl** as a candidate and validate any discovery channel against ground truth: **the 1,804-row CC0 directory is a known-answer set** — a channel's *recall* on directory slugs and *precision* of recognised hits are measured before the channel is trusted (added to B13). |
| **F8** | **Domain-based company merging needs the Public Suffix List**, which the standard library does not have (`co.uk`, `com.eg`, …), and it is not in the Decision Log's dependency set. | [verified] `tldextract` 5.4.0, BSD-3, maintained; `publicsuffix2` last released 2019 | Medium | Add `tldextract` in **offline mode** (bundled snapshot, no runtime fetch) — OT-18. Alternative: ship a dated PSL snapshot file. |
| **F9** | **Agency heuristics are unvalidated.** Tokens such as `Talent`, `Search`, `Personal` occur in ordinary employer names. | [reasoned] | Medium | Advisory flag only, never an exclusion; measure precision on ≥ 100 labelled German company names before it influences duplicate grouping. |
| **F10** | **ESCO recall on real job-ad phrases is unproven.** ESCO labels are formal and occupational; ads name tools and frameworks. The download is a form-gated data file with terms to be checked (OT-14). | [unverified] | Medium | Report `mapped share` on the labelled set; if below the target set after the first baseline, add a corpus-mined gazetteer. Skill-coverage scoring compares **normalised strings plus ESCO synonyms**, so an unmapped skill still counts; ESCO only improves matching. |
| **F11** | **Capacity arithmetic holds; first-sync bursts do not.** 17,000 list requests/day is trivial, but detail fan-out on first sync is not: a 2,000-job Workday tenant at 1.5 req/s needs ~22 minutes; 100 such tenants ~37 hours. | [arithmetic] 2,000 ÷ 1.5 ≈ 1,333 s | Medium | **Onboarding throttle:** cap new boards per day (default 20) and per-tenant first-sync budget; incremental sync afterwards. |
| **F12** | **The only *verified* catalogue size is 1,804.** Channels C2, C4, C6, C7 have unknown yield; C3 gives names only. The plan was honest about not claiming yield, but it did not state the floor. | [verified] directory counts | Medium | State the floor: catalogue = directory + watch-list + imports; everything else is upside to be measured (B13). |
| **F13** | **Careers-page probe recall is unknown.** Static HTML misses widgets injected by tag managers or single-page apps. | [reasoned] | Medium | Pilot on 100 employer domains on the owner's machine; keep the probe opportunistic (not a pillar) if recall is below the target set after the pilot. |
| **F14** | **Labelling effort is real.** Language (≥ 200), enrichment (≥ 100), company names (≥ 100), domains (≥ 100) ≈ 500 items. | [arithmetic] at ~2–3 min per item ≈ 15–25 h | Medium | Stage it: start with ~60 / 40 / 50 / 50 marked *directional only*; AI pre-labels, a human reviews only disagreements; grow with use. |
| **F15** | **Total effort is large for one maintainer.** Using the S/M/L sizes of doc 07 (1/2/3 sessions): core P0–P12 ≈ 30 sessions (more with per-source work in P11); platform P13–P16 ≈ 10. | [arithmetic] | High | Define a **Minimum Viable Methodology** (§5) and ship it first; everything else has kill criteria. |

**Positive findings [verified]:** resolver 34/34; JobSpy schema as claimed; directory data and licence as claimed; Windows wheels for the compiled dependencies; both guard and detector are implementable in a few dozen lines.

## 4. Feasibility verdict per methodology

| Section | Verdict | Condition / residual risk |
|---|---|---|
| B1 C1 directory | **Feasible** | startup-heavy; no Workday/Personio/Workable/SmartRecruiters |
| B1 C2 hosted manifest | Unproven | opt-in only; content and terms unverified |
| B1 C3 government names | Feasible as *sources*; **not** a link channel | name → domain resolution unsolved |
| B1 C4 aggregator envelope | Feasible (local mode), yield unknown | LinkedIn yields none; Indeed links may be redirects |
| B1 C5 user inputs | **Feasible** | low volume, high precision |
| B1 C6 careers probe | Unproven | recall pilot first (F13) |
| B1 C7 passive datasets | CT: **likely infeasible**; Common Crawl: unproven | measure recall against the directory (F7) |
| B2 recognition | **Feasible** | reuse resolver; yield is data-dependent |
| B3 verification | **Feasible** | needs a `health_check` we own (one request) |
| B4 entity resolution | Feasible with a dependency | OT-18; agency flag advisory |
| B5 value, tiers, budgets | Feasible | weights unproven; onboarding throttle added |
| B6 closure and guards | **Feasible only with the v2 fix** | zero-outage fixture mandatory |
| B7 hashes, conditional requests | Feasible | savings unknown, measured |
| B8 connectors | Feasible but **dependency-risky** | keep own parsers as fallback; live verification per connector |
| B9 JSON-LD recipe | Unproven | defer until after pilots |
| B10 enrichment | Feasible with the F3/F4 changes | accuracy unmeasured; ESCO recall unproven |
| B11 adaptive cadence | Feasible | needs change-rate history; defer |
| B12 drift monitoring | Feasible for boards ≥ 20 jobs; cohort level unproven for the rest | F2 |
| B13 funnel evaluation | **Feasible** | add recall check against the directory |
| B14 governance | Feasible | policy, not engineering |
| B15 tests | Feasible | converts E1–E3 into permanent tests |

## 5. Minimum Viable Methodology (what ships first)

**Release R1 (usable discovery for one user):** P0 foundations incl. dated live probe; P1 defect fixes; P2 scheduler with lease; **P3 database and migration (prerequisite for the registry and run tables)**; P4 registry with budgets, **guard v2**, cycle breaker and run metrics; P5a envelope; P5b directory and imports; **P5c-lite** = normalise → resolver → policy gate → verification → static tiers A/B/C (no adaptive cadence); P6 lifecycle with guard; **P8-lite** = language policy, years/seniority (F3 rules), eligibility cues, salary text, open-vocabulary skills (ESCO matching only if the data file is available). Estimated ≈ 16 sessions (doc 07 §7–§8).
**Deferred until measured:** careers-page probe, JSON-LD recipe, adaptive cadence, passive datasets, per-board drift (cohort counts only), agency typing, full ESCO ladder.
**Kill criteria** (each deferred item is dropped if its pilot misses the target set after the first baseline): probe recall < target → opportunistic only; Common Crawl recall on directory slugs < target → drop; ESCO mapped share < target → gazetteer instead; adaptive cadence saves < 20 % of requests [target] → keep fixed tiers.

## 6. What I could not test
Live behaviour of any provider or adapter; real recognition yield of aggregator links; Common Crawl or CT data; careers-page recall; ESCO coverage and terms; accuracy of any rule on real postings; the cohort drift detector; guard behaviour for a stable zero-result outage; anything on Windows.

## 7. Amendments applied
Doc 09: B1 (C7 row, A18), B4 (PSL, agency flag), B5 (onboarding throttle), B6 (guard v2 with safety clause), B8 (library-risk rule), B10 (seniority table and rules, language policy, years edge cases, ESCO measurement), B12 (detector eligibility, cohort level), B13 (recall check against the directory). Doc 07: §7 (R1 scope, fallback rule, tests from E1–E3). Primary document: OT-17 updated, **OT-18** (PSL dependency), **OT-19** (young-library risk and vendoring), AD-22, audit row, risk.

## 8. Propagation (Revision 4)
Every finding above has been carried into the other documents: doc 01 §8 addendum and capability 3 treatment; doc 02 RC-11, OT-18/19 rows and D1/D2/D7 notes; doc 03 §14 and closure/observability text; doc 04 §11 schema (`company_candidate`, `source_scope_state`, `cohort_metric`, `domain_probe`, enrichment columns) and the §8 mapping row; doc 05 §8; doc 06 gates G10/G11, test rows, dependency register; doc 07 §6–§8; doc 08 §10; `docs/PROMPT.md` (working contract); docs index `docs/README.md`. Correction made during propagation: the Minimum Viable Methodology in §5 originally omitted P3, which the registry and run tables depend on.

