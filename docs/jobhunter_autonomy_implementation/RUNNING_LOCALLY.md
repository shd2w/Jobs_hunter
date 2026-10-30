# Local on-demand autonomous discovery

This adds a CLI path; it does not require continuous cloud execution, replace the existing server discovery scheduler, or claim every configured provider is available. GitHub Pages remains a static launcher, not the Python runtime. These Windows commands are documentation, **not Windows execution evidence**.

## 1. Prepare the existing runtime

In PowerShell, from the repository root, use the project's Python 3.13 environment and pinned requirements:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt -r requirements-scanners.lock
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q
```

Use `python` below for that environment's interpreter (or substitute `.\.venv\Scripts\python.exe`). Dependency installation/Windows runtime were not performed during implementation. This work introduced no required paid service or new requirement file edits. Optional legacy cloud evaluation retains its separate configuration.

## 2. Candidate intent, not a website list

Back up an existing database before first use:

```powershell
python run_local.py --db data/jobhunter.sqlite3 backup backups/before-discovery.sqlite3
python run_local.py --db data/jobhunter.sqlite3 --profile-id default init
```

Optionally save legitimate candidate facts/preferences in a private local JSON file, for example:

```json
{
  "skills": ["Python", "SQL"],
  "matching": {
    "preferred_title_terms": ["backend"],
    "preferred_location_terms": ["Germany"]
  },
  "languages": ["en", "de"]
}
```

```powershell
python run_local.py --db data/jobhunter.sqlite3 --profile-id default profile private-candidate.json
```

Do not commit candidate files. Skills and role families drive finite EN/DE/AR packs; arbitrary occupations/languages are not fully covered. An empty/default profile can use broad defaults, reported as such, rather than inventing candidate qualifications. No company/source/website list is required.

## 3. Initiate a finite cycle

Global options `--db` and `--profile-id` must appear **before** the subcommand:

```powershell
python run_local.py --db data/jobhunter.sqlite3 --profile-id default discover --region Germany --language en --attempts 12 --seconds 120
```

Repeat `--region`/`--language` for additional intended scope (bounded). All nine existing JobSpy providers are planned by default, subject to supported parameters, source approvals, readiness, provider cooldowns and finite budget. Native sources are explored too. A run does not promise to contact all providers. Unsupported, paused and unfinished tasks are explicit. More attempts do not override source gates.

First use creates a `.pre-autonomy-v1-<timestamp>.bak` SQLite backup and version-1 additive tables; the original Store schema version stays 5. Do not delete history/databases to bypass cooldowns. Backups contain private data and must remain private. Restore using the existing CLI into a **new destination** after stopping active processes; do not manually drop extension tables as a routine rollback.

The time budget stops **new dispatch**, not an in-flight provider call. Keyboard interrupt may leave an interrupted run; reopening the finite runner reconciles task state. Do not use a hard timeout on a production database as routine cancellation. The dedicated QA harness uses disposable state for that reason.

### New source access policy

Without extra flags, observed supported new sources are cataloged and bound but remain inaccessible until approved. A candidate need not supply their URLs. If, and only if, the operator has reviewed applicable ATS/employer terms and can explicitly attest access for new public ATS bindings:

```powershell
python run_local.py --db data/jobhunter.sqlite3 discover --region Germany --language en --approve-public-ats
```

This is **not** automatic authorization, does not reapprove a previously paused source, and is not appropriate where source-specific terms need a separate decision. Existing `source` approval workflow remains available for a reviewed individual binding. Feed/structured methods need their own explicit approval. Blocked/login-required endpoints are not bypassed.

Optional `--inspect-public-links` enables at most two robots-checked observed first-party inspections per run. These can still be blocked/unsupported; no universal crawl or login/JS engine is enabled.

### Legacy projection and pending processing

By default new/changed records queue an idempotent legacy projection and local lexical matching; each run attempts at most 100 pending projections. Legacy title/location filters still apply and report filtered records separately. To keep a qualification run SQLite-only use `--no-legacy-projection`. Local matching is not cloud evaluation, submission, or proof of legal eligibility.

`run_scan.py` and `run_all.py --scan-only` remain supported. Partial scanner success can still have legacy exit 0, so inspect its explicit errors/summary. Existing queue exports and UniversalAutoApplier contracts are unchanged.

## 4. Inspect state and results

```powershell
python run_local.py --db data/jobhunter.sqlite3 discovery-report
python run_local.py --db data/jobhunter.sqlite3 discovery-report --run-id RUN_ID
python run_local.py --db data/jobhunter.sqlite3 source-health
python run_local.py --db data/jobhunter.sqlite3 --profile-id default list
python run_local.py --db data/jobhunter.sqlite3 summary
```

`discovery-report` shows task status/reasons, generated requests and coverage cells, lead provenance, quality observations, counts, identity and processing. It persists across process restarts. Counts distinguish candidate URLs, recognized source leads, successfully collected sources and canonical insertions. None means useful unique opportunities by itself. Never publish raw reports, profile data, database contents or logs.

Repeated runs reuse compatible cursor/cache state and honor global provider gates. An hour-fresh completed snapshot is deferred; changed intent gets a new query signature. Native source snapshots can be reused while local matching refreshes for profile changes. A partial/deferred run is normal under a small budget, not permission to reset provider access. Unsupported leads stay unsupported until a reviewed method exists.

## 5. Optional integrations (not required)

Brave search needs an actual authorized account/key and explicit local access/cost approval. Set `BRAVE_SEARCH_API_KEY`, `JOBHUNTER_SEARCH_ACCESS_APPROVED=1` and `JOBHUNTER_SEARCH_COST_APPROVED=1` privately in the local environment, then add `--search-api`. Do not put keys in chat, source, reports or command examples. Without all required setup it fails explicitly rather than pretending a search ran. No live API validation was performed here.

The `structured_html` source method requires a reviewed HTTPS public start URL and explicit individual approval through the existing `source` command, followed by `scan SOURCE_ID`. It parses same-origin JSON-LD JobPosting pages subject to robots and strict budgets. Unknown-domain automatic recipe activation is not shipped. Most sites without suitable structured markup will be explicitly unsupported; an individual posting URL is not reusable source proof.

## 6. Reproduce controlled versus real qualification

```powershell
python -m pytest tests/test_scan_outcomes.py tests/test_runtime_queries.py tests/test_source_leads.py tests/test_discovery_processing.py tests/test_autonomy_acceptance.py tests/test_structured_source.py -q
python -m pytest -q
```

The first command is synthetic/controlled and replaces external providers. For an explicitly permitted **real** public test, use disposable private output outside the Git work tree:

```powershell
python qa/autonomy_discovery_live.py --live --provider indeed --output C:/JobHunterPrivate/qualification-1
python qa/autonomy_discovery_live.py --live --provider linkedin --state C:/JobHunterPrivate/qualification-1/synthetic.sqlite3 --output C:/JobHunterPrivate/qualification-2
```

The harness uses a synthetic profile, two adapter attempts, a 60-second dispatch budget and 120-second child timeout, no paid API and no automatic new ATS approval. Reuse state to preserve gates. Inspect `qualification.json`, `run.json` and actual task outcomes privately: process success is **not** new-source discovery success. A real A03/A05 pass requires observed acquisition evidence, an initially absent recognized source, lawful approval, actual native retrieval, valid intake and downstream evidence—not merely another URL or a mocked employer.

## Dashboard integration update

The dashboard now exposes **Search from my profile** to queue the same finite intent-driven runner on its existing worker. **Check due sources** remains the ordinary source refresh action. Expand **Source status & coverage** for persisted search attempts, safe source diagnostics and the `dashboard-discovery-bridge-1` runtime identifier. Update and restart the actual Python server; a GitHub push does not upgrade a running instance. See `DASHBOARD_SEARCH_FIX.md` for verification limits and Windows/existing-Codespace update steps.
