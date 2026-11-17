"""Tests for the SQLite store schema and migration runner (WP-03-01).

Covers the WP exit criterion ("Schema applies on empty and legacy fixtures"),
migration idempotence, automatic backup creation (DEC-046), the DEC-036
tenancy rule (user_id on every per-user table from the first migration) and
failure rollback.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from jobhunter.adapters import store
from jobhunter.app.result import is_err, is_ok
from jobhunter.app.services.store import StoreService

EXPECTED_TABLES = store.PER_USER_TABLES | store.GLOBAL_TABLES


def _table_names(db_path):
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        return {row[0] for row in rows}
    finally:
        conn.close()


def _columns(db_path, table):
    conn = sqlite3.connect(db_path)
    try:
        return [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    finally:
        conn.close()


def test_schema_applies_on_empty_fixture(tmp_path):
    """Exit criterion: the schema applies on an empty fixture."""
    service = StoreService(db_path=tmp_path / "jobhunter.db", backups_dir=tmp_path / "backups")
    result = service.apply_migrations()
    assert is_ok(result)
    report = result.value
    assert report["applied"] == [1]
    assert report["schema_version"] == 1
    # every designed table exists, nothing extra
    assert _table_names(tmp_path / "jobhunter.db") == EXPECTED_TABLES


def test_all_expected_tables_created(tmp_path):
    """Each per-user and global table of the R1 schema exists after migration 1."""
    db = tmp_path / "jobhunter.db"
    StoreService(db_path=db, backups_dir=tmp_path / "backups").apply_migrations()
    names = _table_names(db)
    for table in EXPECTED_TABLES:
        assert table in names, f"missing table: {table}"


def test_user_id_on_per_user_tables(tmp_path):
    """DEC-036: user_id TEXT NOT NULL on every per-user table from migration 1."""
    db = tmp_path / "jobhunter.db"
    StoreService(db_path=db, backups_dir=tmp_path / "backups").apply_migrations()
    for table in store.PER_USER_TABLES:
        columns = _columns(db, table)
        assert "user_id" in columns, f"per-user table {table} lacks user_id"
        # NOT NULL check via table_info not-null flag (index 3)
        info = [row for row in sqlite3.connect(db).execute(f"PRAGMA table_info({table})")]
        user_id_row = next(row for row in info if row[1] == "user_id")
        assert user_id_row[3] == 1, f"user_id in {table} is not NOT NULL"


def test_no_user_id_on_global_tables(tmp_path):
    """DEC-036: shared/global tables carry no user_id column."""
    db = tmp_path / "jobhunter.db"
    StoreService(db_path=db, backups_dir=tmp_path / "backups").apply_migrations()
    for table in store.GLOBAL_TABLES:
        assert "user_id" not in _columns(db, table), f"global table {table} must not have user_id"


def test_migration_idempotence_on_empty_fixture(tmp_path):
    """T (WP evidence): running the runner twice is a no-op the second time."""
    db = tmp_path / "jobhunter.db"
    service = StoreService(db_path=db, backups_dir=tmp_path / "backups")
    first = service.apply_migrations()
    assert is_ok(first) and first.value["applied"] == [1]

    # data written between runs must survive and not be touched
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            "INSERT INTO saved_search(user_id, id, name, filters_json, created_at) "
            "VALUES ('u1', 1, 'n', '{}', '2026-11-17T00:00:00Z')"
        )
        conn.commit()
    finally:
        conn.close()

    second = service.apply_migrations()
    assert is_ok(second)
    assert second.value["applied"] == []
    assert second.value["skipped"] == [1]
    assert second.value["schema_version"] == 1
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute("SELECT user_id, name FROM saved_search").fetchall()
        assert rows == [("u1", "n")]
    finally:
        conn.close()


def test_schema_applies_on_legacy_fixture(tmp_path):
    """Exit criterion: the schema applies on a legacy fixture (existing DB,
    user_version 0, pre-existing data). Migration is additive."""
    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(db)
    try:
        conn.execute("CREATE TABLE legacy_note(id INTEGER PRIMARY KEY, text TEXT NOT NULL)")
        conn.execute("INSERT INTO legacy_note(text) VALUES ('keep me')")
        conn.commit()
    finally:
        conn.close()

    service = StoreService(db_path=db, backups_dir=tmp_path / "backups")
    result = service.apply_migrations()
    assert is_ok(result)
    assert result.value["applied"] == [1]
    # one backup was created because the file existed before migration 1
    assert len(result.value["backups"]) == 1

    names = _table_names(db)
    assert "legacy_note" in names  # additive: nothing destroyed
    assert EXPECTED_TABLES <= names
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute("SELECT text FROM legacy_note").fetchall()
        assert rows == [("keep me",)]
    finally:
        conn.close()


def test_backup_file_created_and_valid(tmp_path):
    """E (WP evidence): a backup file is created before the migration and is a
    valid database containing the pre-migration data."""
    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(db)
    try:
        conn.execute("CREATE TABLE legacy_note(id INTEGER PRIMARY KEY, text TEXT NOT NULL)")
        conn.execute("INSERT INTO legacy_note(text) VALUES ('precious')")
        conn.commit()
    finally:
        conn.close()

    service = StoreService(db_path=db, backups_dir=tmp_path / "backups")
    result = service.apply_migrations()
    assert is_ok(result)
    recorded = result.value["backups"]["1"]
    assert recorded, "expected a recorded backup path"
    assert Path(recorded).exists(), "recorded backup file exists on disk"
    # the recorded path is a readable SQLite file with the legacy row
    bconn = sqlite3.connect(recorded)
    try:
        rows = bconn.execute("SELECT text FROM legacy_note").fetchall()
        assert rows == [("precious",)]
    finally:
        bconn.close()


def test_no_backup_on_first_creation(tmp_path):
    """An empty (nonexistent) database has nothing to back up: no backup entry."""
    service = StoreService(db_path=tmp_path / "fresh.db", backups_dir=tmp_path / "backups")
    result = service.apply_migrations()
    assert is_ok(result)
    assert result.value["backups"] == {}
    assert not (tmp_path / "backups").exists() or not any((tmp_path / "backups").iterdir())


def test_failed_migration_rolls_back(tmp_path):
    """A failing migration rolls back completely; user_version stays 0 and no
    partial schema is left behind."""
    db = tmp_path / "conflict.db"
    conn = sqlite3.connect(db)
    try:
        # a conflicting object makes migration 1's CREATE TABLE source fail
        conn.execute("CREATE TABLE source(id TEXT PRIMARY KEY, extra TEXT)")
        conn.commit()
    finally:
        conn.close()

    service = StoreService(db_path=db, backups_dir=tmp_path / "backups")
    result = service.apply_migrations()
    assert is_err(result)
    assert result.error  # non-empty message
    assert result.code == "store_migration_failed"

    # version unchanged; no partial tables from migration 1
    version = service.schema_version()
    assert is_ok(version) and version.value == 0
    names = _table_names(db)
    assert "source" in names  # the pre-existing table is untouched
    assert "job" not in names
    assert "saved_search" not in names


def test_service_schema_version_before_any_migration(tmp_path):
    """A fresh, nonexistent database reports schema version 0."""
    service = StoreService(db_path=tmp_path / "none.db", backups_dir=tmp_path / "backups")
    result = service.schema_version()
    assert is_ok(result) and result.value == 0


def test_runner_reports_pending_migrations(tmp_path):
    """pending_migrations lists only migrations newer than the applied version."""
    db = tmp_path / "jobhunter.db"
    conn = store.connect(db)
    try:
        assert [m.version for m in store.pending_migrations(conn)] == [1]
        conn.close()

        StoreService(db_path=db, backups_dir=tmp_path / "backups").apply_migrations()

        conn = store.connect(db)
        assert store.pending_migrations(conn) == []
    finally:
        conn.close()


def test_backup_write_is_atomic_no_temp_leftover(tmp_path):
    """DEC-046 atomic backup: no leftover .tmp files after a successful run."""
    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(db)
    try:
        conn.execute("CREATE TABLE t(x)")
        conn.commit()
    finally:
        conn.close()
    store.backup_database(db, tmp_path / "backups", label="pre-migration-0001")
    leftovers = [p.name for p in (tmp_path / "backups").iterdir() if p.name.endswith(".tmp")]
    assert leftovers == []
