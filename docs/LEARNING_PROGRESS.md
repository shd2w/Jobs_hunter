# Manual learning progress — v0.3.6f

## Save and use a practice record

1. Refresh matches after changing evidence or vacancies. In **Skill priorities**, inspect a current required/preferred cue, its original source, reading material and optional exercise. No exercise is assigned automatically. Negated-only, stale-only, uncertain or plain-mention-only context does not offer a positive practice save.
2. In **Optional reading & practice**, choose **Save SKILL practice**. The current preview is checked again before saving. A changed offer must be refreshed; an identical saved snapshot opens the existing record without resetting notes, completion or revision.
3. Under **Your manual practice records**, choose a saved practice, inspect its exercise/self-check snapshot, select **Planned**, **In progress**, **Paused** or **Completed — self-recorded**, add private notes and choose **Save practice progress**.
4. Completed requires the explicit statement that you completed the practice and reviewed its self-checks. This is your own record, not independent grading, verified experience, certification or a hiring qualification. Editing a completed record requires that confirmation again. Reopening to another status clears its current completion timestamp; completing again records a new one.
5. Refresh saved practices to load another tab's changes. Updates and deletions carry an expected revision; stale changes are rejected rather than overwriting newer data. Unsaved notes survive a global dashboard refresh. Explicit record switching/refresh prompts before discarding edits. Deletion also requires confirmation and removes only that saved record, not external work files.

At most **50 saved snapshots per profile**, private notes at most **2,000 Unicode characters** (not bytes). Snapshot versions can coexist when catalog/exercise content changes. Saved records remain inspectable/updateable if the catalog becomes unavailable or guidance/profile/matches change; no content auto-refresh is performed. An old saved link/check date is historical and must be reviewed before reuse. Completion timestamps describe the **current** self-record, not a complete study/event log; no daily counts, hours, proficiency scores or automatic reminders are inferred.

## CLI

Global options precede commands: `python run_local.py --db PATH --profile-id PROFILE COMMAND`. Obtain an offered skill and its `learning_options.plan_fingerprint` from `learning`; replace placeholders, never run them literally.

```sh
python run_local.py learning
python run_local.py learning-save SQL --preview-fingerprint CURRENT_FINGERPRINT
python run_local.py learning-progress
python run_local.py learning-update RECORD_ID --revision 1 --status in_progress --notes "Private practice note"
python run_local.py learning-update RECORD_ID --revision 2 --status completed --completed-attested
python run_local.py learning-delete RECORD_ID --revision 3 --confirm
```

Use the actual latest revision returned by each command. Omit `--notes` to preserve existing notes; `--notes ""` explicitly clears them. No command executes exercise steps, opens a course, uploads a deliverable or modifies candidate evidence. Command-line notes may enter shell history: use the local dashboard for private editing when that matters. JSON output from `learning-progress` includes private notes: protect redirects/files.

## Storage, privacy and recovery

The existing schema-5 `workflow_settings` row contains a dedicated versioned `learning_progress` JSON namespace. Digest preferences and saved searches are preserved in both write directions; writes use transactions, and record revisions prevent lost updates. A record stores an immutable resource/exercise snapshot, SHA-256 content hash, state/notes/revision and UTC creation/update/current-completion dates. No job source excerpts or candidate facts are copied into the snapshot. A hash detects accidental content changes; it is not a signature, reviewer authentication or protection from someone who can edit the whole database.

Malformed/unknown namespaces and invalid stored snapshots fail without silently resetting records. Preserve the database and restore a known-good backup rather than editing internal JSON. Database backups/reopen include the records and private notes, so backups are sensitive. Learning progress does not create study artifacts; back up your own work separately. Pack folders and pack-review history still require separate filesystem backup.

The ordinary guidance endpoint `/api/learning` includes only offers and capability flags, not private records. Records use the profile-scoped `/api/learning-progress` and explicit CSRF-protected save/update/delete routes. Internal audit entries include only record/profile identifiers, revision and status, not note text, resource title or URL. Notes never enter candidate evidence, match scores, application statuses/history, CVs, packs, calendar exports, aggregate progress reports or Telegram digests. Records are local, **not encrypted** and not a hosted multi-user access boundary. Do not store credentials, CV text or confidential employer material in notes. No course, resource, model, source, platform or messaging call is made by this workflow.

## Boundaries and next task

The dated reading catalog/exercise content and requirement-context matching remain unchanged. Reading a page, saving a plan or checking a box is not independent proof of learning; no completion is promoted into your evidence. Scoped P6-LEARN-002 is delivered; Phase 6g adds [explicit evidence-to-job relevance mapping](EVIDENCE_MAPPING.md); the next checkpoint is integrated Phase 6 acceptance. Phase 6 is not complete. Optional AI/model validation stays deferred, not passed and not a blocker. Windows, live integration, representative performance and exhaustive original-spec compliance remain unverified.
