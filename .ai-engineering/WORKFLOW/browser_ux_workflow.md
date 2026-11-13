# Browser / UX evidence workflow (spec 11.1, roadmap Phase D)

Applies when a task changes the UI (`CONFIG/project_profile.yml` `ui.applicable: true`).

## Status of tooling
No browser-automation tool is approved for JobHunter (`ui.browser_automation: unavailable`), and the viewport sizes and workflows are `pending_owner`. Until the owner sets them, UI gates are **unavailable**, not passed, and `record-ui` refuses any tool except `--tool manual`. An agent must not approve a tool for itself: the owner edits `ui.browser_automation` (for example to the name of the tool they accept) and the viewports.

## Procedure
1. Start the real app with `command_profiles.yml` `app_start`; record health with `health_check`.
2. For each approved viewport and each affected workflow, perform the workflow against the real app with the approved tool (or manually).
3. Save a screenshot and, if available, the browser console log.
4. Record it: `python .ai-engineering/SCRIPTS/validation/run_gates.py record-ui --task WP-pp-nn --viewport 390x844 --image <png> --workflow <name> --result passed|failed --tool <approved-tool|manual> [--console-log <file>]`
   The record is labelled `screenshot-evidence`, gets gate id `UI-<viewport>`, and the image is copied under `EVIDENCE/<task>/browser/`.
5. `--result` is your judgement after inspecting the screenshot and console. A screenshot proves the state shown, nothing more. Console errors or a broken layout are `failed`.
6. Include every viewport the project defines. A missing viewport is a missing gate, not an implied pass (`close-check --require UI-1920x1080,UI-820x1180,UI-390x844`).

## Never
- Treat a design mock, prototype or synthetic demo as UI evidence (`Designer-written`, `Prototype`, `Demo` are not live; see the label mapping in `project_contract_map.yml`).
- Put S3/S4 data (CV text, contact details, credentials) on screen in a screenshot: use fixtures or redact before recording.
