
"""End-to-end integration tests for the recovery workflow."""

import pytest

from phoenix.adapters.sqlite_backup_repository import (
    SQLiteBackupRepository,
)
from phoenix.adapters.docker_restore_adapter import (
    DockerRestoreAdapter,
)
from phoenix.backup.service import BackupService
from phoenix.restore.service import RestoreService


@pytest.mark.integration
@pytest.mark.docker
def test_complete_recovery_workflow(
    postgres_test_dump,
    tmp_path,
):
    repository = SQLiteBackupRepository(
        tmp_path / "phoenix.db"
    )

    backup_service = BackupService(repository)
    restore_adapter = DockerRestoreAdapter()

    restore_service = RestoreService(
        backup_service=backup_service,
        restore_adapter=restore_adapter,
    )

    # 1. Register the real backup.
    artifact = backup_service.register_backup(
        postgres_test_dump,
        "recovery-e2e",
    )

    # 2. Verify its integrity.
    integrity = backup_service.verify_backup_integrity(
        "recovery-e2e"
    )

    assert integrity.verified is True

    # 3. Restore through the application service.
    result = restore_service.restore_backup(
        "recovery-e2e",
        diagnostic_mode=True,
    )

    try:
        assert result.success is True
        assert result.container_id is not None
        assert result.backup_name == artifact.display_name

        # 4. Verify the restored database actually exists.
        import subprocess

        query = subprocess.run(
            [
                "docker",
                "exec",
                result.container_id,
                "psql",
                "-U",
                "postgres",
                "-d",
                "phoenix_restore",
                "-t",
                "-A",
                "-c",
                "SELECT count(*) FROM recovery_test;",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )

        assert query.stdout.strip() == "3"

    finally:
        if result.container_id is not None:
            restore_adapter._remove_container(result.container_id)
