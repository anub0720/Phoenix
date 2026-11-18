
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from phoenix.restore.service import (
    BackupIntegrityError,
    RestoreService,
)
from phoenix.domain.restoration import RestoreResult


@pytest.fixture
def dependencies():
    backup_service = Mock()
    restore_adapter = Mock()

    backup_service.get_backup.return_value = SimpleNamespace(
        display_name="ecommerce-real",
        local_path="/backups/ecommerce.dump",
    )

    backup_service.verify_backup_integrity.return_value = (
        SimpleNamespace(verified=True)
    )

    restore_adapter.restore.return_value = RestoreResult(
        success=True,
        backup_name="ecommerce-real",
        container_id="container-123",
        duration_seconds=4.2,
        error_message=None,
        retained=False,
    )

    service = RestoreService(backup_service, restore_adapter)

    return service, backup_service, restore_adapter


def test_successful_restore(dependencies):
    service, backup_service, adapter = dependencies

    result = service.restore_backup("ecommerce-real")

    assert result.success is True

    backup_service.get_backup.assert_called_once_with("ecommerce-real")
    backup_service.verify_backup_integrity.assert_called_once_with(
        "ecommerce-real"
    )

    adapter.restore.assert_called_once_with(
        backup_path=Path("/backups/ecommerce.dump"),
        backup_name="ecommerce-real",
        diagnostic_mode=False,
    )


def test_diagnostic_mode_is_forwarded(dependencies):
    service, _, adapter = dependencies

    service.restore_backup("ecommerce-real", diagnostic_mode=True)

    assert adapter.restore.call_args.kwargs["diagnostic_mode"] is True


def test_integrity_failure_prevents_restore(dependencies):
    service, backup_service, adapter = dependencies

    backup_service.verify_backup_integrity.return_value = (
        SimpleNamespace(verified=False)
    )

    with pytest.raises(BackupIntegrityError):
        service.restore_backup("ecommerce-real")

    adapter.restore.assert_not_called()


def test_unknown_backup_prevents_integrity_check(dependencies):
    service, backup_service, adapter = dependencies

    backup_service.get_backup.side_effect = LookupError("Unknown backup")

    with pytest.raises(LookupError):
        service.restore_backup("missing-backup")

    backup_service.verify_backup_integrity.assert_not_called()
    adapter.restore.assert_not_called()
