# JobHunter

A private, single-user job-search workspace: deliberate discovery, transparent lexical matching, unchanged original CVs, evidence-backed preparation, and manually recorded progress.

**Current source:** Phase 6g + GitHub launch support. This repository is a sanitized source release, not a backup of anyone's private workspace.

## Open with GitHub

- [GitHub Pages launch page](https://shd2w.github.io/Jobs_hunter/) — static launcher; availability depends on the Pages deployment succeeding.
- [Create a private Codespace](https://codespaces.new/shd2w/Jobs_hunter?quickstart=1) — runs the full Python app, not just a static demo. GitHub sign-in and your explicit workspace creation are required. Compute/storage may incur charges; check your plan and stop unused workspaces.

After setup, open forwarded port **8765** and keep its visibility **Private**. The devcontainer installs the pinned core dependencies and starts the dashboard. If it stops, run `bash .devcontainer/start.sh` in the Codespace terminal. Troubleshooting: [hosting guide](docs/GITHUB_HOSTING.md).

**GitHub Pages cannot execute Python or store a SQLite backend.** It serves only `site/`. A Codespace holds your data on GitHub infrastructure, not solely on your own computer. The backend has no account login and is not intended for a public port or shared/multi-user deployment.

## Run locally

Use Python 3.13. These commands work in a POSIX shell:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-local.lock
python run_local.py serve --port 8765
```

Open `http://127.0.0.1:8765`. On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1` instead of the POSIX activation command. The Windows instructions have not been verified on a Windows machine for this publication.

The server creates an empty SQLite workspace under ignored `data/`. Nothing scans or applies merely because you open it. Review source permissions before explicitly requesting collection; some providers require additional setup, access approval, credentials or optional dependencies. A source adapter existing is not a claim that current live access succeeds.

Optional spreadsheet support: install `requirements-local-excel.txt`. Optional browser-source support has its own `requirements-local-browser.txt` and setup guide. Core usage does not require cloud AI keys. Optional AI/real-model validation remains deferred, not passed.

## Private inputs and backups

- No personal profile, database, CV, tokens, logs, reports or preparation packs are included in this release. `config/profile.yml` is an empty compatibility starter.
- Configure accurate evidence in the dashboard. For CLI profile loading, create an ignored private JSON file, then run `python run_local.py profile my-profile.private.json`. Do **not** put personal information into tracked configuration or commit it.
- Ignored files are not backups. Back up the private database and preparation folders separately, especially before deleting a Codespace. Review any export before sharing it.
- Never paste tokens into chat, tracked files, issues or commit messages. Revoke any exposed credential and use a secure connection or the relevant private secret configuration.

## Features and scope

- Approved, bounded source scans and supported platform-post intake; ambiguous posts remain reviewable.
- Lexical skill/context evidence, explicit exclusion settings and human eligibility review — not an AI suitability or legal-eligibility decision.
- Versioned preparation packs, exact source-backed quotes and explicit evidence-to-listing mappings. No CV rewriting, automatic applications or invented candidate facts.
- Personal follow-ups, manual digests, private calendar snapshots, saved searches and aggregate progress reporting.
- Contextual learning guidance, optional reading/practice and private self-recorded practice progress — not verified qualifications.

Selected guides: [mapping](docs/EVIDENCE_MAPPING.md), [pack versions](docs/PACK_VERSIONS.md), [cover validation](docs/COVER_VALIDATION.md), [learning progress](docs/LEARNING_PROGRESS.md), [learning resources](docs/LEARNING_RESOURCES.md), [contextual learning](docs/CONTEXTUAL_LEARNING.md), [posts](docs/PLATFORM_POSTS.md), [browser sources](docs/BROWSER_SOURCES.md), [calendar](docs/CALENDAR_PHASE5B.md).

## Test and publish

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

CI runs the synthetic test suite on Python 3.13. The Pages workflow publishes only the static launch directory. See [release policy](docs/RELEASE_POLICY.md) for the standing instruction to push verified releases to this repository and preserve GitHub launchability.

Local simulated-host tests are not an end-to-end Codespaces run. Live provider access, Windows execution, representative performance and the next integrated preparation/learning acceptance task remain unverified/pending unless separately recorded.
