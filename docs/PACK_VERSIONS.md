# Preparation versions and explicit local review

## Create and preserve versions

Every core preparation creates a private `pack-VERSION_ID` directory. IDs are opaque random version identifiers, not sequential revision numbers. New versions always start **pending**, even when an older version was reviewed. Creation never overwrites or deletes an earlier pack, draft, sidecar or original CV.

The legacy `CoverLetterWriter` now writes each run into its own `cover-VERSION_ID` directory. Its returned `output_path`, `success`, evidence/method fields and basename ending `-cover.md` remain compatible with the legacy PDF/export caller. A sibling `.evidence.json` and `draft-version.json` record the generated artifacts/hashes. Old flat outputs and edited prior versions are left alone. Legacy outputs require ordinary manual review; they are not automatically imported into the core review panel. Optional later PDF conversion is not included in the sealed legacy draft manifest and was not executed in this checkpoint.

Both writers construct a new same-filesystem staging directory, finish their files and metadata, then publish by directory rename under a local lock. Ordinary write/seal/publication failure removes only the new stage. A crash can leave an unpublished `.pack-stage-*` directory; it is not listed or accepted as complete. Preserve it for inspection if needed; there is no automatic destructive recovery. Namespace publication is atomic; this is not a guarantee against power-loss/filesystem corruption or a cross-database/filesystem transaction. Core integrity checks detect missing/changed known artifacts on subsequent inspection.

## Dashboard

Open an opportunity, [connect one to three verified facts to exact listing excerpts](EVIDENCE_MAPPING.md), explain the connections, explicitly confirm them, then choose **Prepare review pack**. The modal stays open, selects the new version and displays:

- Exact cover draft, selected source-labelled evidence and the saved user-attested connections/excerpts/reasons, rendered as text. Saved connections remain visible even if current validation is blocked.
- Current validation check results and original-CV copy hash or explicit absence.
- Pending, reviewed, needs-changes or blocked state and historical local decisions.

Use **Refresh versions**, select a saved version, or load more pages (50 versions per page). Review the original vacancy yourself. **Record reviewed** requires all four checkboxes: quoted facts/sources, original role/employer, original CV copy/absence and manual-only eligibility/submission. **Record needs changes** can be used without checking every item, but both actions require an explicit confirmation dialog. Cancelling records nothing. Opening, creating, refreshing or selecting a version never records a review.

These decisions are **local self-records**, not independently verified facts, authenticated reviewer identity, eligibility clearance, employer approval or applications. They do not change tracking status, source approvals, CVs, or notification settings. Even after `reviewed`, `review_required` remains true as a reminder that the user decides what to use and applies manually.

## CLI

Use the same explicit root for each command. The longstanding CLI default is `output/packs`; the dashboard uses `preparation-packs` beside its database. To manage dashboard-created versions from CLI, pass that dashboard root with `--output` and the same database/profile.

```sh
python run_local.py --db PRIVATE_DB pack JOB_ID --output PRIVATE_PACK_ROOT
python run_local.py --db PRIVATE_DB pack-list --job-id JOB_ID --output PRIVATE_PACK_ROOT
python run_local.py --db PRIVATE_DB pack-inspect VERSION_ID --output PRIVATE_PACK_ROOT
python run_local.py --db PRIVATE_DB pack-review VERSION_ID --output PRIVATE_PACK_ROOT --decision reviewed --fingerprint FRESH_INSPECT_FINGERPRINT --confirm
```

For corrections use `--decision needs_changes` with a new inspection fingerprint and explicit `--confirm`. `--confirm` attests to the four review checks; do not use it without personally reviewing. A preview used to record one decision cannot be reused to append another; inspect again. `pack-list --offset 50` retrieves the next page. `--profile-id` scopes all commands.

The loopback endpoints are GET `/api/packs?job_id=...&offset=...`, GET `/api/pack-inspect?id=VERSION_ID` and POST `/api/pack-review`. POST requires existing CSRF/Host/Origin checks, `confirmed: true`, `decision`, fresh `fingerprint` and the four boolean `checks` keys `facts`, `target`, `original_cv`, `manual_submission`. The server uses its fixed pack root, not a client-supplied path. IDs must be 32 lowercase hexadecimal characters and the manifest owner must match the active profile. This is trusted-local profile separation, not multi-user authentication.

## Integrity, stale data and review records

Format-1 `pack.json` stores creation time, owner profile/job, current-input context hash and hashes of the known generated artifacts. `preparation.json` retains job/match/provenance, validation and evidence metadata. Existing exact-template checks are unchanged. Original CVs, when selected, remain byte copies with SHA-256 comparison.

Inspection checks known artifact bytes, current job/profile/provenance context, deterministic cover validation and the selected original CV source/copy. Changed bytes, missing/linked files, changed profile/job/provenance or original CV source, malformed metadata/history and stale validation block new decisions. A tracking-status/note change alone is not a job-input change. Generate a new version after changing evidence or draft content; edited free-form letters are not accepted by the supported-template validator. If exact inputs are restored, inspection may again match the original snapshot: stale/blocked is computed, not an irreversible revocation event.

Decisions are separate append-only numbered JSON events under `reviews/`, up to 1,000 per version. Each includes UTC time, owner, explicit check values, decision, inspected artifact/preview fingerprints and the prior event hash. Concurrent decisions are serialized; only one can use a given preview. History corruption is surfaced, never silently reset. Lists omit versions whose owner/format manifest cannot be read; older unversioned folders remain untouched, not falsely labelled reviewed. Invalid artifacts in a readable owned version show blocked.

Hashes and chains are **not signatures or tamper-proof proof**. A local user who edits all files/metadata can forge them; ordinary filesystem races and whole-DB/whole-filesystem atomicity are not eliminated. Inspection is a bounded snapshot, not a filesystem watcher. Refresh before recording a decision and inspect original sources before applying. Only known manifest artifacts are covered; extra files added manually are not certified. Locks are implementation files beside the root, not candidate artifacts. Format-1 packs are compatibility-scoped; future validator changes may require regeneration rather than silently granting current review validity to old drafts.

## Backup and privacy

Pack drafts, preparation metadata, evidence and original CV copies are sensitive plaintext. **Database backups do not contain pack folders or filesystem review events.** Back up the entire private pack root separately, including manifests, artifacts and review directories, on encrypted storage while the app is stopped. Keep original CVs separately too. Do not publish the preserved project archive or deploy the loopback app as a hosted multi-user service.

Old files are not migrated/deleted. No cloud/model request, recruiter outreach, automatic application or CV rewrite occurs. Windows execution, optional PDF rendering, power-loss resilience and representative large-pack performance remain unverified. Optional AI/real-model work stays deferred, not passed and not a blocker. Evidence relevance mapping and contextual skill guidance/resources/exercises/progress remain pending Phase 6 work.


## Phase 6g mapping and older versions

A mapped pack stores the explicit map, immutable relevance snapshot and validator-v3 bindings in the sealed `preparation.json`. Current inspection revalidates selected facts, sources, target and exact excerpt offsets. Reason edits change the validation contract hash even if cover prose is identical; create a new pack, never patch a prior version. Source-only changes stale the preview/pack. A changed source is not automatically false; review and re-map current inputs.

Earlier validator/template versions remain on disk untouched. Their previous reports may fail current validation equality and become blocked for new review; create a fresh version under the current contract. Prior review history is preserved as history, not carried forward. Hashes are not signatures or independent relevance verification. Mapping metadata and private reasons are filesystem pack content, **not included in database-only backups**.
