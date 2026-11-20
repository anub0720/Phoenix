
"""Built-in PostgreSQL database validation checks."""

import time
from collections.abc import Callable

from phoenix.adapters.postgres.validation_adapter import (
    PostgresValidationAdapter,
)
from phoenix.domain.validation import (
    ValidationCheck,
    ValidationResult,
    ValidationStatus,
)


def _sql_literal(value: str) -> str:
    """Safely quote a value as a PostgreSQL string literal."""

    return "'" + value.replace("'", "''") + "'"


def _sql_identifier(value: str) -> str:
    """Safely quote a PostgreSQL identifier."""

    return '"' + value.replace('"', '""') + '"'


class PostgresValidationChecks:
    """Runs built-in read-only checks against a restored database."""

    def __init__(
        self,
        adapter: PostgresValidationAdapter,
        container_id: str,
    ) -> None:
        if not container_id or not container_id.strip():
            raise ValueError("Container ID cannot be empty.")

        self.adapter = adapter
        self.container_id = container_id

    def _run_check(
        self,
        check: ValidationCheck,
        query: str,
        expected: str,
        evaluate: Callable[[str], bool],
    ) -> ValidationResult:
        """Execute one check and capture its result and duration."""

        started_at = time.monotonic()

        try:
            actual = self.adapter.execute_scalar(
                self.container_id,
                query,
            )

            status = (
                ValidationStatus.PASS
                if evaluate(actual)
                else ValidationStatus.FAIL
            )

            return ValidationResult(
                check_id=check.check_id,
                name=check.name,
                status=status,
                expected=expected,
                actual=actual,
                duration_seconds=time.monotonic() - started_at,
                evidence=check.description,
            )

        except Exception as error:
            return ValidationResult(
                check_id=check.check_id,
                name=check.name,
                status=ValidationStatus.ERROR,
                expected=expected,
                actual=None,
                duration_seconds=time.monotonic() - started_at,
                evidence=check.description,
                error_message=str(error),
            )

    def check_database_connectivity(self) -> ValidationResult:
        check = ValidationCheck(
            check_id="database_connectivity",
            name="Database connectivity",
            description="Verify PostgreSQL can execute a simple query.",
        )

        return self._run_check(
            check=check,
            query="SELECT 1",
            expected="1",
            evaluate=lambda actual: actual == "1",
        )

    def check_schema_exists(self, schema_name: str) -> ValidationResult:
        check = ValidationCheck(
            check_id=f"schema_exists:{schema_name}",
            name=f"Schema {schema_name} exists",
            description=f"Verify the PostgreSQL schema {schema_name}.",
        )

        query = (
            "SELECT EXISTS ("
            "SELECT 1 FROM information_schema.schemata "
            f"WHERE schema_name = {_sql_literal(schema_name)}"
            ")::text"
        )

        return self._run_check(
            check=check,
            query=query,
            expected="true",
            evaluate=lambda actual: actual.lower() == "true",
        )

    def check_table_exists(
        self,
        schema_name: str,
        table_name: str,
    ) -> ValidationResult:
        check = ValidationCheck(
            check_id=f"table_exists:{schema_name}.{table_name}",
            name=f"Table {schema_name}.{table_name} exists",
            description="Verify that a required table exists.",
        )

        qualified_name = (
            f"{_sql_identifier(schema_name)}."
            f"{_sql_identifier(table_name)}"
        )

        query = (
            "SELECT (to_regclass("
            f"{_sql_literal(qualified_name)}"
            ") IS NOT NULL)::text"
        )

        return self._run_check(
            check=check,
            query=query,
            expected="true",
            evaluate=lambda actual: actual.lower() == "true",
        )

    def check_extension_exists(
        self,
        extension_name: str,
    ) -> ValidationResult:
        check = ValidationCheck(
            check_id=f"extension_exists:{extension_name}",
            name=f"Extension {extension_name} exists",
            description="Verify that a required PostgreSQL extension is installed.",
        )

        query = (
            "SELECT EXISTS ("
            "SELECT 1 FROM pg_extension "
            f"WHERE extname = {_sql_literal(extension_name)}"
            ")::text"
        )

        return self._run_check(
            check=check,
            query=query,
            expected="true",
            evaluate=lambda actual: actual.lower() == "true",
        )

    def check_row_count(
        self,
        schema_name: str,
        table_name: str,
        expected_count: int,
    ) -> ValidationResult:
        if expected_count < 0:
            raise ValueError("Expected row count cannot be negative.")

        check = ValidationCheck(
            check_id=f"row_count:{schema_name}.{table_name}",
            name=f"Row count for {schema_name}.{table_name}",
            description="Verify the table contains the expected number of rows.",
        )

        qualified_name = (
            f"{_sql_identifier(schema_name)}."
            f"{_sql_identifier(table_name)}"
        )

        query = f"SELECT COUNT(*) FROM {qualified_name}"

        return self._run_check(
            check=check,
            query=query,
            expected=str(expected_count),
            evaluate=lambda actual: actual == str(expected_count),
        )
