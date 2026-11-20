
from datetime import datetime, timezone
from unittest.mock import Mock, call

import pytest

from phoenix.domain.validation import (
    ValidationPlan,
    ValidationReport,
    ValidationResult,
    ValidationStatus,
)
from phoenix.validation.checks import PostgresValidationChecks
from phoenix.validation.service import ValidationService


def make_result(
    check_id: str,
    status: ValidationStatus = ValidationStatus.PASS,
) -> ValidationResult:
    return ValidationResult(
        check_id=check_id,
        name=check_id,
        status=status,
        expected="expected",
        actual="actual",
    )


@pytest.fixture
def checks():
    return Mock(spec=PostgresValidationChecks)


@pytest.fixture
def service(checks):
    return ValidationService(checks)


def test_validation_service_always_checks_connectivity(
    service,
    checks,
):
    checks.check_database_connectivity.return_value = make_result(
        "database_connectivity"
    )

    report = service.validate(
        ValidationPlan(database_name="phoenix_restore")
    )

    checks.check_database_connectivity.assert_called_once_with()
    assert report.total_checks == 1
    assert report.passed == 1


def test_validation_service_executes_all_plan_checks(
    service,
    checks,
):
    checks.check_database_connectivity.return_value = make_result(
        "database_connectivity"
    )
    checks.check_schema_exists.return_value = make_result(
        "schema_exists:public"
    )
    checks.check_table_exists.return_value = make_result(
        "table_exists:public.users"
    )
    checks.check_extension_exists.return_value = make_result(
        "extension_exists:pgcrypto"
    )
    checks.check_row_count.return_value = make_result(
        "row_count:public.users"
    )

    plan = ValidationPlan(
        database_name="phoenix_restore",
        schemas=("public",),
        tables=(("public", "users"),),
        extensions=("pgcrypto",),
        row_counts=(("public", "users", 100),),
    )

    report = service.validate(plan)

    assert report.database_name == "phoenix_restore"
    assert report.total_checks == 5
    assert report.passed == 5

    assert checks.method_calls == [
        call.check_database_connectivity(),
        call.check_schema_exists("public"),
        call.check_table_exists("public", "users"),
        call.check_extension_exists("pgcrypto"),
        call.check_row_count("public", "users", 100),
    ]


def test_validation_service_preserves_failed_results(
    service,
    checks,
):
    checks.check_database_connectivity.return_value = make_result(
        "database_connectivity"
    )
    checks.check_schema_exists.return_value = make_result(
        "schema_exists:missing",
        ValidationStatus.FAIL,
    )

    plan = ValidationPlan(
        database_name="phoenix_restore",
        schemas=("missing",),
    )

    report = service.validate(plan)

    assert report.total_checks == 2
    assert report.passed == 1
    assert report.failed == 1
    assert report.overall_status == ValidationStatus.FAIL


def test_validation_service_generates_unique_report_ids(
    service,
    checks,
):
    checks.check_database_connectivity.return_value = make_result(
        "database_connectivity"
    )

    plan = ValidationPlan(database_name="phoenix_restore")

    first = service.validate(plan)
    second = service.validate(plan)

    assert first.report_id != second.report_id


def test_validation_service_records_report_timestamps(
    service,
    checks,
):
    checks.check_database_connectivity.return_value = make_result(
        "database_connectivity"
    )

    report = service.validate(
        ValidationPlan(database_name="phoenix_restore")
    )

    assert isinstance(report.started_at, datetime)
    assert isinstance(report.completed_at, datetime)
    assert report.started_at.tzinfo == timezone.utc
    assert report.completed_at >= report.started_at


def test_validation_service_preserves_error_results(
    service,
    checks,
):
    checks.check_database_connectivity.return_value = make_result(
        "database_connectivity",
        ValidationStatus.ERROR,
    )

    report = service.validate(
        ValidationPlan(database_name="phoenix_restore")
    )

    assert report.errors == 1
    assert report.overall_status == ValidationStatus.ERROR


@pytest.mark.parametrize(
    "kwargs",
    [
        {"database_name": ""},
        {"database_name": "phoenix_restore", "schemas": ("",)},
        {"database_name": "phoenix_restore", "extensions": ("",)},
        {
            "database_name": "phoenix_restore",
            "tables": (("", "users"),),
        },
        {
            "database_name": "phoenix_restore",
            "row_counts": (("public", "users", -1),),
        },
    ],
)
def test_validation_plan_rejects_invalid_expectations(kwargs):
    with pytest.raises(ValueError):
        ValidationPlan(**kwargs)
