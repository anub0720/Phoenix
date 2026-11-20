
"""Orchestrates PostgreSQL database validation."""

from datetime import datetime, timezone
from uuid import uuid4

from phoenix.domain.validation import (
    ValidationPlan,
    ValidationReport,
    ValidationResult,
    ValidationStatus,
)
from phoenix.validation.checks import PostgresValidationChecks


class ValidationService:
    """Coordinates validation checks and generates a report."""

    def __init__(self, checks: PostgresValidationChecks) -> None:
        self.checks = checks

    def validate(self, plan: ValidationPlan) -> ValidationReport:
        """Execute all checks defined in a validation plan."""

        started_at = datetime.now(timezone.utc)
        results: list[ValidationResult] = []

        # Connectivity is always checked first.
        results.append(
            self.checks.check_database_connectivity()
        )

        # Validate expected schemas.
        for schema_name in plan.schemas:
            results.append(
                self.checks.check_schema_exists(schema_name)
            )

        # Validate expected tables.
        for schema_name, table_name in plan.tables:
            results.append(
                self.checks.check_table_exists(
                    schema_name,
                    table_name,
                )
            )

        # Validate expected extensions.
        for extension_name in plan.extensions:
            results.append(
                self.checks.check_extension_exists(extension_name)
            )

        # Validate expected row counts.
        for schema_name, table_name, expected_count in plan.row_counts:
            results.append(
                self.checks.check_row_count(
                    schema_name,
                    table_name,
                    expected_count,
                )
            )

        completed_at = datetime.now(timezone.utc)

        return ValidationReport(
            report_id=str(uuid4()),
            database_name=plan.database_name,
            started_at=started_at,
            completed_at=completed_at,
            results=tuple(results),
        )
