# Dashboard search bridge and stale-build diagnostics

## Reported symptom and confirmed boundaries

The reported screen listed only Arbeitnow, Jobicy and Remotive, with the older “Worldwide remote + Germany starter feeds” scope text. Arbeitnow showed a generic ValueError, Jobicy reported 100 new records and Remotive zero new records.

- That is not evidence of broad scraping. Cooldown is not a scrape failure, and zero new records can be empty results or duplicates.
- In the repository at `1a7ad2d...`, `automatic.STARTERS/configure` already contains 16 seeded mechanisms, including all nine pinned JobSpy providers; existing source approvals/deletions remain authoritative.
- **Confirmed integration gap:** the newly implemented candidate-derived `discovery_run` had a CLI entry point but was not called by the dashboard's older `AutomaticDiscovery` coordinator. The prior implementation report's distinction between the CLI runner and existing scheduler was material to actual usage.
- **Inferred, not established:** the quoted older scope text suggests an older running build. The user's running server, installed packages, source database and original failed response were not available for inspection. The exact Arbeitnow failure cannot be reconstructed from a generic historical ValueError.

## Fix

1. Added **Search from my profile** to the existing dashboard. The CSRF-protected `POST /api/profile-search` queues one bounded profile-derived run on the **same coordinator worker** as source refresh. The HTTP request does not wait on provider latency. Duplicate pending clicks coalesce. Pause and persisted cancellation apply.
2. The run uses the existing 12-attempt/120-second dispatch bounds and existing source/provider gates. It does not autoapprove new sources, reset cooldowns, add paid access or create a second competing scanner. In-flight vendor calls can exceed the dispatch deadline, as documented previously.
3. The dashboard shows the latest persisted search, task/source attempts, failures/deferred reasons, raw insertion counts and recognized-source lead count. Running counters derive from persisted tasks before the final report is committed. This is not proof of live publisher availability, global coverage or relevant uniqueness.
4. Added **read-only** `GET /api/runtime`: build `dashboard-discovery-bridge-1`, source fingerprint, Python and installed JobSpy/Scrapling versions. Source status includes registered-source inventory and safe error type/stage/code/HTTP status. Known Arbeitnow payload/content-type failures have fixed explanatory hints; arbitrary provider bodies, credentials and candidate values are never copied into diagnostics.
5. Kept Check due sources for ordinary approved-source refresh. It is distinct from the new candidate-derived profile search. Neither action bypasses quota/access rules. GET status does not migrate the database or register sources.

The runtime fingerprint is a diagnostic of the installed source files, not an authenticated Git revision or proof that every publisher works. **Restart the Python process after updating.** Installing source on GitHub does not update an already-running local server or Codespace.

## Verification

- Added seven test cases in `tests/test_dashboard_discovery_bridge.py`: real HTTP action -> existing worker -> generated JobSpy request -> shared intake/status; CSRF/option/pause constraints; manual/read-only runtime status; three safe source-error variants; cancellation/no approval override; in-progress persisted counters.
- Local full suite: **1,800 passed in 51.17s**. Existing test files were not weakened/deleted. Integrated synthetic preparation/learning compatibility smoke also passed, with zero external requests and the synthetic original CV hash preserved.
- **Controlled browser passed**, with the application's CSP retained: clicked the actual dashboard button, dispatched nine fake-provider generated queries, inserted one synthetic canonical record, displayed three independent fixture failures and deferred work, showed 16 registered mechanisms/build/package versions, retained expanded report across polling, zero JavaScript errors. This is not live nine-provider scraping evidence.
- **One real Arbeitnow recheck passed from the agent environment**, using the existing synthetic qualification database and its retained gates: 300 valid records, 0 invalid, 234 insertions and 66 updates. These are raw canonical intake counts, not verified unique relevant opportunities. This does not establish the user's runtime health or explain its earlier response failure. No extra live tests of all nine boards were performed for this fix.
- No user database, profile, CV or remote runtime was changed. Raw browser/live artifacts remain private and outside Git. No billable environment, Codespace or public Python backend was started.

## Update the actual running instance

First inspect `git status`; preserve unrelated local changes. On the intended project checkout:

```text
git pull --ff-only origin main
python -m pip install -r requirements-dev.txt -r requirements-scanners.lock
python -m pip check
```

Use that environment's Python interpreter, not an unrelated system interpreter. If the checkout cannot fast-forward, do not force-reset local work.

**Windows/local terminal:** stop the existing JobHunter server with Ctrl+C in its owning terminal, then launch with the same database/profile arguments previously used:

```text
python run_local.py serve --port 8765
```

If using an explicit database/profile, those global arguments go before `serve`. Do not create a new empty database merely to clear errors or gates.

**Already-existing private Codespace:** after updating/installing in that workspace, use its existing owned-process restart helper:

```text
bash .devcontainer/start.sh --restart
```

This is not a request to create a new paid Codespace. Keep the forwarded port private.

Refresh the dashboard. Under **Source status & coverage**, verify `Server build: dashboard-discovery-bridge-1`, installed engine versions and the source inventory. Click **Search from my profile** and inspect its actual attempt results. Many tasks may legitimately be deferred by gates/budget or fail due to upstream access; they must not be counted as successful scraped sources.

For direct local diagnosis, visit `http://127.0.0.1:8765/api/runtime` (or the equivalent existing private forwarded origin). A 404 or missing new build identifies an old/incompatible runtime; do not assume refreshing the browser updates Python. The new diagnostic code/stage applies to subsequent failures, not retroactively to old responses.

If only three cards remain after the new build is confirmed, inspect source inventory/approvals without resetting them. Previously paused/deleted sources are not blindly reenabled. The next needed evidence is the actual runtime build/dependency status and the affected source's new diagnostic code/stage/HTTP status, not candidate/private data or credentials.
