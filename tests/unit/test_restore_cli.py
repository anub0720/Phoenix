
from typer.testing import CliRunner
from unittest.mock import Mock

from phoenix.cli import app
from phoenix.restore.service import BackupIntegrityError

runner = CliRunner()


def test_restore_command_success(monkeypatch):
    service = Mock()
    service.restore_backup.return_value = Mock(
        success=True,
        backup_name="ecommerce-real",
        duration_seconds=4.2,
        container_id="container-123",
        retained=False,
        error_message=None,
    )

    monkeypatch.setattr(
        "phoenix.cli.get_restore_service",
        lambda: service,
    )

    result = runner.invoke(
        app,
        ["backup", "restore", "ecommerce-real"],
    )

    assert result.exit_code == 0
    assert "RESTORE: SUCCESS" in result.output
    service.restore_backup.assert_called_once()


def test_restore_command_diagnostic(monkeypatch):
    service = Mock()
    service.restore_backup.return_value = Mock(
        success=True,
        backup_name="ecommerce-real",
        duration_seconds=4.2,
        container_id="container-123",
        retained=True,
        error_message=None,
    )

    monkeypatch.setattr(
        "phoenix.cli.get_restore_service",
        lambda: service,
    )

    result = runner.invoke(
        app,
        ["backup", "restore", "ecommerce-real", "--diagnostic"],
    )

    assert result.exit_code == 0
    assert "retained" in result.output.lower()

    assert service.restore_backup.call_args.kwargs[
        "diagnostic_mode"
    ] is True


def test_restore_command_integrity_failure(monkeypatch):
    service = Mock()
    service.restore_backup.side_effect = BackupIntegrityError(
        "Integrity verification failed."
    )

    monkeypatch.setattr(
        "phoenix.cli.get_restore_service",
        lambda: service,
    )

    result = runner.invoke(
        app,
        ["backup", "restore", "ecommerce-real"],
    )

    assert result.exit_code == 1
    assert "RESTORE ABORTED" in result.output
