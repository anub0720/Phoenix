
import pytest

from phoenix.backup.service import BackupService
from phoenix.adapters.sqlite_backup_repository import SQLiteBackupRepository


def test_verify_unchanged_backup(tmp_path):
    backup_file = tmp_path / "backup.dump"
    backup_file.write_bytes(b"original backup data")

    repository = SQLiteBackupRepository(tmp_path / "phoenix.db")
    service = BackupService(repository)

    service.register_backup(backup_file, "test-backup")

    result = service.verify_backup_integrity("test-backup")

    assert result.verified is True
    assert result.stored_checksum == result.current_checksum


def test_verify_modified_backup(tmp_path):
    backup_file = tmp_path / "backup.dump"
    backup_file.write_bytes(b"original backup data")

    repository = SQLiteBackupRepository(tmp_path / "phoenix.db")
    service = BackupService(repository)

    service.register_backup(backup_file, "test-backup")

    original_checksum = service.get_backup(
        "test-backup"
    ).checksum

    backup_file.write_bytes(b"modified backup data")

    result = service.verify_backup_integrity("test-backup")

    assert result.verified is False
    assert result.stored_checksum == original_checksum
    assert result.current_checksum != original_checksum

    # Verification must not overwrite the original checksum.
    artifact = service.get_backup("test-backup")
    assert artifact.checksum == original_checksum


def test_verify_missing_registered_file(tmp_path):
    backup_file = tmp_path / "backup.dump"
    backup_file.write_bytes(b"original backup data")

    repository = SQLiteBackupRepository(tmp_path / "phoenix.db")
    service = BackupService(repository)

    service.register_backup(backup_file, "test-backup")

    backup_file.unlink()

    with pytest.raises(FileNotFoundError):
        service.verify_backup_integrity("test-backup")


def test_verify_unregistered_backup(tmp_path):
    repository = SQLiteBackupRepository(tmp_path / "phoenix.db")
    service = BackupService(repository)

    with pytest.raises(LookupError):
        service.verify_backup_integrity("unknown-backup")
