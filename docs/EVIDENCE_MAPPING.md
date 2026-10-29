# Explicit evidence-to-job connections — v0.3.6g

## Dashboard workflow

1. Open **Review opportunity**. Read the full original listing and your existing source-backed facts. Only `verified: true`, nonblank, bounded fact/source records can be selected; this boolean remains your attestation, not independent verification.
2. In **Connect your evidence to this listing**, check one to three facts. For each, choose **Description** or **Title**, copy an exact excerpt, choose its exact occurrence and explain the connection in your own words. Multiple identical occurrences require an explicit choice. Offsets are zero-based Unicode code points, not UTF-16 units or bytes; an emoji counts as one code point.
3. Check that you reviewed facts, sources, excerpts and connections against the original vacancy, then choose **Prepare review pack**. No facts are chosen automatically in the dashboard. Facts are quoted in the order they appear in your profile/editor; CLI callers can supply another explicit order. Private explanations never enter the cover prose.
4. Inspect **Your evidence-to-listing connections** in the saved version and review every claim before recording a local reviewed/needs-changes decision. Read the version state as well: stored connections remain inspectable when current validation is blocked, but are not then a fresh approval.

An exact quote and explanation are **not a machine semantic judgment**. Excerpts may be negated, ambiguous or lack context, and a transferable example may use no shared keywords. The app validates identity, current source/target snapshots, exact offsets and explicit choices; it cannot independently establish that your explanation is accurate, persuasive or sufficient. Verify legal/qualification requirements yourself.

## Preview freshness and unsaved edits

The preview fingerprint binds target title/company/URL/description, trimmed candidate name and all currently authorized fact texts/sources. Changing any of these invalidates the map, including a source-only change or change to an unselected authorized fact. A failed/stale map creates no new pack. Refresh and explicitly review current links instead of editing fingerprints to bypass the check.

Connection edits reset confirmation. Refreshing the editor or opening another opportunity asks before discarding unsaved links; cancel keeps them. Saving application progress does not persist the editor. Maps persist only when pack creation succeeds; a repeated preparation creates a distinct immutable version, not an update of the old one. No global reusable mapping, draft-autosave or database migration is introduced.

Limits: one to three distinct facts; excerpt and explanation each at most 1,000 Unicode characters server-side, title or description only. Excerpts must match exact supplied text/offsets; no normalization, paraphrasing or URL fetching. The editor exposes the first 200 exact occurrences and native form limits can be more restrictive for non-BMP characters; use a more specific excerpt or the bounded CLI map for later occurrences. Candidate fact/source limits remain 2,000 characters each. Hidden controls are rejected; ordinary newlines/tabs and literal Unicode/markup are preserved. Maximum 350 cover words still applies.

## CLI and direct callers

Global options precede commands. Preview is read-only and contains private facts/sources, so protect redirected files and shell history.

```sh
python run_local.py --profile-id PROFILE cover-evidence JOB_ID
python run_local.py --profile-id PROFILE pack JOB_ID --evidence-map private-map.json --output PRIVATE_PACKS
```

`private-map.json` is at most 64 KiB. Replace every placeholder with actual preview values. The link example quotes `Python` at codepoint offsets `[0:6]` only if that is the exact current description text:

```json
{
  "format": 1,
  "preview_fingerprint": "COPY_CURRENT_PREVIEW_FINGERPRINT",
  "confirmed": true,
  "links": [{
    "fact_id": "COPY_CURRENT_FACT_ID",
    "field": "description",
    "start": 0,
    "end": 6,
    "quote": "Python",
    "reason": "Your own reviewed explanation of how this fact connects."
  }]
}
```

The original `pack JOB_ID` CLI shape remains supported without `--evidence-map`, as do direct `cover_draft(job, profile)` and legacy writer calls. Compatibility automatic selection only includes facts with a recognized skill shared with the title/description, ranked by overlap then original order, capped at three. It **never fills remaining slots with zero-overlap facts**. With no recognized cues it rejects the draft and requests an explicit map; lack of overlap is not proof of irrelevance because the small lexicon is incomplete. Such maps support user-explained transferable evidence outside the lexicon.

Unmapped compatible drafts report **lexical_cues_only** — not an explicit user connection or independent relevance assessment. Matching a skill string can include negated or mixed context, so review it. The neutral template says examples are provided for review, not that they are proven relevant. To get the explicit workflow, pass a map to `cover_draft(job, profile, evidence_mapping)`, `prepare_pack(..., evidence_mapping=map)` or `CoverLetterWriter.generate(job, evidence_mapping=map)`. `validate_cover_report` and the compatibility `validate_cover` wrapper accept the map as their fifth argument. No model is needed.

## HTTP, storage and privacy

Read-only `/api/cover-evidence?id=JOB_ID` uses the server's active profile and returns a fingerprint, exact target and authorized fact choices. `/api/pack` accepts `{id, evidence_mapping}` via the existing Host/origin/token/content-type protections. Omitted maps preserve bounded lexical-only compatibility; an explicitly supplied null/non-object or invalid map is rejected, not silently downgraded. Exact user choice/confirmation does not authenticate the user's identity in a trusted single-machine local app.

Validator **deterministic cover contract v3** / template **grounded local template v2** include the declared relevance status, exact mapping/connection snapshot and SHA-256 bindings. A changed explanation changes the binding even when draft text is unchanged. The sealed `preparation.json` contains the original map, selected evidence and resolved connections; the legacy evidence sidecar does likewise. These hashes are content snapshots, **not signatures or protection against someone editing the entire workspace**.

No new database table/namespace is created. Pack maps and private explanations require **filesystem pack backups**, not database-only backups. They are not written into candidate evidence, CVs, learning progress, match scores, application status/history, digests, calendar or aggregate reports. Creating the pack itself writes only the new private version directory and existing lock files. Inputs and reasons are rendered as literal text and never opened as paths/URLs, executed, uploaded or sent to a model.

Existing packs/history/CVs remain untouched. Prior validator/template reports may become blocked for new review under v3; preserve old versions and create a new pack after checking current evidence rather than editing an old manifest. Original CV copies remain byte-for-byte, with no rewriting or rendering. Eligibility, applying and outreach remain manual; no submission occurs.

## Next checkpoint

Scoped P6-REL-001 is addressed by exact explicit mappings and removal of automatic zero-overlap fill, not by a claim of universal semantic relevance intelligence. Integrated preparation/learning acceptance is now covered by [Phase 6h](PHASE6_ACCEPTANCE.md). Phase 6 is still active. Optional AI/model work remains deferred, not passed and not a blocker. Full original-spec, live platform/product, Windows and representative performance checks remain unverified.
