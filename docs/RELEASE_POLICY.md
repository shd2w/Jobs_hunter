# Release policy

For work on JobHunter, publish verified source updates to **shd2w/Jobs_hunter**, preserving existing repository history. Keep the project openable through the GitHub Pages launch page and a private Codespaces configuration. This records the project owner's requested release workflow; it does not imply automatic background publication.

Before each push:

1. Inspect the diff and run relevant tests plus the full suite when practical. Report skipped or failed validation accurately.
2. Stage source, synthetic tests and reviewed documentation only. Never publish personal profiles, credentials, CVs, databases, logs, reports, preparation packs or private delivery archives.
3. Preserve Host/Origin/CSRF protections and private forwarded-port access. Never interpret launchability as permission for an unauthenticated public backend.
4. Push using the connected GitHub integration, not a token copied from chat. Do not overwrite unrelated user changes or force-push history.
5. Check Actions/Pages results and the deployed page when access permits. Distinguish source pushed, static page deployed, and full Python runtime verified.
6. Do not start billable infrastructure or a Codespace without explicit permission. A public launcher may offer the user that choice with cost/privacy disclosure.

The present baseline is 0.4.0 automatic-first discovery with GitHub launch support. See `docs/AUTOMATIC_DISCOVERY.md` for the zero-input workflow and bounded live validation. Integrated synthetic preparation/learning acceptance is covered by `docs/PHASE6_ACCEPTANCE.md`; remote runtime and representative-environment checks remain open. Optional AI/real-model checks are deferred rather than completed. Unverified live providers, Windows and representative performance must not be described as passed.
