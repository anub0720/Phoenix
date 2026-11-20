"""Coordinates backup restoration and post-restore validation."""

from phoenix.domain.recovery import RecoveryResult
from phoenix.domain.validation import ValidationPlan
from phoenix.restore.service import RestoreService

from phoenix.adapters.docker_restore_adapter import DockerRestoreAdapter
from phoenix.adapters.postgres.validation_adapter import (
    PostgresValidationAdapter,
)
from phoenix.validation.checks import PostgresValidationChecks
from phoenix.validation.service import ValidationService


class RecoveryService:
    """Runs the complete restore, validate, and cleanup workflow."""

    def __init__(
        self,
        restore_service: RestoreService,
        validation_adapter: PostgresValidationAdapter,
        restore_adapter: DockerRestoreAdapter,
    ) -> None:
        self.restore_service = restore_service
        self.validation_adapter = validation_adapter
        self.restore_adapter = restore_adapter

    def recover(
        self,
        backup_name: str,
        validation_plan: ValidationPlan,
        diagnostic_mode: bool = False,
    ) -> RecoveryResult:
        """Restore a backup, validate it, and clean up its container."""

        # Retain the container temporarily so validation can access it.
        restore_result = self.restore_service.restore_backup(
            display_name=backup_name,
            diagnostic_mode=True,
        )

        container_id = restore_result.container_id
        validation_report = None
        validation_error = None
        cleanup_error = None

        # A failed restore must never be treated as a valid database.
        if not restore_result.success:
            if container_id and not diagnostic_mode:
                try:
                    self.restore_adapter.cleanup_container(container_id)
                except Exception as error:
                    cleanup_error = str(error)

            return RecoveryResult(
                restore_result=restore_result,
                validation_report=None,
                container_retained=bool(
                    container_id and (
                        diagnostic_mode or cleanup_error is not None
                    )
                ),
                cleanup_error=cleanup_error,
            )

        if not container_id:
            return RecoveryResult(
                restore_result=restore_result,
                validation_report=None,
                container_retained=False,
                validation_error=(
                    "Restore reported success but returned no container ID."
                ),
            )

        try:
            checks = PostgresValidationChecks(
                adapter=self.validation_adapter,
                container_id=container_id,
            )
            validation_service = ValidationService(checks)
            validation_report = validation_service.validate(
                validation_plan
            )
        except Exception as error:
            validation_error = str(error)
        finally:
            # Keep the container only when diagnostic mode was requested.
            if not diagnostic_mode:
                try:
                    self.restore_adapter.cleanup_container(container_id)
                except Exception as error:
                    cleanup_error = str(error)

        return RecoveryResult(
            restore_result=restore_result,
            validation_report=validation_report,
            container_retained=diagnostic_mode or cleanup_error is not None,
            validation_error=validation_error,
            cleanup_error=cleanup_error,
        )