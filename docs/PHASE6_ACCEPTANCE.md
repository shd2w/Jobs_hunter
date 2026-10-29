# Integrated preparation and learning acceptance

Phase 6h adds a repeatable acceptance checkpoint around the existing preparation, exact evidence mapping, contextual guidance and private practice workflows. It does not add an AI model, change matching, rewrite CVs, submit applications or claim independent verification of candidate facts.

## Reproduce

Use Python 3.13 and a disposable checkout. No personal profile or live credentials are needed.

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q tests/test_phase6_acceptance.py
python qa/phase6h_smoke.py .
python -m pytest -q
```

The HTTP smoke test seeds three synthetic vacancies (positive, mixed-context and explicitly excluded), an empty practice tracker, two user-attested facts, one unverified claim and opaque synthetic PDF bytes. It performs real loopback HTTP operations against a temporary workspace. Provider retrieval and message delivery functions are replaced with failures; non-loopback socket connections are rejected. The fixture PDF tests byte preservation, not PDF visual validity or rendering.

## Acceptance boundaries

- Explicit fact/excerpt/rationale mapping creates a new pending pack. Unverified claims cannot be selected; private rationale is preserved as metadata, not added to cover prose.
- Human review is recorded for that exact version. Saving/completing a practice never modifies the reviewed pack, candidate facts, matching, application status/history or original CV.
- Contextual guidance excludes configured employers; negated-only cues do not offer practice. Completing SQL practice does not turn an unverified SQL claim into a verified candidate fact.
- Completion requires explicit self-attestation. Duplicate saves preserve progress; stale revisions cannot overwrite newer notes.
- Source edits, fact revocation, listing changes and skill changes block old pack reviews. Saved practice snapshots and historical review entries remain available. A fresh valid pack starts pending rather than inheriting review.
- A mapping preview binds identity, authorized facts and target text, not unrelated matching preferences. A skills-only edit can preserve the mapping fingerprint while still making the old pack context obsolete. Those are different contracts.
- Private practice notes and evidence connections are absent from calendar export, aggregate JSON/CSV, counts-only digest preview, learning guidance and ordinary job export. Ordinary job exports intentionally include application notes and must still be treated as private.
- Database backup/reopen restores practice data. Pack directories and review history need a separate filesystem backup; a database alone cannot recover missing packs. Later changes to the working copy do not mutate the backup.
- Profile namespaces and a reopened workspace preserve those boundaries. No preparation or learning action submits an application.

The repeatable smoke prints assertion-backed counts and a summary; it writes no supplied personal data. Synthetic test results are not live provider, publisher, model, notification or hiring-outcome evidence.

## Browser acceptance

Optional development-only dependencies: Python Playwright and a local Chromium executable. Install Playwright only in a development environment if needed; it is not required by the application or its ordinary CI regression suite. Supply your executable path:

```sh
python -m pip install playwright
python qa/phase6h_browser.py --output /PRIVATE/qa-results --chromium /path/to/chromium
```

The browser runner creates its own temporary loopback workspace, uses no live accounts, closes the browser/server, and deletes the fixture workspace afterward. It captures desktop explicit mapping/review, mobile completed practice, dark mobile practice, and a changed-source blocked pack. It asserts no browser errors, external browser requests, horizontal page/dialog overflow or executed markup. Screenshot output is private and must not be committed. Inspect the captured images as well as the machine assertions; screenshot creation alone is not visual review.

## Scope still open

This checkpoint validates synthetic integrated behavior, not the entire original specification or every deployment environment. Remote Codespaces startup/proxy/persistence, Windows execution, representative performance and changing live provider access remain unverified. Optional AI/real-model validation remains deferred, not passed, and is not required for this local deterministic checkpoint. Starting a potentially billable Codespace still requires the owner's explicit choice.

## Recorded local result for this checkpoint

- Full regression: **1,650 passed**, including six new integrated acceptance cases.
- Standalone smoke: **47 real loopback HTTP operations**, three synthetic jobs, two included learning vacancies, one reviewed version, and six checked export/preview boundaries; no real external requests.
- Browser: **five states** at desktop 1440px and mobile 390px, light/dark themes, no page errors, external browser requests or measured horizontal page/dialog overflow. Each captured state was also visually inspected locally.
- Original synthetic CV bytes, saved private practices, blocked historical reviews, profile isolation and separate database/pack recovery assertions passed.

These are local Linux/Python 3.13/Chromium observations. They do not imply a remote Codespaces or Windows test. GitHub CI reruns the regression and smoke on publication; the browser runner is a separate optional development check.
