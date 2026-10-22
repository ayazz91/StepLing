"""Create and restore consistent SQLite backups."""

from __future__ import annotations

import argparse
import os
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

from bot.config import PROJECT_ROOT

RETENTION_DAYS = 7


def _database_path() -> Path:
    load_dotenv(PROJECT_ROOT / ".env")
    path = Path(os.environ.get("DATABASE_PATH", "data/tutor.sqlite3"))
    return path if path.is_absolute() else PROJECT_ROOT / path


def _backup_dir() -> Path:
    path = Path(os.environ.get("BACKUP_PATH", str(PROJECT_ROOT / "backups")))
    return path if path.is_absolute() else PROJECT_ROOT / path


def create_backup(source: Path, backup_dir: Path) -> Path:
    """Write a transactionally consistent SQLite snapshot and prune old copies."""
    if not source.is_file():
        raise FileNotFoundError(f"Database file does not exist: {source}")
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    destination = backup_dir / f"tutor-{timestamp}.sqlite3"
    with closing(sqlite3.connect(source)) as live_db:
        with closing(sqlite3.connect(destination)) as backup_db:
            with backup_db:
                live_db.backup(backup_db)
                result = backup_db.execute("PRAGMA integrity_check").fetchone()
                if result is None or result[0] != "ok":
                    destination.unlink(missing_ok=True)
                    raise sqlite3.DatabaseError(f"Backup integrity check failed: {result}")
    cutoff = datetime.now(UTC) - timedelta(days=RETENTION_DAYS)
    for old_backup in backup_dir.glob("tutor-*.sqlite3"):
        modified = datetime.fromtimestamp(old_backup.stat().st_mtime, UTC)
        if modified < cutoff:
            old_backup.unlink()
    return destination


def restore_backup(source: Path, destination: Path) -> None:
    """Validate a snapshot and replace the target database with its contents."""
    if not source.is_file():
        raise FileNotFoundError(f"Backup file does not exist: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(source)) as backup_db:
        backup_db.execute("PRAGMA query_only = ON")
        result = backup_db.execute("PRAGMA integrity_check").fetchone()
        if result is None or result[0] != "ok":
            raise sqlite3.DatabaseError(f"Backup integrity check failed: {result}")
        with closing(sqlite3.connect(destination)) as live_db:
            with live_db:
                backup_db.backup(live_db)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restore", type=Path, help="restore this backup into the configured database")
    args = parser.parse_args()
    database = _database_path()
    if args.restore:
        restore_backup(args.restore, database)
        print(f"Restored {args.restore} to {database}")
    else:
        print(f"Created backup: {create_backup(database, _backup_dir())}")


if __name__ == "__main__":
    main()
