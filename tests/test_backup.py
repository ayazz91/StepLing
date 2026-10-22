import sqlite3
from pathlib import Path

import pytest

from bot.backup import create_backup, restore_backup


def test_backup_is_consistent_and_can_be_restored(tmp_path: Path) -> None:
    database = tmp_path / "live.sqlite3"
    backup_dir = tmp_path / "backups"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE notes (value TEXT)")
        connection.execute("INSERT INTO notes VALUES ('saved')")

    backup = create_backup(database, backup_dir)

    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE notes SET value = 'changed'")
    restore_backup(backup, database)

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT value FROM notes").fetchone() == ("saved",)


def test_restore_rejects_invalid_backup_without_overwriting_database(tmp_path: Path) -> None:
    database = tmp_path / "live.sqlite3"
    invalid_backup = tmp_path / "invalid.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE notes (value TEXT)")
        connection.execute("INSERT INTO notes VALUES ('preserved')")
    invalid_backup.write_text("not a sqlite database", encoding="utf-8")

    with pytest.raises(sqlite3.DatabaseError):
        restore_backup(invalid_backup, database)

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT value FROM notes").fetchone() == ("preserved",)
