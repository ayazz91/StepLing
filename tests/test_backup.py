import sqlite3
from pathlib import Path

import pytest

from bot.backup import create_backup, restore_backup
from bot.db.database import SCHEMA


def _create_database(path: Path, note: str) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript(SCHEMA)
        connection.execute("CREATE TABLE IF NOT EXISTS notes (value TEXT)")
        connection.execute("DELETE FROM notes")
        connection.execute("INSERT INTO notes VALUES (?)", (note,))


def test_backup_is_consistent_and_can_be_restored(tmp_path: Path) -> None:
    database = tmp_path / "live.sqlite3"
    backup_dir = tmp_path / "backups"
    _create_database(database, "saved")

    backup = create_backup(database, backup_dir)
    _create_database(database, "changed")
    safety_backup = restore_backup(backup, database, backup_dir)

    assert safety_backup is not None
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT value FROM notes").fetchone() == ("saved",)
    with sqlite3.connect(safety_backup) as connection:
        assert connection.execute("SELECT value FROM notes").fetchone() == ("changed",)


def test_restore_rejects_invalid_backup_without_overwriting_database(tmp_path: Path) -> None:
    database = tmp_path / "live.sqlite3"
    invalid_backup = tmp_path / "invalid.sqlite3"
    _create_database(database, "preserved")
    invalid_backup.write_text("not a sqlite database", encoding="utf-8")

    with pytest.raises(sqlite3.DatabaseError):
        restore_backup(invalid_backup, database)

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT value FROM notes").fetchone() == ("preserved",)


def test_restore_rejects_valid_sqlite_file_without_application_schema(
    tmp_path: Path,
) -> None:
    database = tmp_path / "live.sqlite3"
    invalid_backup = tmp_path / "incompatible.sqlite3"
    _create_database(database, "preserved")
    with sqlite3.connect(invalid_backup) as connection:
        connection.execute("CREATE TABLE unrelated (value TEXT)")

    with pytest.raises(sqlite3.DatabaseError, match="missing required tables"):
        restore_backup(invalid_backup, database)

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT value FROM notes").fetchone() == ("preserved",)


def test_restore_rejects_same_source_and_destination(tmp_path: Path) -> None:
    database = tmp_path / "live.sqlite3"
    _create_database(database, "preserved")

    with pytest.raises(ValueError, match="must be different"):
        restore_backup(database, database)

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT value FROM notes").fetchone() == ("preserved",)
