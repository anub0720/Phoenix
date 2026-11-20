
from unittest.mock import Mock

import pytest

from phoenix.adapters.postgres.validation_adapter import (
    PostgresValidationAdapter,
)
from phoenix.domain.validation import ValidationStatus
from phoenix.validation.checks import PostgresValidationChecks


@pytest.fixture
def adapter():
    return Mock(spec=PostgresValidationAdapter)


@pytest.fixture
def checks(adapter):
    return PostgresValidationChecks(
        adapter=adapter,
        container_id="container-123",
    )


def test_database_connectivity_passes(checks, adapter):
    adapter.execute_scalar.return_value = "1"

    result = checks.check_database_connectivity()

    assert result.status == ValidationStatus.PASS
    assert result.expected == "1"
    assert result.actual == "1"

    adapter.execute_scalar.assert_called_once_with(
        "container-123",
        "SELECT 1",
    )


def test_database_connectivity_fails_on_unexpected_result(
    checks,
    adapter,
):
    adapter.execute_scalar.return_value = "0"

    result = checks.check_database_connectivity()

    assert result.status == ValidationStatus.FAIL


def test_schema_exists_passes(checks, adapter):
    adapter.execute_scalar.return_value = "true"

    result = checks.check_schema_exists("public")

    assert result.status == ValidationStatus.PASS
    assert result.check_id == "schema_exists:public"


def test_schema_exists_fails_when_missing(checks, adapter):
    adapter.execute_scalar.return_value = "false"

    result = checks.check_schema_exists("missing_schema")

    assert result.status == ValidationStatus.FAIL


def test_table_exists_passes(checks, adapter):
    adapter.execute_scalar.return_value = "true"

    result = checks.check_table_exists("public", "users")

    assert result.status == ValidationStatus.PASS
    assert result.check_id == "table_exists:public.users"

def test_schema_exists_uses_normalized_boolean_output(
    checks,
    adapter,
):
    adapter.execute_scalar.return_value = "true"

    result = checks.check_schema_exists("public")

    assert result.status == ValidationStatus.PASS

    query = adapter.execute_scalar.call_args.args[1]
    assert ")::text" in query

def test_table_exists_fails_when_missing(checks, adapter):
    adapter.execute_scalar.return_value = "false"

    result = checks.check_table_exists("public", "missing_table")

    assert result.status == ValidationStatus.FAIL


def test_extension_exists_passes(checks, adapter):
    adapter.execute_scalar.return_value = "true"

    result = checks.check_extension_exists("pgcrypto")

    assert result.status == ValidationStatus.PASS


def test_row_count_passes(checks, adapter):
    adapter.execute_scalar.return_value = "100"

    result = checks.check_row_count(
        "public",
        "users",
        expected_count=100,
    )

    assert result.status == ValidationStatus.PASS
    assert result.expected == "100"
    assert result.actual == "100"


def test_row_count_fails_when_count_differs(checks, adapter):
    adapter.execute_scalar.return_value = "95"

    result = checks.check_row_count(
        "public",
        "users",
        expected_count=100,
    )

    assert result.status == ValidationStatus.FAIL
    assert result.expected == "100"
    assert result.actual == "95"


def test_check_records_execution_error(checks, adapter):
    adapter.execute_scalar.side_effect = RuntimeError(
        "PostgreSQL connection failed"
    )

    result = checks.check_database_connectivity()

    assert result.status == ValidationStatus.ERROR
    assert "connection failed" in result.error_message


def test_row_count_rejects_negative_expectation(checks):
    with pytest.raises(ValueError, match="cannot be negative"):
        checks.check_row_count(
            "public",
            "users",
            expected_count=-1,
        )


def test_checks_reject_empty_container_id(adapter):
    with pytest.raises(ValueError, match="Container ID"):
        PostgresValidationChecks(adapter, "")
