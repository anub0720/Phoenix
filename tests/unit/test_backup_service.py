
import hashlib

import pytest

from phoenix.backup.service import BackupService
from phoenix.adapters.sqlite_backup_repository import (
    SQLiteBackupRepository,
)


@pytest.fixture
def backup_environment(tmp_path):
    database_path = tmp_path / "phoenix.db"

    repository = SQLiteBackupRepository(database_path)
    service = BackupService(repository)

    backup_file = tmp_path / "test_backup.dump"
    backup_file.write_bytes(b"synthetic-postgresql-backup")

    return service, backup_file


def test_register_backup(backup_environment):
    service, backup_file = backup_environment

    artifact = service.register_backup(
        backup_file,
        "test-backup",
    )

    assert artifact.display_name == "test-backup"
    assert artifact.size_bytes == backup_file.stat().st_size
    assert artifact.format == "postgres_custom"


def test_checksum_is_correct(backup_environment):
    service, backup_file = backup_environment

    artifact = service.register_backup(
        backup_file,
        "test-backup",
    )

    expected_checksum = hashlib.sha256(
        backup_file.read_bytes()
    ).hexdigest()

    assert artifact.checksum == expected_checksum


def test_duplicate_backup_name_is_rejected(
    backup_environment,
):
    service, backup_file = backup_environment

    service.register_backup(
        backup_file,
        "test-backup",
    )

    with pytest.raises(ValueError):
        service.register_backup(
            backup_file,
            "test-backup",
        )


def test_missing_backup_is_rejected(backup_environment):
    service, backup_file = backup_environment
    missing_file = backup_file.parent / "missing.dump"

    with pytest.raises(FileNotFoundError):
        service.register_backup(missing_file, "missing-backup")


def test_registered_backup_can_be_retrieved(
    backup_environment,
):
    service, backup_file = backup_environment

    service.register_backup(
        backup_file,
        "test-backup",
    )

    artifact = service.get_backup("test-backup")

    assert artifact.display_name == "test-backup"


def test_unknown_backup_returns_lookup_error(
    backup_environment,
):
    service, _ = backup_environment

    with pytest.raises(LookupError):
        service.get_backup("does-not-exist")


def test_registration_persists_across_repository_instances(
    backup_environment,
):
    service, backup_file = backup_environment

    service.register_backup(
        backup_file,
        "persistent-backup",
    )

    database_path = backup_file.parent / "phoenix.db"

    new_repository = SQLiteBackupRepository(database_path)

    restored_artifact = new_repository.get_by_name(
        "persistent-backup"
    )

    assert restored_artifact is not None
    assert restored_artifact.display_name == "persistent-backup"
