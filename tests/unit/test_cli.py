
from datetime import datetime, timezone
from unittest.mock import Mock

from typer.testing import CliRunner

import phoenix.cli as cli
from phoenix.cli import app
from phoenix.domain.recovery import RecoveryResult
from phoenix.domain.restoration import RestoreResult
from phoenix.domain.validation import (
    ValidationPlan,
    ValidationReport,
    ValidationResult,
    ValidationStatus,
)

runner = CliRunner()


def test_version_command():
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert "Phoenix v0.1.0" in result.stdout


def test_help_command():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "version" in result.stdout


def test_get_recovery_service_wires_runtime_dependencies(monkeypatch):
    backup_service = Mock()
    restore_adapter = Mock()
    restore_service = Mock()
    validation_adapter = Mock()
    recovery_service = Mock()

    restore_adapter_factory = Mock(return_value=restore_adapter)
    restore_service_factory = Mock(return_value=restore_service)
    validation_adapter_factory = Mock(return_value=validation_adapter)
    recovery_service_factory = Mock(return_value=recovery_service)

    monkeypatch.setattr(
        cli,
        "get_backup_service",
        lambda: backup_service,
    )
    monkeypatch.setattr(cli, "DockerRestoreAdapter", restore_adapter_factory)
    monkeypatch.setattr(cli, "RestoreService", restore_service_factory)
    monkeypatch.setattr(
        cli,
        "PostgresValidationAdapter",
        validation_adapter_factory,
    )
    monkeypatch.setattr(cli, "RecoveryService", recovery_service_factory)

    result = cli.get_recovery_service()

    assert result is recovery_service
    restore_service_factory.assert_called_once_with(
        backup_service=backup_service,
        restore_adapter=restore_adapter,
    )
    validation_adapter_factory.assert_called_once_with(
        database_name="phoenix_restore",
    )
    recovery_service_factory.assert_called_once_with(
        restore_service=restore_service,
        validation_adapter=validation_adapter,
        restore_adapter=restore_adapter,
    )


def test_recover_command_runs_validation_and_displays_results(
    monkeypatch,
):
    now = datetime.now(timezone.utc)
    restore_result = RestoreResult(
        success=True,
        backup_name="backup-1",
        container_id="container-123",
        duration_seconds=1.5,
        retained=True,
    )
    validation_report = ValidationReport(
        report_id="report-1",
        database_name="phoenix_restore",
        started_at=now,
        completed_at=now,
        results=(
            ValidationResult(
                check_id="schema_exists:public",
                name="Schema public exists",
                status=ValidationStatus.PASS,
                expected="true",
                actual="true",
            ),
        ),
    )
    recovery_result = RecoveryResult(
        restore_result=restore_result,
        validation_report=validation_report,
        container_retained=True,
    )
    service = Mock()
    service.recover.return_value = recovery_result
    monkeypatch.setattr(cli, "get_recovery_service", lambda: service)

    result = runner.invoke(
        app,
        [
            "backup",
            "recover",
            "backup-1",
            "--schema",
            "public",
            "--table",
            "public.users",
            "--extension",
            "pgcrypto",
            "--diagnostic",
        ],
    )

    assert result.exit_code == 0
    assert "RESTORE: PASS" in result.output
    assert "PASS: Schema public exists" in result.output
    assert "VALIDATION: PASS" in result.output
    assert "Container retained: container-123" in result.output
    service.recover.assert_called_once_with(
        backup_name="backup-1",
        validation_plan=ValidationPlan(
            database_name="phoenix_restore",
            schemas=("public",),
            tables=(("public", "users"),),
            extensions=("pgcrypto",),
        ),
        diagnostic_mode=True,
    )


def test_recover_command_rejects_malformed_table(monkeypatch):
    get_recovery_service = Mock()
    monkeypatch.setattr(
        cli,
        "get_recovery_service",
        get_recovery_service,
    )

    result = runner.invoke(
        app,
        ["backup", "recover", "backup-1", "--table", "users"],
    )

    assert result.exit_code == 1
    assert "RECOVERY ABORTED" in result.output
    assert "Use schema.table format" in result.output
    get_recovery_service.assert_not_called()
