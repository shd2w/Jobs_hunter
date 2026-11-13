---
operation: "add_dependency_or_external_service"
task_id: "WP-00-01"
approved_by: "owner (JobHunter repository owner), chat message"
owner_message_ref: "2026-11-13, owner chat message (OpenCode session, WP-00-01), verbatim: '1. tldextract (PCD-018): APPROVED. I authorize adding tldextract as a project dependency for registered-domain extraction and future company-domain normalization.' Owner requirements attached: assign it to the appropriate dependency group; ensure its Public Suffix List behavior is understood and documented; preserve reproducibility and avoid uncontrolled runtime updates to suffix data; record this approval against PCD-018."
scope: "WP-00-01 only: adding tldextract (offline Public Suffix List mode) to the appropriate dependency group in pyproject.toml and the lock files, plus documentation of the PSL behaviour and of the no-runtime-update policy. No other dependency may be added under this approval; new packages beyond DEC-013 and this approval remain forbidden (GOV-02 section 4.2, WP-00-01 non-scope)."
---

# Approval record - add_dependency_or_external_service (WP-00-01)

- **What was approved:** adding `tldextract` as a project dependency (registered-domain extraction; future company-domain normalisation).
- **When:** 2026-11-13, owner chat message (quoted verbatim in the front matter `owner_message_ref`).
- **Relation to PCD-018:** GOV-02 section 3 lists PCD-018 as non-blocking with interim default "assumed accepted". This owner message is an explicit approval and is stronger than the interim default; it does not amend GOV-02 (implementers never edit it). `MEMORY/CURRENT_TASK.md` retains the required "PCD impact" line for the start check.
- **Implementation conditions set by the owner:**
  1. tldextract is assigned to the appropriate dependency group (proposal: `ingestion`; consumers are company-entity resolution and URL normalisation, phases 05-06).
  2. Public Suffix List behaviour is understood and documented in the install notes.
  3. Reproducibility is preserved and uncontrolled runtime updates to suffix data are avoided (offline mode; no network fetch of the PSL at runtime).
  4. This approval is recorded against PCD-018 (this file).
- **Related records:** owner decision record of 2026-11-13 (`.ai-engineering/MEMORY/decisions/WP-00-01_owner_decision_record_2026-11-13.md`) — decision 2 re-affirms this approval and requires the complete package-to-group mapping to be presented for confirmation before locks are generated; decision 5 approves pydantic-xml for locking now (it is inside the DEC-013 stack, so no separate approval record is required for it).
- **Authenticity note (KI-009):** this record was written by the implementer agent from the owner's chat message. The independent reviewer must confirm it against the owner's actual message before treating the approval as authentic.
