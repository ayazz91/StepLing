"""Create and restore consistent SQLite backups."""

from __future__ import annotations

import argparse
import os
import sqlite3
import tempfile
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

from bot.config import PROJECT_ROOT

RETENTION_DAYS = 7
REQUIRED_TABLES = {"users", "messages", "vocabulary", "mistakes", "gemini_daily_usage"}


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
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    destination = backup_dir / f"tutor-{timestamp}.sqlite3"
    suffix = 1
    while True:
        try:
            descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(descriptor)
            break
        except FileExistsError:
            destination = backup_dir / f"tutor-{timestamp}-{suffix}.sqlite3"
            suffix += 1
    completed = False
    try:
        _write_snapshot(source, destination)
        completed = True
    finally:
        if not completed:
            destination.unlink(missing_ok=True)
    cutoff = datetime.now(UTC) - timedelta(days=RETENTION_DAYS)
    for old_backup in backup_dir.glob("tutor-*.sqlite3"):
        modified = datetime.fromtimestamp(old_backup.stat().st_mtime, UTC)
        if modified < cutoff:
            old_backup.unlink()
    return destination


def restore_backup(
    source: Path, destination: Path, safety_backup_dir: Path | None = None,
) -> Path | None:
    """Validate a snapshot, preserve the target, then replace it with the snapshot."""
    if not source.is_file():
        raise FileNotFoundError(f"Backup file does not exist: {source}")
    if source.resolve() == destination.resolve():
        raise ValueError("Backup source and destination must be different files")

    _validate_database(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    safety_backup = None
    if destination.is_file():
        backup_dir = safety_backup_dir or destination.parent / "backups"
        safety_backup = create_backup(destination, backup_dir)

    descriptor, staged_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".sqlite3", dir=destination.parent,
    )
    os.close(descriptor)
    staged = Path(staged_name)
    try:
        _write_snapshot(source, staged)
        _validate_database(staged)
        with closing(sqlite3.connect(staged)) as staged_db:
            with closing(sqlite3.connect(destination)) as destination_db:
                with destination_db:
                    staged_db.backup(destination_db)
        _validate_database(destination)
    finally:
        staged.unlink(missing_ok=True)
    return safety_backup


def _write_snapshot(source: Path, destination: Path) -> None:
    """Write a consistent SQLite snapshot to a new database file."""
    with closing(sqlite3.connect(source)) as source_db:
        with closing(sqlite3.connect(destination)) as destination_db:
            with destination_db:
                source_db.backup(destination_db)
    _check_integrity(destination)


def _validate_database(path: Path) -> None:
    """Reject corrupt or non-application SQLite files before restoring them."""
    _check_integrity(path)
    with closing(sqlite3.connect(path)) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    missing_tables = sorted(REQUIRED_TABLES - tables)
    if missing_tables:
        raise sqlite3.DatabaseError(
            f"Backup is missing required tables: {', '.join(missing_tables)}"
        )


def _check_integrity(path: Path) -> None:
    """Raise when SQLite reports corruption in a database file."""
    with closing(sqlite3.connect(path)) as connection:
        result = connection.execute("PRAGMA integrity_check").fetchall()
    if not result or any(row[0] != "ok" for row in result):
        raise sqlite3.DatabaseError(f"Backup integrity check failed: {result}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restore", type=Path, help="restore this backup into the configured database")
    args = parser.parse_args()
    database = _database_path()
    if args.restore:
        safety_backup = restore_backup(args.restore, database, _backup_dir())
        print(f"Restored {args.restore} to {database}")
        if safety_backup is not None:
            print(f"Previous database saved as: {safety_backup}")
    else:
        print(f"Created backup: {create_backup(database, _backup_dir())}")


if __name__ == "__main__":
    main()
