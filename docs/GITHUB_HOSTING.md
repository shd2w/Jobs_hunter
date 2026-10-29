# GitHub launch and private backend

## Two different services

GitHub Pages publishes only `site/`, a public launch/instructions page. The dashboard needs a live Python process and a private SQLite database. The launch page links to GitHub Codespaces as an optional way to run that process. It does not start or bill a workspace by itself.

1. Sign in to GitHub and open the repository's Codespaces link.
2. Review your GitHub plan, included usage and possible compute/storage charges before creating a workspace.
3. Wait for the devcontainer setup and dashboard startup.
4. Public starter feeds now scan automatically without profile/source entry. Open port 8765 from the **Ports** panel. Keep visibility **Private**. Do not change it to Public or Organization.
5. Close/stop the Codespace when finished. Deleting the workspace can delete private files; back them up first.

The app does not provide its own account authentication. Private Codespaces access is the access boundary. Do not publish the backend on an unrestricted network interface, reverse proxy or shared deployment.

## Setup and troubleshooting

The container installs `requirements-scanners.lock`. `.devcontainer/start.sh` runs `python run_local.py serve --port 8765`, writes a PID and log under ignored `data/`, and keeps the Python server bound to loopback. Start it again with:

```sh
bash .devcontainer/start.sh
```

To load a new release in an existing Codespace, update and restart (reloading the browser alone does not load Python changes):

```sh
git pull --ff-only
python -m pip install -r requirements-scanners.lock
bash .devcontainer/start.sh --restart
```

Preserve local edits if Git refuses the update. Restart verifies the saved PID belongs to the dashboard before stopping it; an unrelated process is never killed. Existing private data and saved pause choices are retained.

If startup fails, inspect `data/dashboard.log` privately. If a stale PID file prevents a restart, first verify the dashboard is stopped, then remove `data/dashboard.pid` and retry. Do not post private logs or database files in public issues.

If dependencies failed to install:

```sh
python -m pip install -r requirements-scanners.lock
```

An HTTP 403 in the forwarded browser can indicate that the Codespaces hostname does not match the environment. Supported forwarding requires `CODESPACES=true`, a valid `CODESPACE_NAME`, and `GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN=app.github.dev`. Do not weaken the Host/Origin checks or expose the port to solve it. Open the port from the current workspace rather than reusing another workspace's URL.

## Host and request boundaries

Ordinary local operation still allows loopback hosts only. In an identified Codespace, the app additionally accepts the one exact computed `CODESPACE_NAME-PORT.app.github.dev` hostname, and HTTPS origins for that hostname. Other hosts, suffix lookalikes and forwarded-header substitutions are not accepted. Existing CSRF, content-type, payload limits and browser headers remain in place. This allowlist is **not authentication**.

Automated tests simulate those headers on a local loopback server. They do not prove GitHub's actual proxy behavior, remote startup, account access, data persistence or billing. Until explicitly tested in a newly created Codespace, remote runtime validation is pending.

## Pages deployment

`.github/workflows/pages.yml` deploys `site/` only. The workflow needs repository Pages/Actions permissions. If automatic enablement is denied, a repository administrator must enable Pages with **GitHub Actions** as its source in repository Settings → Pages, then rerun the workflow. Do not use the repository root or upload private files as the Pages artifact.

The expected launch URL for this repository is `https://shd2w.github.io/Jobs_hunter/`. Only a successful deployment and an HTTP check establish that it is live; a committed workflow alone does not.

## Privacy and persistence

A Codespace is a remote GitHub-hosted development machine, not local-only storage. Your ignored private data can still exist on that machine. Avoid entering credentials or personal evidence in public previews. Back up the SQLite workspace, original CV and preparation folders privately. Database-only backups do not necessarily include pack folders. Never rely on `.gitignore` to remove material already tracked in Git.

Use a secure GitHub connection for publication. An exposed personal access token should be revoked; it is neither required nor bundled here.
