
"""Application service for PostgreSQL backup restoration."""

from pathlib import Path

from phoenix.backup.service import BackupService
from phoenix.adapters.docker_restore_adapter import DockerRestoreAdapter
from phoenix.domain.restoration import RestoreResult


class RestoreService:
    """Coordinates backup integrity verification and restoration."""

    def __init__(
        self,
        backup_service: BackupService,
        restore_adapter: DockerRestoreAdapter,
    ):
        self.backup_service = backup_service
        self.restore_adapter = restore_adapter

    def restore_backup(
        self,
        display_name: str,
        diagnostic_mode: bool = False,
    ) -> RestoreResult:

        # Step 1: Retrieve the registered backup.
        artifact = self.backup_service.get_backup(display_name)

        # Step 2: Verify that the backup has not changed.
        integrity_result = (
            self.backup_service.verify_backup_integrity(display_name)
        )

        # Step 3: Refuse restoration if integrity verification fails.
        if not integrity_result.verified:
            raise ValueError(
                f"Backup integrity verification failed for "
                f"'{display_name}'. Restoration cancelled."
            )

        # Step 4: Restore using the Docker adapter.
        return self.restore_adapter.restore(
            backup_path=Path(artifact.local_path),
            backup_name=artifact.display_name,
            diagnostic_mode=diagnostic_mode,
        )
