# Evidence-bound cover drafts — Phase 6b

**Current contract: Phase 6g.** Explicit [evidence-to-job maps](EVIDENCE_MAPPING.md) are now available, and used by the dashboard. Old versions remain untouched; their prior validator reports may be blocked under the new contract until a new pack is created.
## Supported behavior

Prepare a local review pack through the dashboard, `python run_local.py pack JOB_ID --output PRIVATE_DIRECTORY`, or the loopback `/api/pack` endpoint. Cover drafts use the existing conservative English template and up to three distinct verified source-backed facts. Facts are copied as exact quotations, never paraphrased or expanded. Duplicate exact fact text uses its first eligible source record; an explicit map selects exact facts in its supplied order. Without a map, compatibility ranking uses recognized title/description skill overlap but never fills zero-overlap facts. No-cue facts need an explicit user mapping, not a machine verdict of irrelevance.

A successful pack/CLI/HTTP response now includes `validation_report`. The same report is stored under `cover.validation_report` in `preparation.json`, and the legacy writer includes it in its `.evidence.json` file. Existing response keys and `validate_cover(...) -> list[str]` are retained; `validate_cover_report(...)` exposes the detailed result. The new read-only `/api/cover-evidence` preview and optional `evidence_mapping` input provide explicit links; there is no free-form cover editor, external service, model or dependency.

## What the checks mean

Validator: **deterministic cover contract v3**. Supported rendering: **grounded local template v2** (neutral examples-for-review wording, not an asserted relevance claim).

- Candidate identity: nonblank single-line name, at most 300 characters.
- Application target: nonblank single-line role/employer, each at most 1,000 characters; exact expected opening paragraph. Mentioning the right tokens elsewhere does not pass.
- Selected evidence: one to three distinct exact texts from eligible profile records. `verified` must be the boolean `true`, with nonblank text/source. Text/source are limited to 2,000 characters each. Invalid entries cannot authorize claims; unverified entries are ignored.
- Evidence connection: exact current user-attested links and reasons, or clearly declared lexical-only compatibility cues. A passing check is bounded structural binding, never independent semantic relevance. Map reasons stay outside cover prose.
- Exact quotations: each selected fact appears with the template's quotation delimiters, without rewriting.
- Supported template: the entire content exactly matches the rendered contract, including signature. Appended claims, negated targets, altered closings, whitespace/newline edits and other free-form prose are rejected. This is conservative structural validation, not natural-language understanding.
- Word limit: no more than 350 whitespace-separated words. Shorten the user-supplied facts when needed; the application does not silently rewrite them.
- Target context: URL/description, when supplied, must be Unicode text. Input labels/evidence reject hidden control characters; fact/source text may retain ordinary linefeeds/tabs. Authorized quotes and other Unicode/markup are retained as literal text, not treated as executable content.

Reports include `valid`, `review_required`, check IDs/results/messages, an issue list and word count. Check messages describe the passed requirement or failure; `passed` and `issues` provide machine-readable results. Invalid reports have no successful `bindings` object.

## Evidence binding and changes

Successful reports include SHA-256 of exact UTF-8 content, the target snapshot (title, employer, URL, description), trimmed candidate name, selected exact evidence/source/boolean records, the declared connection/mapping snapshot, and a combined template/validator/input contract. Repeated identical inputs produce identical reports; changed evidence sources or job context change the binding even when draft text remains the same. The evidence records remain in the draft sidecar for review.

These hashes are **snapshots, not signatures or independent truth verification**. They do not prevent someone editing both the files and report. Revalidate against current inputs after changes; an old passing report does not authorize a changed draft. The compatibility validator returns an empty issue list only for the supported contract. Arbitrary edited/AI prose is not accepted merely because known facts and employer tokens are present.

## Required human review and boundaries

`verified: true` means the user checked the fact, not that JobHunter established truth. The validator does not assess semantic relevance, candidate qualifications, legal eligibility, job legitimacy or name ownership. Review the original vacancy, evidence and every draft. User-attested evidence can still be mistaken or inappropriate; a structural pass is not an approval to apply.

Original PDF CVs remain optional byte-for-byte copies with SHA-256 comparison, never rewritten/rendered. Failed validation produces no new pack; later pack-write/copy failure removes the new directory. No application, recruiter outreach, background task or model call occurs.

The legacy deterministic output path can still overwrite a prior draft on rerun (P6-PACK-001); preserve edits separately until the next pack-management slice fixes it. Core packs already use distinct directories. Evidence-to-job mapping, learning context/resources/exercises/progress, free-form prose, real PDF renderer/Windows/live integrations remain separate work. Optional AI/model validation remains deferred, not passed and not a blocker.
