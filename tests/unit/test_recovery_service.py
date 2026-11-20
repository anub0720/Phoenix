from unittest.mock import Mock

from phoenix.adapters.docker_restore_adapter import DockerRestoreAdapter
from phoenix.adapters.postgres.validation_adapter import (
    PostgresValidationAdapter,
)
from phoenix.domain.restoration import RestoreResult
from phoenix.domain.validation import ValidationPlan
from phoenix.recovery.service import RecoveryService


def test_recover_builds_validation_checks_for_restored_container(
    monkeypatch,
):
    restore_service = Mock()
    restore_service.restore_backup.return_value = RestoreResult(
        success=True,
        backup_name="backup",
        container_id="container-123",
        duration_seconds=1.0,
        error_message=None,
        retained=True,
    )
    validation_adapter = Mock(spec=PostgresValidationAdapter)
    restore_adapter = Mock(spec=DockerRestoreAdapter)
    checks = Mock()
    validation_report = Mock()
    validation_service = Mock()
    validation_service.validate.return_value = validation_report
    checks_factory = Mock(return_value=checks)
    validation_service_factory = Mock(return_value=validation_service)

    monkeypatch.setattr(
        "phoenix.recovery.service.PostgresValidationChecks",
        checks_factory,
    )
    monkeypatch.setattr(
        "phoenix.recovery.service.ValidationService",
        validation_service_factory,
    )

    service = RecoveryService(
        restore_service=restore_service,
        validation_adapter=validation_adapter,
        restore_adapter=restore_adapter,
    )
    plan = ValidationPlan(database_name="phoenix_restore")

    result = service.recover("backup", plan)

    checks_factory.assert_called_once_with(
        adapter=validation_adapter,
        container_id="container-123",
    )
    validation_service_factory.assert_called_once_with(checks)
    validation_service.validate.assert_called_once_with(plan)
    restore_adapter.cleanup_container.assert_called_once_with(
        "container-123"
    )
    assert result.validation_report is validation_report
