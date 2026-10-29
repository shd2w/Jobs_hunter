# Automatic-first discovery — 0.4.0

## Open the app, get jobs

Normal startup (`python run_local.py serve`) starts bounded public-feed scans immediately. No name, CV, skills, keywords, board identifiers or API keys are required. New valid listings are saved progressively and the open dashboard updates every two seconds. Personalization and preparation remain optional; a blank profile is not assigned a fabricated match percentage.

The initial sources are:

| Feed | Starter scope | Earliest next scan |
| --- | --- | --- |
| Jobicy public API | Worldwide remote listings; individual location restrictions still apply | 1 hour |
| Arbeitnow public API | Germany-based feed, not worldwide coverage | 1 hour |
| Remotive public API | Worldwide remote listings; individual restrictions still apply | 6 hours |

These feeds are not a complete search of the internet. Jobicy is delayed three hours and bounded to one page of 100 listings per pass; Remotive is delayed 24 hours. Arbeitnow is one page of at most 100 per pass. Provider attribution and original links remain attached. Absence from a later scan never proves closure. Review the original vacancy and your eligibility before applying.

Provider documentation: [Jobicy](https://jobicy.com/jobs-rss-feed), [Arbeitnow](https://www.arbeitnow.com/blog/job-board-api), [Remotive](https://github.com/remotive-com/remote-jobs-api).

## Controls and persistence

- **Pause discovery** saves the choice in the private workspace, including across restarts. It does not remove jobs. An in-flight HTTP request may finish, but a response observed after cancellation is discarded before intake. Another server's persisted pause is also checked before intake.
- **Resume discovery** checks due sources; it never clears cooldowns or provider gates, reapproves blocked sources, or triggers paid setup.
- **Check due feeds** wakes the coordinator. It is not a force-refresh or a quota bypass.
- The coordinator checks eligibility to run every minute while the Python server remains running. It stops when the server or Codespace stops. Opening the static Pages launcher does not start a scan.
- Source failures are isolated. See **Feed status & coverage** for errors and next allowed times. A 429 pauses that provider and retains Retry-After restrictions. Review its access/quota conditions before reapproving it.
- Each cycle attempts at most ten due, approved sources. The oldest checked sources get priority, preventing additional sources from being permanently starved. Existing single-scan locks prevent manual/automatic overlap; a separate coordinator lock prevents duplicate automatic cycles.
- Expired Jobicy cursors restart a due pass at the first page. Only that checkpoint is reset; existing jobs, approvals, cooldowns and Retry-After gates remain intact. Manual scans retain their explicit-reset behavior.
- Existing private profiles, notes, application states, saved searches, learning records and CVs are preserved. Starter registration is insert-only and happens once per profile's automatic-discovery setup. It never reapproves an existing paused source.

## More channels

Already approved custom sources join automatic discovery when due. Add new sources in **Discovery** only when authorized. Wuzzuf/Naukrigulf may reject access or change markup; the app does not solve anti-bot challenges or turn a denied response into a success. Social APIs still need their authorized account/source configuration. No paid API key or account credentials are invented or enabled by this release. A disconnected or blocked platform does not hold up the public starter feeds.

## Update an existing Codespace

In the repository terminal:

```sh
git pull --ff-only
bash .devcontainer/start.sh --restart
```

Then open **Ports → 8765 → Open in Browser**, keeping visibility **Private**, and reload the tab. The old Python process must restart to load the new backend; a browser reload alone is insufficient. If Git reports local changes, preserve them before updating; do not force-reset private work. If the PID file belongs to an unrelated process, the start script refuses to stop it.

For an offline/manual session use `python run_local.py serve --manual-discovery`. Direct `make_server` and `serve` library calls remain manual by default so synthetic test harnesses do not unexpectedly contact providers.

## Validation and honest limits

A disposable blank-workspace live check during this release collected **112 unique jobs** with no profile input: **100 from Jobicy and 12 from Remotive**. Arbeitnow failed its response/access path and did not block the working feeds. This is one observed run, not a promise of current counts, availability, completeness or candidate fit. No live job payloads or databases are published in this repository.

Offline regression covers first-run intake, no-profile browsing, failure isolation, persistent pause, in-flight cancellation, provider cooldowns/429 gates, fair scheduling, expired-cursor handling, preserved settings, optional matching, HTTP controls and safe Codespaces restarts. `qa/automatic_browser.py` additionally checks progressive arrival, mobile light/dark layouts, draft preservation and browser errors against disposable fixtures. No fixture result is represented as a real provider result. Remote Codespaces runtime, Windows, optional AI/real-model validation and continuous availability remain unverified; no billable infrastructure is provisioned by these tests.

Release checks completed: **1,675 tests passed**, the existing **47-operation** integrated HTTP smoke passed, and **six dashboard plus three launcher** browser states were rendered and visually inspected. These local checks do not substitute for remote Codespaces validation.
