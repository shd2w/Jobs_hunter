# JobHunter

A private, single-user job-search workspace that starts finding jobs automatically. Open the app, browse public-feed results, and add a profile only if you want personalization. Original CVs stay unchanged; applying stays in your hands.

**Current source:** 0.4.1 — automatic-first discovery + GitHub launch support. This repository is a sanitized source release, not a backup of anyone's private workspace.

## Open with GitHub

- [GitHub Pages launch page](https://shd2w.github.io/Jobs_hunter/) — static launcher; availability depends on the Pages deployment succeeding.
- [Create a private Codespace](https://codespaces.new/shd2w/Jobs_hunter?quickstart=1) — runs the full Python app, not just a static demo. GitHub sign-in and your explicit workspace creation are required. Compute/storage may incur charges; check your plan and stop unused workspaces.

After setup, open forwarded port **8765** and keep its visibility **Private**. The devcontainer installs the pinned core dependencies and starts the dashboard. Starter feeds scan automatically as soon as the Python server starts. No profile or source entry is needed. If it stops, run `bash .devcontainer/start.sh` in the Codespace terminal. Troubleshooting: [hosting guide](docs/GITHUB_HOSTING.md).

**GitHub Pages cannot execute Python or store a SQLite backend.** It serves only `site/`. A Codespace holds your data on GitHub infrastructure, not solely on your own computer. The backend has no account login and is not intended for a public port or shared/multi-user deployment.

## Already have a Codespace open?

Update the code **and restart the Python server**:

```sh
git pull --ff-only
python -m pip install -r requirements-scanners.lock
bash .devcontainer/start.sh --restart
```

Open **Ports → 8765 → Open in Browser**, keep visibility **Private**, and reload. No profile setup is required. If Git refuses because of local changes, preserve those changes first; do not force-reset your work.

## Run locally

Use Python 3.13. These commands work in a POSIX shell:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-scanners.lock
python run_local.py serve --port 8765
```

Open `http://127.0.0.1:8765`. On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1` instead of the POSIX activation command. The Windows instructions have not been verified on a Windows machine for this publication.

The original configured JobSpy searches (Indeed, LinkedIn, Google retained, plus Bayt) are reconnected, alongside Remote OK and We Work Remotely. Search access varies; Google currently fails upstream and Bayt returned 403 in testing. The server creates a private SQLite workspace under ignored `data/` and starts the preconfigured Jobicy, Arbeitnow and Remotive public feeds. Results arrive automatically; a failed feed does not block the rest. No name, CV, skills or API key is required. Pause/resume is persistent. Scans respect provider cooldowns and run only while the server is running. Additional channels may still require setup or fail access checks. Nothing applies on your behalf. See [automatic discovery and coverage](docs/AUTOMATIC_DISCOVERY.md).

Optional spreadsheet support: install `requirements-local-excel.txt`. Optional browser-source support has its own `requirements-local-browser.txt` and setup guide. Core usage does not require cloud AI keys. Optional AI/real-model validation remains deferred, not passed.

## Original scanner preserved and expanded

See [regression investigation, changes and live source results](docs/SCRAPER_RESTORATION.md). `python run_scan.py` retains the original configured scan → filter → deduplicate → Markdown/history/cache workflow and now also fills the SQLite inbox. `python run_all.py --scan-only` remains available. Docker Compose again runs collection every six hours; do not simultaneously run both full-scan and dashboard schedulers against the same workspace. The dashboard uses bounded provider/query/page checkpoints. Existing legacy data is backed up and archived non-destructively on first startup; conflicting identities are reported, never overwritten.

## Private inputs and backups

- No personal profile, database, CV, tokens, logs, reports or preparation packs are included in this release. `config/profile.yml` is an empty compatibility starter.
- Configure accurate evidence in the dashboard. For CLI profile loading, create an ignored private JSON file, then run `python run_local.py profile my-profile.private.json`. Do **not** put personal information into tracked configuration or commit it.
- Ignored files are not backups. Back up the private database and preparation folders separately, especially before deleting a Codespace. Review any export before sharing it.
- Never paste tokens into chat, tracked files, issues or commit messages. Revoke any exposed credential and use a secure connection or the relevant private secret configuration.

## Features and scope

- Zero-input startup: automatic bounded public-feed scans, progressive inbox updates, source status, and persistent pause/resume. Additional approved sources join when due.
- Supported platform-post intake; ambiguous posts remain reviewable and account-dependent platforms still need authorized configuration.
- Lexical skill/context evidence, explicit exclusion settings and human eligibility review — not an AI suitability or legal-eligibility decision.
- Versioned preparation packs, exact source-backed quotes and explicit evidence-to-listing mappings. No CV rewriting, automatic applications or invented candidate facts.
- Personal follow-ups, manual digests, private calendar snapshots, saved searches and aggregate progress reporting.
- Contextual learning guidance, optional reading/practice and private self-recorded practice progress — not verified qualifications.

Integrated checkpoint: [preparation and learning acceptance](docs/PHASE6_ACCEPTANCE.md).

Selected guides: [mapping](docs/EVIDENCE_MAPPING.md), [pack versions](docs/PACK_VERSIONS.md), [cover validation](docs/COVER_VALIDATION.md), [learning progress](docs/LEARNING_PROGRESS.md), [learning resources](docs/LEARNING_RESOURCES.md), [contextual learning](docs/CONTEXTUAL_LEARNING.md), [posts](docs/PLATFORM_POSTS.md), [browser sources](docs/BROWSER_SOURCES.md), [calendar](docs/CALENDAR_PHASE5B.md).

## Test and publish

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

CI runs the synthetic test suite on Python 3.13. The Pages workflow publishes only the static launch directory. See [release policy](docs/RELEASE_POLICY.md) for the standing instruction to push verified releases to this repository and preserve GitHub launchability.

Local simulated-host tests are not an end-to-end Codespaces run. Live provider access, Windows execution, representative performance remain unverified/pending unless separately recorded. The integrated local preparation/learning acceptance checkpoint is documented separately; it does not close those deployment checks.
