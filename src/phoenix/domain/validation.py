
"""Domain models for database validation."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class ValidationStatus(str, Enum):
    """Possible outcomes of an individual validation check."""

    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True)
class ValidationCheck:
    """Defines one validation check Phoenix intends to perform."""

    check_id: str
    name: str
    description: str


@dataclass(frozen=True)
class ValidationResult:
    """Records the outcome and evidence from one validation check."""

    check_id: str
    name: str
    status: ValidationStatus
    expected: str | None = None
    actual: str | None = None
    duration_seconds: float = 0.0
    evidence: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if self.duration_seconds < 0:
            raise ValueError("Validation duration cannot be negative.")


@dataclass(frozen=True)
class ValidationReport:
    """Aggregates the results of a database validation run."""

    report_id: str
    database_name: str
    started_at: datetime
    completed_at: datetime
    results: tuple[ValidationResult, ...]

    def __post_init__(self) -> None:
        if self.completed_at < self.started_at:
            raise ValueError(
                "Validation completion time cannot precede start time."
            )

        check_ids = [result.check_id for result in self.results]
        if len(check_ids) != len(set(check_ids)):
            raise ValueError(
                "A validation report cannot contain duplicate check IDs."
            )

    @property
    def total_checks(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(
            result.status == ValidationStatus.PASS
            for result in self.results
        )

    @property
    def failed(self) -> int:
        return sum(
            result.status == ValidationStatus.FAIL
            for result in self.results
        )

    @property
    def errors(self) -> int:
        return sum(
            result.status == ValidationStatus.ERROR
            for result in self.results
        )

    @property
    def skipped(self) -> int:
        return sum(
            result.status == ValidationStatus.SKIPPED
            for result in self.results
        )

    @property
    def overall_status(self) -> ValidationStatus:
        """Determine the overall outcome of the validation run."""

        if self.failed:
            return ValidationStatus.FAIL

        if self.errors:
            return ValidationStatus.ERROR

        if self.passed:
            return ValidationStatus.PASS

        return ValidationStatus.SKIPPED

@dataclass(frozen=True)
class ValidationPlan:
    """Defines the checks to run against a recovered database."""

    database_name: str
    schemas: tuple[str, ...] = ()
    tables: tuple[tuple[str, str], ...] = ()
    extensions: tuple[str, ...] = ()
    row_counts: tuple[tuple[str, str, int], ...] = ()

    def __post_init__(self) -> None:
        if not self.database_name.strip():
            raise ValueError("Database name cannot be empty.")

        for schema_name, table_name in self.tables:
            if not schema_name.strip() or not table_name.strip():
                raise ValueError(
                    "Table schema and name cannot be empty."
                )

        for schema_name, table_name, expected_count in self.row_counts:
            if not schema_name.strip() or not table_name.strip():
                raise ValueError(
                    "Row count schema and table name cannot be empty."
                )

            if expected_count < 0:
                raise ValueError(
                    "Expected row count cannot be negative."
                )

        if any(not name.strip() for name in self.schemas):
            raise ValueError("Schema names cannot be empty.")

        if any(not name.strip() for name in self.extensions):
            raise ValueError("Extension names cannot be empty.")
