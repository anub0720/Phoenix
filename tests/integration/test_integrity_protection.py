
"""Integration test for integrity-protected recovery."""

import pytest

from phoenix.adapters.sqlite_backup_repository import (
    SQLiteBackupRepository,
)
from phoenix.adapters.docker_restore_adapter import (
    DockerRestoreAdapter,
)
from phoenix.backup.service import BackupService
from phoenix.restore.service import (
    BackupIntegrityError,
    RestoreService,
)


@pytest.mark.integration
def test_modified_backup_is_rejected(
    postgres_test_dump,
    tmp_path,
):
    repository = SQLiteBackupRepository(
        tmp_path / "phoenix.db"
    )

    backup_service = BackupService(repository)
    adapter = DockerRestoreAdapter()

    restore_service = RestoreService(
        backup_service,
        adapter,
    )

    # Register original backup.
    backup_service.register_backup(
        postgres_test_dump,
        "protected-backup",
    )

    # Alter the registered backup after registration.
    with postgres_test_dump.open("ab") as backup_file:
        backup_file.write(b"ALTERED")

    # Restoration must be rejected before Docker is invoked.
    with pytest.raises(BackupIntegrityError):
        restore_service.restore_backup("protected-backup")
