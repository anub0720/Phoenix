"""Domain model for an end-to-end recovery and validation operation."""

from dataclasses import dataclass

from phoenix.domain.restoration import RestoreResult
from phoenix.domain.validation import ValidationReport


@dataclass(frozen=True)
class RecoveryResult:
    """Combines restoration and validation outcomes."""

    restore_result: RestoreResult
    validation_report: ValidationReport | None
    container_retained: bool
    validation_error: str | None = None
    cleanup_error: str | None = None

    @property
    def restore_success(self) -> bool:
        return self.restore_result.success

    @property
    def validation_success(self) -> bool:
        return (
            self.validation_report is not None
            and self.validation_report.overall_status.value == "PASS"
        )

    @property
    def success(self) -> bool:
        return (
            self.restore_success
            and self.validation_success
            and self.validation_error is None
            and self.cleanup_error is None
        )