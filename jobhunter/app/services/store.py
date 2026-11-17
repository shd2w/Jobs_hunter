"""Store service — schema migrations over the SQLite adapter (WP-03-01)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from jobhunter.adapters import store
from jobhunter.app.result import Err, Ok, Result


class StoreService:
    """Applies additive schema migrations with automatic backups (DEC-046)."""

    def __init__(
        self,
        db_path: str | Path = store.DEFAULT_DB_PATH,
        backups_dir: str | Path | None = None,
    ):
        self.db_path = Path(db_path)
        self.backups_dir = (
            Path(backups_dir) if backups_dir is not None else self.db_path.parent / "backups"
        )

    def apply_migrations(self) -> Result[dict]:
        """Apply pending migrations.

        Returns Ok(report) with keys: applied (versions), skipped (versions),
        schema_version, backups (version -> backup path). Returns Err on any
        database failure; the failed migration rolls back completely.
        """
        try:
            report = store.apply_migrations(self.db_path, self.backups_dir)
        except sqlite3.Error as exc:
            return Err(error=f"migration failed: {exc}", code="store_migration_failed")
        except OSError as exc:
            return Err(error=f"backup/write failed: {exc}", code="store_backup_failed")
        return Ok(report)

    def schema_version(self) -> Result[int]:
        """Return the applied schema version (PRAGMA user_version)."""
        try:
            conn = store.connect(self.db_path)
        except sqlite3.Error as exc:
            return Err(error=f"cannot open database: {exc}", code="store_open_failed")
        try:
            return Ok(store.schema_version(conn))
        except sqlite3.Error as exc:
            return Err(error=f"cannot read schema version: {exc}", code="store_version_failed")
        finally:
            conn.close()
