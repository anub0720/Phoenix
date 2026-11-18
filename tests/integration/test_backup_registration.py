
"""Integration tests for backup registration and SQLite persistence."""

import pytest

from phoenix.adapters.sqlite_backup_repository import SQLiteBackupRepository
from phoenix.backup.service import BackupService


@pytest.mark.integration
def test_register_backup_persists_metadata(
    postgres_test_dump,
    tmp_path,
):
    database_path = tmp_path / "phoenix-test.db"

    repository = SQLiteBackupRepository(database_path)
    service = BackupService(repository)

    artifact = service.register_backup(
        postgres_test_dump,
        "integration-backup",
    )

    # Verify registration.
    assert artifact.display_name == "integration-backup"
    assert artifact.size_bytes > 0
    assert artifact.checksum

    # Reopen repository to verify persistence.
    reopened_repository = SQLiteBackupRepository(database_path)

    stored = reopened_repository.get_by_name(
        "integration-backup"
    )

    assert stored is not None
    assert stored.id == artifact.id
    assert stored.checksum == artifact.checksum
    assert stored.local_path == artifact.local_path
