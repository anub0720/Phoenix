
"""Application services for backup management."""

import hashlib
import uuid

from datetime import datetime, timezone
from pathlib import Path

from phoenix.domain.integrity import IntegrityVerificationResult
from phoenix.domain.models import BackupArtifact
from phoenix.adapters.postgres.archive_inspector import (
    PostgresArchiveInspector,
)

class BackupService:
    """Coordinates backup registration and retrieval."""

    def __init__(self, repository):
        self.repository = repository

    @staticmethod
    def _calculate_checksum(path: Path) -> str:
        sha256 = hashlib.sha256()

        with path.open("rb") as backup_file:
            while chunk := backup_file.read(1024 * 1024):
                sha256.update(chunk)

        return sha256.hexdigest()

    def register_backup(
        self,
        path: Path,
        display_name: str,
    ) -> BackupArtifact:

        path = path.expanduser().resolve()

        if not path.exists():
            raise FileNotFoundError(
                f"Backup file does not exist: {path}"
            )

        if not path.is_file():
            raise ValueError(
                f"Backup path is not a file: {path}"
            )

        if not display_name.strip():
            raise ValueError(
                "Backup display name cannot be empty."
            )

        if self.repository.get_by_name(display_name):
            raise ValueError(
                f"A backup named '{display_name}' "
                "is already registered."
            )

        artifact = BackupArtifact(
            id=str(uuid.uuid4()),
            display_name=display_name,
            local_path=str(path),
            format="postgres_custom",
            size_bytes=path.stat().st_size,
            checksum=self._calculate_checksum(path),
            registered_at=datetime.now(timezone.utc),
        )

        self.repository.save(artifact)

        return artifact

    def list_backups(self) -> list[BackupArtifact]:
        return self.repository.list_all()

    def get_backup(self, display_name: str) -> BackupArtifact:
        artifact = self.repository.get_by_name(display_name)

        if artifact is None:
            raise LookupError(
                f"No registered backup found: {display_name}"
            )

        return artifact

    def inspect_backup(
        self,
        display_name: str,
        inspector: PostgresArchiveInspector,
    ):
        artifact = self.get_backup(display_name)

        return inspector.inspect(
            Path(artifact.local_path)
        )

    
    def verify_backup_integrity(
        self, display_name: str
    ) -> IntegrityVerificationResult:
        artifact = self.get_backup(display_name)

        current_checksum = self._calculate_checksum(
            Path(artifact.local_path)
        )

        return IntegrityVerificationResult(
            verified=current_checksum == artifact.checksum,
            stored_checksum=artifact.checksum,
            current_checksum=current_checksum,
        )
