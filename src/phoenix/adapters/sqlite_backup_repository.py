
"""SQLite persistence adapter for backup artifacts."""

import sqlite3
from pathlib import Path
from datetime import datetime

from phoenix.domain.models import BackupArtifact


class SQLiteBackupRepository:
    """Stores and retrieves backup metadata using SQLite."""

    def __init__(self, database_path: Path):
        self.database_path = database_path

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._initialize_database()

    def _connect(self):
        return sqlite3.connect(self.database_path)

    def _initialize_database(self):
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS backup_artifacts (
                    id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL UNIQUE,
                    local_path TEXT NOT NULL,
                    format TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    checksum TEXT NOT NULL,
                    registered_at TEXT NOT NULL
                )
                """
            )

    def save(self, artifact: BackupArtifact) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO backup_artifacts (
                    id,
                    display_name,
                    local_path,
                    format,
                    size_bytes,
                    checksum,
                    registered_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact.id,
                    artifact.display_name,
                    artifact.local_path,
                    artifact.format,
                    artifact.size_bytes,
                    artifact.checksum,
                    artifact.registered_at.isoformat(),
                ),
            )

    def list_all(self) -> list[BackupArtifact]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, display_name, local_path,
                       format, size_bytes, checksum,
                       registered_at
                FROM backup_artifacts
                ORDER BY registered_at DESC
                """
            ).fetchall()

        return [
            self._row_to_artifact(row)
            for row in rows
        ]

    def get_by_name(self, name: str) -> BackupArtifact | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, display_name, local_path,
                       format, size_bytes, checksum,
                       registered_at
                FROM backup_artifacts
                WHERE display_name = ?
                """,
                (name,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_artifact(row)

    @staticmethod
    def _row_to_artifact(row) -> BackupArtifact:
        return BackupArtifact(
            id=row[0],
            display_name=row[1],
            local_path=row[2],
            format=row[3],
            size_bytes=row[4],
            checksum=row[5],
            registered_at=datetime.fromisoformat(row[6]),
        )
