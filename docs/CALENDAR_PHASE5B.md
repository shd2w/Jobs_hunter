# Private calendar snapshots — Phase 5b

## What this does

In **Planning & reminders → Export a private calendar snapshot**, choose a reference date and window, preview, then download an all-day `.ics` file. No external calendar account is connected and no API, sync, invitation, scheduler, alarm or message is triggered by JobHunter. Downloading does not mark a task done or change application status, notes, matches or notification preferences.

Schema **5 is unchanged** from v0.3.5a. Extract this cumulative release into a new folder and back up your current database before selecting it. For older schemas, back up the database and use the current CLI migration help; an already-upgraded schema-5 database needs no additional migration. Historical cumulative-release instructions are not included in this source-only publication. Core dependencies are unchanged.

## Included reminders and date window

- Application deadlines must be explicitly recorded in the local tracking workflow, with current state discovered/saved/reviewing/preparing/ready. Applied, interview, offer and closed records no longer create application-deadline calendar events.
- Personal follow-ups must be unfinished. They remain eligible even when the underlying job is closed because they are your explicit personal tasks. Completed tasks are excluded.
- Choose **0–365 days ahead**, plus optional **0–365 days before** the reference date. Both endpoints are inclusive. Zero days ahead exports the reference day only. Past reminders are excluded by default, unlike the main inbox's overdue view.
- Dates are complete `YYYY-MM-DD` calendar days on the computer running JobHunter. They are not UTC closing instants, employer-verified deadlines or timezone-aware alerts. Every event spans that date through the exclusive next-day end.

The preview reports the full eligible count in the window, valid items outside it, and invalid stored dates omitted. It shows all event previews when there are at most ten, otherwise a clearly bounded ten-event sample. It does not silently repair legacy dates or include the source job's unrecorded closing date. Empty output means no eligible local reminders in that window, not proof that the original vacancies have no deadlines.

At most **1,000 events / 8 MiB** per export. These bounds and impossible all-day end dates beyond year 9999 disable export in the preview; narrow the range if necessary. No first-page truncation or partial calendar is substituted.

## Privacy choices

By default, event summaries are simply **Application deadline** or **Personal follow-up**. Job names, companies and original URLs are excluded. Generic files still disclose reminder dates, event counts and stable identifiers; treat them as private files.

The separate **Include job title, employer and original URL** checkbox adds those listing fields to the snapshot, including any original URL query parameters. It does not allow candidate evidence, name, CV contents, application notes, personal task notes or custom personal task titles. Even with details enabled, personal tasks retain the generic task label with optional job context rather than their private custom title.

The file never contains ATTENDEE, ORGANIZER, METHOD, VALARM or ATTACH properties. Events are marked transparent/non-blocking. Source text is escaped as iCalendar text, and the browser preview renders it as text, not HTML. UTF-8 physical lines are folded by octet count with CRLF endings; local IDs are stable hashes, not raw profile IDs or database paths. Hashing is not encryption or a guarantee of anonymity.

**Importing into a synced calendar can upload the file's contents to that service.** JobHunter does not perform or authorize that upload. Review the downloaded file and the destination calendar's sharing/privacy settings first. A calendar app may apply its own default reminders, sharing or availability behavior even though this exporter supplies no alarms or participants.

## Preview and stale-data protection

Changing the window/detail choice clears the browser preview and disables download. Changes to the underlying reminders or relevant listing data are checked again on the server using a current-preview fingerprint. If data changed, preview again instead of exporting stale content. A delayed preview response cannot re-enable a download after its options have changed. Both mouse and keyboard preview controls are exercised in QA.

The file is downloaded by your browser; the server never selects an arbitrary export path. A preview is read-only and creates no file. Empty snapshots are valid calendars containing no events.

## CLI

Use your actual database/profile and dates. Examples below use a reference date only as an example, not as a real deadline:

```sh
python run_local.py --db data/phase5.sqlite3 --profile-id default calendar-preview --start 2026-11-01 --days 30
python run_local.py --db data/phase5.sqlite3 --profile-id default calendar-export output/reminders-new.ics --start 2026-11-01 --days 30
# Explicitly include bounded past reminders and job details:
python run_local.py --db data/phase5.sqlite3 --profile-id default calendar-preview --start 2026-11-01 --days 7 --past-days 3 --include-job-details
python run_local.py --db data/phase5.sqlite3 --profile-id default calendar-export output/reminders-details-new.ics --start 2026-11-01 --days 7 --past-days 3 --include-job-details --preview-fingerprint CURRENT_PREVIEW_FINGERPRINT
```

`--start` defaults to the current local calendar day. `--preview-fingerprint` is optional in the CLI; when supplied it must match the current content/options. Always use a **new output filename**. Atomic no-clobber publication rejects existing files or symlinks rather than replacing originals. The browser download always requires a current preview.

## Snapshot and importer limits

This is not a subscribed calendar feed or two-way synchronization. Events have stable IDs across rescheduling/backups for the same profile/reminder, but **a particular calendar app may duplicate reimports or fail to update existing entries**. Completing a task, applying for a job, rescheduling or deleting a record does not send a cancellation or remove an already imported event. Manage previous imports explicitly; consider using a dedicated private calendar when reviewing snapshots.

No Outlook/Google/Apple calendar import, authenticated calendar connection, Windows execution or real timed reminder delivery was verified here. Actual evidence covers generated bytes, local Chromium downloads, synthetic backend/UI/CLI behavior and retained regression. Saved searches, advanced outcome reporting and other Phase 5 tasks remain pending. Optional AI/model validation is still deferred at the user's instruction.
