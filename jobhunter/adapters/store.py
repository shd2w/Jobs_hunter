"""SQLite store adapter — R1 schema and migration runner (WP-03-01).

Implements:
- DEC-046: migrations are additive; an automatic backup precedes each; backup
  writes are atomic (sqlite3 backup API to a temp file, then os.replace).
- DEC-036: user_id is present on every per-user table from the first migration.
  Global (shared) tables carry no user_id.

Schema source (docs/04_DATA_AND_INTEGRATION_DESIGN.md):
- s4  base DDL (principal entities)
- s10 Revision 1 additions — authoritative where it differs (tenancy: user_id
  on every per-user table from migration 0001; job/source/company additions;
  job_version, job_salary, job_eligibility, profile_* child tables, company,
  job_feedback, import_item, scheduler_lease, source_http_cache)
- s11 Revision 2-3 additions — authoritative where they differ (company
  columns, company_candidate, domain_probe, source_scope_state, cohort_metric,
  job seniority/language columns)

Version tracking: PRAGMA user_version. Migrations are additive; a failing
migration rolls back completely and leaves user_version unchanged.
"""

from __future__ import annotations

import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

LATEST_SCHEMA_VERSION = 1

DEFAULT_DB_PATH = "data/jobhunter.db"
DEFAULT_BACKUPS_DIR = "data/backups"

# Tables that carry user_id TEXT NOT NULL per DEC-036 / doc 04 s10 (tenancy
# list; profile and profile_version child tables are keyed by version_id and
# inherit tenancy through the future profile_version foreign key, so they are
# not in this list).
PER_USER_TABLES = frozenset({
    "job_match", "job_evaluation", "skill_gap", "learning_reco",
    "application", "application_event", "notification", "ai_call",
    "ai_key_state", "saved_search", "job_feedback", "import_item",
    "audit_event", "job_eligibility_verdict",
})

# Shared/global tables that must not carry user_id (doc 04 s10 tenancy list).
GLOBAL_TABLES = frozenset({
    "source", "source_run", "source_item_state", "source_http_cache",
    "raw_job", "job", "job_sighting", "job_link", "job_version",
    "job_salary", "job_eligibility", "company", "company_candidate",
    "scheduler_lease", "domain_probe", "source_scope_state",
    "cohort_metric",
    # profile-version children (s10): tenancy via profile_version FK.
    "profile_work_authorization", "profile_nationality",
    "profile_relocation_plan", "profile_remote_constraints",
})


@dataclass(frozen=True)
class Migration:
    """One additive migration: version number and ordered SQL statements."""

    version: int
    statements: tuple[str, ...]


# R1 schema (doc 04 s4 as amended by s10 and s11) in one additive migration.
MIGRATION_0001_R1_SCHEMA = (
    # --- sources (s4; s10 adds redistribution/cadence; s11 adds run metrics) ---
    """CREATE TABLE source(
  id TEXT PRIMARY KEY, kind TEXT NOT NULL,
  provider TEXT NOT NULL, identifier TEXT,
  config_json TEXT NOT NULL DEFAULT '{}',
  access_basis TEXT NOT NULL,
  policy TEXT NOT NULL DEFAULT 'review',
  authorized INTEGER NOT NULL DEFAULT 0,
  state TEXT NOT NULL DEFAULT 'proposed',
  enabled INTEGER NOT NULL DEFAULT 0,
  rate_json TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  redistribution TEXT NOT NULL DEFAULT 'personal_only',
  cadence_seconds INTEGER,
  UNIQUE(provider, identifier))""",
    """CREATE TABLE source_run(
  id INTEGER PRIMARY KEY, source_id TEXT NOT NULL REFERENCES source(id),
  started_at TEXT NOT NULL, finished_at TEXT, status TEXT NOT NULL,
  coverage TEXT NOT NULL DEFAULT 'unknown',
  fetched INTEGER DEFAULT 0, new_jobs INTEGER DEFAULT 0,
  updated INTEGER DEFAULT 0, requests INTEGER DEFAULT 0,
  http_status_json TEXT, errors_json TEXT, warnings_json TEXT,
  metrics_json TEXT, guard_note TEXT)""",
    """CREATE TABLE source_item_state(
  source_id TEXT NOT NULL REFERENCES source(id), external_id TEXT NOT NULL,
  summary_hash TEXT NOT NULL, detail_fetched_at TEXT, last_seen_run INTEGER,
  PRIMARY KEY(source_id, external_id))""",
    """CREATE TABLE raw_job(
  id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL REFERENCES source_run(id),
  source_id TEXT NOT NULL, external_id TEXT, payload_json TEXT NOT NULL,
  fetched_at TEXT NOT NULL)""",
    # --- jobs (s4; s10 adds visibility/hidden/seniority/role_family; s11 adds
    #     seniority_hint/seniority_evidence/language_unknown) ---
    """CREATE TABLE job(
  id TEXT PRIMARY KEY,
  global_id TEXT NOT NULL UNIQUE, canonical_url TEXT NOT NULL, title TEXT NOT NULL,
  company TEXT NOT NULL, company_norm TEXT NOT NULL, requisition_id TEXT,
  location TEXT, country_iso TEXT, is_remote INTEGER, employment_type TEXT,
  salary_min REAL, salary_max REAL, salary_currency TEXT, posted_at TEXT,
  description TEXT, description_hash TEXT, language TEXT, job_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'new',
  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, closed_at TEXT,
  miss_count INTEGER NOT NULL DEFAULT 0,
  visibility TEXT NOT NULL DEFAULT 'visible',
  hidden_reason TEXT,
  seniority_level TEXT,
  role_family TEXT,
  seniority_hint TEXT,
  seniority_evidence_json TEXT,
  language_unknown INTEGER NOT NULL DEFAULT 0)""",
    "CREATE INDEX job_status_seen ON job(status, last_seen DESC)",
    "CREATE INDEX job_company_req ON job(company_norm, requisition_id)",
    "CREATE INDEX job_desc_hash ON job(description_hash)",
    """CREATE TABLE job_sighting(
  job_id TEXT NOT NULL REFERENCES job(id),
  source_id TEXT NOT NULL REFERENCES source(id),
  run_id INTEGER REFERENCES source_run(id), url TEXT NOT NULL,
  matched_search_term TEXT, attribution TEXT,
  first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
  PRIMARY KEY(job_id, source_id, url))""",
    """CREATE TABLE job_link(
  a_job_id TEXT NOT NULL REFERENCES job(id), b_job_id TEXT NOT NULL REFERENCES job(id),
  kind TEXT NOT NULL,
  stage INTEGER NOT NULL, score REAL, status TEXT NOT NULL DEFAULT 'proposed',
  decided_by TEXT, created_at TEXT NOT NULL,
  PRIMARY KEY(a_job_id, b_job_id, kind))""",
    # --- job history / eligibility (s10; global) ---
    """CREATE TABLE job_version(
  job_id TEXT NOT NULL REFERENCES job(id), version INTEGER NOT NULL,
  content_hash TEXT NOT NULL, fields_json TEXT NOT NULL, run_id INTEGER,
  seen_at TEXT NOT NULL, PRIMARY KEY(job_id, version))""",
    """CREATE TABLE job_salary(
  job_id TEXT PRIMARY KEY REFERENCES job(id), min REAL, max REAL, currency TEXT,
  period TEXT, basis TEXT, tax_note TEXT, raw_text TEXT, origin TEXT NOT NULL,
  confidence REAL)""",
    """CREATE TABLE job_eligibility(
  job_id TEXT PRIMARY KEY REFERENCES job(id), location_restriction_json TEXT,
  nationality_restriction_json TEXT, work_auth_required TEXT, sponsorship TEXT,
  relocation_support TEXT, work_mode TEXT, onsite_days INTEGER,
  clearance_required INTEGER, timezone_requirement TEXT,
  evidence_json TEXT NOT NULL, extractor TEXT NOT NULL, extracted_at TEXT NOT NULL)""",
    """CREATE TABLE job_eligibility_verdict(
  user_id TEXT NOT NULL, job_id TEXT NOT NULL REFERENCES job(id),
  profile_version_id INTEGER NOT NULL,
  status TEXT NOT NULL, reasons_json TEXT NOT NULL, computed_at TEXT NOT NULL,
  PRIMARY KEY(user_id, job_id, profile_version_id))""",
    # --- matching / evaluation (s4 + s10 tenancy: user_id NOT NULL) ---
    """CREATE TABLE job_match(
  user_id TEXT NOT NULL, job_id TEXT NOT NULL REFERENCES job(id),
  profile_version_id INTEGER NOT NULL,
  match_score REAL, score_1_5 REAL, confidence REAL, signals_json TEXT NOT NULL,
  missing_critical_json TEXT, weights_json TEXT NOT NULL,
  stale INTEGER NOT NULL DEFAULT 0, computed_at TEXT NOT NULL,
  PRIMARY KEY(job_id, profile_version_id))""",
    """CREATE TABLE job_evaluation(
  user_id TEXT NOT NULL, id INTEGER PRIMARY KEY,
  job_id TEXT NOT NULL REFERENCES job(id),
  status TEXT NOT NULL,
  requirements_json TEXT, rationale TEXT, recommendation TEXT, model TEXT,
  prompt_version TEXT, ai_call_id INTEGER, failure_reason TEXT,
  created_at TEXT NOT NULL)""",
    """CREATE TABLE skill_gap(
  user_id TEXT NOT NULL, job_id TEXT NOT NULL, profile_version_id INTEGER NOT NULL,
  skill TEXT NOT NULL, required INTEGER NOT NULL, state TEXT NOT NULL,
  needed_level TEXT, PRIMARY KEY(job_id, profile_version_id, skill))""",
    """CREATE TABLE learning_reco(
  user_id TEXT NOT NULL, id INTEGER PRIMARY KEY, skill TEXT NOT NULL,
  resource_json TEXT NOT NULL, source TEXT NOT NULL, status TEXT DEFAULT 'suggested')""",
    # --- tracking / notifications / audit (s4 + s10 tenancy) ---
    """CREATE TABLE application(
  user_id TEXT NOT NULL, job_id TEXT PRIMARY KEY REFERENCES job(id),
  status TEXT NOT NULL, updated_at TEXT NOT NULL, note TEXT)""",
    """CREATE TABLE application_event(
  user_id TEXT NOT NULL, id INTEGER PRIMARY KEY,
  job_id TEXT NOT NULL REFERENCES job(id),
  from_status TEXT, to_status TEXT NOT NULL, note TEXT, at TEXT NOT NULL,
  audit_id INTEGER)""",
    """CREATE TABLE notification(
  user_id TEXT NOT NULL, id INTEGER PRIMARY KEY, channel TEXT NOT NULL,
  dedupe_key TEXT NOT NULL UNIQUE, event TEXT NOT NULL,
  payload_json TEXT NOT NULL, status TEXT NOT NULL, attempts INTEGER DEFAULT 0,
  created_at TEXT, sent_at TEXT)""",
    """CREATE TABLE ai_call(
  user_id TEXT NOT NULL, id INTEGER PRIMARY KEY, task TEXT NOT NULL,
  provider TEXT NOT NULL, model TEXT NOT NULL, key_alias TEXT,
  status TEXT NOT NULL, error_class TEXT, tokens_in INTEGER, tokens_out INTEGER,
  latency_ms INTEGER, cache_hit INTEGER DEFAULT 0, at TEXT NOT NULL)""",
    """CREATE TABLE ai_key_state(
  user_id TEXT NOT NULL, key_alias TEXT PRIMARY KEY, provider TEXT NOT NULL,
  cooldown_until TEXT, status TEXT NOT NULL)""",
    """CREATE TABLE audit_event(
  user_id TEXT NOT NULL, id INTEGER PRIMARY KEY, type TEXT NOT NULL,
  actor TEXT NOT NULL, details_json TEXT, at TEXT NOT NULL)""",
    """CREATE TABLE saved_search(
  user_id TEXT NOT NULL, id INTEGER PRIMARY KEY, name TEXT NOT NULL,
  filters_json TEXT NOT NULL, created_at TEXT NOT NULL)""",
    # --- company / discovery funnel (s10; s11 adds columns and tables) ---
    """CREATE TABLE company(
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, name_norm TEXT NOT NULL,
  aliases_json TEXT, domain TEXT, country_iso TEXT, careers_url TEXT,
  ats_provider TEXT, ats_identifier TEXT, source_id TEXT REFERENCES source(id),
  status TEXT NOT NULL DEFAULT 'candidate', discovered_via TEXT NOT NULL,
  first_seen TEXT NOT NULL, verified_at TEXT, last_ok_at TEXT,
  company_type TEXT NOT NULL DEFAULT 'unknown',
  registrable_domain TEXT,
  recognition_status TEXT,
  tier TEXT,
  value_score REAL,
  language_mix_json TEXT,
  next_probe_at TEXT,
  UNIQUE(ats_provider, ats_identifier))""",
    """CREATE TABLE company_candidate(
  id INTEGER PRIMARY KEY, kind TEXT NOT NULL,
  value TEXT NOT NULL, channel TEXT NOT NULL,
  discovered_via TEXT NOT NULL, first_seen TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'new', outcome TEXT, ttl_until TEXT,
  UNIQUE(kind, value, channel))""",
    """CREATE TABLE domain_probe(
  domain TEXT PRIMARY KEY, last_probed_at TEXT NOT NULL, outcome TEXT NOT NULL,
  ttl_until TEXT NOT NULL)""",
    # --- guard v2 / monitoring (s11) ---
    """CREATE TABLE source_scope_state(
  source_id TEXT NOT NULL REFERENCES source(id), scope_key TEXT NOT NULL,
  baseline_count REAL, baseline_updated_at TEXT, flagged_buffer_json TEXT,
  state TEXT NOT NULL DEFAULT 'normal',
  PRIMARY KEY(source_id, scope_key))""",
    """CREATE TABLE cohort_metric(
  provider TEXT NOT NULL, tier TEXT NOT NULL, day TEXT NOT NULL,
  jobs INTEGER NOT NULL, boards INTEGER NOT NULL,
  PRIMARY KEY(provider, tier, day))""",
    # --- feedback / import / scheduler / cache (s10) ---
    """CREATE TABLE job_feedback(
  id INTEGER PRIMARY KEY, user_id TEXT NOT NULL,
  job_id TEXT NOT NULL REFERENCES job(id), event TEXT NOT NULL,
  reason TEXT, at TEXT NOT NULL)""",
    """CREATE TABLE import_item(
  id INTEGER PRIMARY KEY, user_id TEXT NOT NULL, kind TEXT NOT NULL,
  raw_ref TEXT, status TEXT NOT NULL, job_id TEXT REFERENCES job(id),
  confidence REAL, created_at TEXT NOT NULL)""",
    """CREATE TABLE scheduler_lease(
  name TEXT PRIMARY KEY, holder TEXT NOT NULL, expires_at TEXT NOT NULL)""",
    """CREATE TABLE source_http_cache(
  source_id TEXT NOT NULL, url TEXT NOT NULL, etag TEXT, last_modified TEXT,
  fetched_at TEXT NOT NULL, PRIMARY KEY(source_id, url))""",
    # --- profile-version child tables (s10; tenancy via profile_version) ---
    """CREATE TABLE profile_work_authorization(
  version_id INTEGER NOT NULL, country_iso TEXT NOT NULL, status TEXT NOT NULL,
  valid_until TEXT, source TEXT NOT NULL,
  PRIMARY KEY(version_id, country_iso))""",
    """CREATE TABLE profile_nationality(
  version_id INTEGER NOT NULL, country_iso TEXT NOT NULL,
  PRIMARY KEY(version_id, country_iso))""",
    """CREATE TABLE profile_relocation_plan(
  version_id INTEGER PRIMARY KEY, willing TEXT NOT NULL, countries_json TEXT,
  earliest_start TEXT, needs_sponsorship INTEGER, needs_relocation_support INTEGER,
  notes TEXT)""",
    """CREATE TABLE profile_remote_constraints(
  version_id INTEGER PRIMARY KEY, home_country TEXT, tz_min_offset INTEGER,
  tz_max_offset INTEGER, remote_only INTEGER)""",
)

MIGRATIONS: tuple[Migration, ...] = (
    Migration(version=1, statements=MIGRATION_0001_R1_SCHEMA),
)


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open a connection with integrity and durability settings enabled."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def schema_version(conn: sqlite3.Connection) -> int:
    """Return the applied schema version (PRAGMA user_version)."""
    row = conn.execute("PRAGMA user_version").fetchone()
    return int(row[0]) if row else 0


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def backup_database(
    db_path: str | Path,
    backups_dir: str | Path = DEFAULT_BACKUPS_DIR,
    *,
    label: str = "pre-migration",
) -> Path:
    """Back up the database file atomically; return the backup path.

    DEC-046: automatic backup before each migration; atomic writes. The copy
    uses the sqlite3 backup API into a temp file in the target directory, then
    os.replace (atomic on the same filesystem).
    """
    source = Path(db_path)
    target_dir = Path(backups_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = _utc_timestamp()
    target = target_dir / f"{label}-{stamp}.db"
    tmp = target_dir / f".{target.name}.tmp"
    src_conn = sqlite3.connect(source)
    try:
        dst = sqlite3.connect(tmp)
        try:
            src_conn.backup(dst)
        finally:
            dst.close()
    finally:
        src_conn.close()
    tmp.replace(target)  # atomic rename
    return target


def pending_migrations(conn: sqlite3.Connection) -> list[Migration]:
    """Return migrations with a version newer than the applied schema version."""
    current = schema_version(conn)
    return [m for m in MIGRATIONS if m.version > current]


def apply_migrations(
    db_path: str | Path,
    backups_dir: str | Path = DEFAULT_BACKUPS_DIR,
) -> dict:
    """Apply all pending migrations additively; return an applied-report dict.

    - Idempotent: a second call on the same database applies nothing.
    - DEC-046: backs up the existing database file before each migration
      (no backup is possible before the first creation of an empty file).
    - Each migration runs inside one transaction; a failure rolls the whole
      migration back and leaves user_version unchanged.
    """
    path = Path(db_path)
    had_file = path.exists()
    report: dict = {"applied": [], "skipped": [], "backups": {}}
    conn = connect(path)
    try:
        for migration in pending_migrations(conn):
            backup_path = None
            if had_file:
                backup_path = backup_database(
                    path, backups_dir, label=f"pre-migration-{migration.version:04d}"
                )
            try:
                conn.execute("BEGIN IMMEDIATE")
                for statement in migration.statements:
                    conn.execute(statement)
                conn.execute(f"PRAGMA user_version = {migration.version}")
                conn.commit()
            except sqlite3.Error:
                conn.rollback()
                raise
            report["applied"].append(migration.version)
            if backup_path is not None:
                report["backups"][str(migration.version)] = str(backup_path)
            had_file = True
        current = schema_version(conn)
        for migration in MIGRATIONS:
            if migration.version <= current:
                report["skipped"].append(migration.version)
        report["schema_version"] = current
        return report
    finally:
        conn.close()
