# Wuzzuf / Naukrigulf: explicit browser-assisted collection

The direct client cannot solve a provider's browser challenge by skipping robots checking. The optional route uses an ordinary **dedicated Chrome/Edge** browser and reads its public rendered HTML/JSON-LD. It does not spoof headers, extract/replay cookies, change IPs, call hidden APIs, log in, solve access controls automatically or submit applications. There is **no automatic fallback** after a failed HTTP scan.

## Windows PowerShell — recommended setup

Extract this checkpoint into a new directory. Keep existing data and back up your existing canonical SQLite database before selecting it with `--db`. The delivered original data/config/reports are unchanged. Test jobs and test browsers are not bundled.

With the project's Python environment activated:

```powershell
python -m pip install -r requirements-local.lock
python -m pip install -r requirements-local-browser.txt
.\start_board_browser.ps1
python run_local.py serve
```

The script locates your installed Chrome/Edge. It does not download a browser or change execution policy. If scripts are restricted, use your approved local script-execution process; do not weaken organizational policy. This Linux checkpoint reviewed the Windows script but did not execute it on Windows.

The launcher starts a dedicated public-only profile at `%LOCALAPPDATA%\JobHunter\PublicBoardBrowser`, binds debugging to `127.0.0.1:9222`, and sets these variables in **that terminal**:

```powershell
$env:JOBHUNTER_AUTHORIZED_BOARD_TRANSPORT = "browser"
$env:JOBHUNTER_BOARD_BROWSER_CDP = "http://127.0.0.1:9222"
```

Run the CLI/server from the same terminal. Restart a previously running dashboard so it inherits the selection. Default remains `http` in terminals that have not selected browser mode. Source policy shows the active transport. To return to direct HTTP, set the transport variable to `http` and restart the server; that does not cure provider HTTP restrictions.

Use only this dedicated profile, never your main personal browser/profile. Do not sign into personal accounts. Debugging gives local processes control over the browser, so keep the port on loopback, do not tunnel or publicly expose it, and close the dedicated browser when done. The launcher refuses an occupied port rather than trusting an unknown listener. This is a trusted single-user-machine feature, not multi-user service isolation. Docker-to-host remote debugging is not configured; do not widen the listener to make it work.

Linux/macOS can start an installed Chromium/Chrome with a separate `--user-data-dir`, `--remote-debugging-address=127.0.0.1` and `--remote-debugging-port=9222`, then export the same variables before starting JobHunter. Use a normal browser, not stealth extensions or disabled security. No `playwright install` or Node installation is needed for this client.

## Register and scan

In Discovery choose `wuzzuf` / `naukrigulf` and the public listing URL:

- `https://wuzzuf.net/a/Jobs-in-Egypt`
- `https://www.naukrigulf.com/jobs-in-egypt`

Review the permission checkbox and save. Nothing runs until **Scan now** or a selected batch scan. Equivalent CLI:

```powershell
python run_local.py source wuzzuf https://wuzzuf.net/a/Jobs-in-Egypt --approve
python run_local.py source naukrigulf https://www.naukrigulf.com/jobs-in-egypt --approve
python run_local.py source-health
# Copy the exact saved source ID printed above; do not use this placeholder literally.
python run_local.py scan SOURCE_ID
```

For an existing canonical database, put `--db PATH` before the command. A previous access failure pauses sources of that provider: reapprove deliberately only after reviewing access and configuring the browser route. Existing one-hour cooldown and Retry-After gates still apply. **Reset scan progress does not reset those gates.** Do not delete the database or register alternative listings to get around them.

### Bounds and semantics

- One listing plus at most four details per requested scan; default scoped robots skip means at most **five top-level navigations**, or six with robots check restored. The browser also requests JavaScript, CSS, images and other normal resources. This is **not a five-HTTP-request browser mode**; run metrics separately count observed resource requests. The live samples observed 471 and 520 resource requests respectively.
- Up to 30 seconds for navigation, then publisher readiness polling within a 60-second per-page target. No network-idle wait: analytics must not hold job extraction open. Actual browser/OS operations can add cleanup overhead. Cancellation is checked between pages and while polling; active navigation can take its timeout before cancellation is seen.
- Only publisher JobPosting JSON-LD is normalized. Listing leads may come from anchors or ItemList URLs. No job is invented from a title-only card. Naukrigulf's initial empty shell is not accepted as a completed detail.
- Exact approved top-level hosts/paths, no redirected navigation, at most 5 MiB serialized HTML per page (256 KiB crawler rules), committed-only pending details, page cap, URL deduplication, atomic jobs/checkpoint/run writes and one-hour provider-wide cooldown remain.
- Browser assets use the browser's normal network stack, **not** the direct client's DNS-pinned/asset-isolated transport. This optional route has a different security and traffic boundary. User-approved provider content/scripts run in the dedicated browser.
- Only the temporary collector tab is closed; the user-owned browser stays open. No browser cookies/profile contents or remote error bodies are copied to application logs/database/archive.

## Failure handling

Missing optional client, browser not running, structured-data timeout and wrong format produce sanitized diagnostics. A failed page does not advance the canonical checkpoint. HTTP 401/403 or visible access challenge stops the scan and unapproves that provider; 429 also persists its Retry-After gate. There is no stealth retry or alternate-IP fallback.

If a public page requires human verification, collection stops. Inspect the dedicated browser manually using only your authorized access method, then review/reapprove and retry **when due**. If access is still denied, obtain the provider's supported/allowlisted route or supply an authorized export. Provider permission does not guarantee every network path will work.

## What was genuinely verified

On 2026-10-29 a managed standard browser in this Linux environment loaded both public listings and four details per board. The shipped browser collector and normal `sources.scan` pipeline saved **eight genuine jobs**, zero invalid rows, transactional checkpoints, and SQLite integrity `ok`. A test connector supplied the environment's managed CDP connection; production endpoint validation remains loopback-only. The Windows localhost launcher, long-running browser stability, robots-check browser path against live rules, later pages and whole-site completeness were not verified live. Fixtures cover many of those contracts but are not live evidence. The private historical live-result archive is not part of this source-only release; current access must be checked separately.
