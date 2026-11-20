
from datetime import datetime, timedelta, timezone

import pytest

from phoenix.domain.validation import (
    ValidationCheck,
    ValidationReport,
    ValidationResult,
    ValidationStatus,
)


def make_result(
    check_id: str = "database_connectivity",
    status: ValidationStatus = ValidationStatus.PASS,
) -> ValidationResult:
    return ValidationResult(
        check_id=check_id,
        name="Database connectivity",
        status=status,
        expected="Database accepts connections",
        actual="Connection successful",
        duration_seconds=0.25,
    )


def make_report(
    results: tuple[ValidationResult, ...],
) -> ValidationReport:
    started_at = datetime.now(timezone.utc)

    return ValidationReport(
        report_id="report-001",
        database_name="phoenix_restore",
        started_at=started_at,
        completed_at=started_at + timedelta(seconds=2),
        results=results,
    )


def test_validation_check_definition():
    check = ValidationCheck(
        check_id="users_table_exists",
        name="Users table exists",
        description="Verify that the users table exists.",
    )

    assert check.check_id == "users_table_exists"
    assert check.name == "Users table exists"


def test_validation_result_pass():
    result = make_result()

    assert result.status == ValidationStatus.PASS
    assert result.expected == "Database accepts connections"
    assert result.actual == "Connection successful"
    assert result.duration_seconds == 0.25


def test_validation_result_rejects_negative_duration():
    with pytest.raises(ValueError):
        ValidationResult(
            check_id="test",
            name="Test",
            status=ValidationStatus.PASS,
            duration_seconds=-1,
        )


def test_report_counts_results():
    report = make_report(
        (
            make_result("check-1", ValidationStatus.PASS),
            make_result("check-2", ValidationStatus.PASS),
            make_result("check-3", ValidationStatus.FAIL),
            make_result("check-4", ValidationStatus.ERROR),
            make_result("check-5", ValidationStatus.SKIPPED),
        )
    )

    assert report.total_checks == 5
    assert report.passed == 2
    assert report.failed == 1
    assert report.errors == 1
    assert report.skipped == 1


def test_report_overall_status_is_fail_when_check_fails():
    report = make_report(
        (
            make_result("check-1", ValidationStatus.PASS),
            make_result("check-2", ValidationStatus.FAIL),
        )
    )

    assert report.overall_status == ValidationStatus.FAIL


def test_report_overall_status_is_error_without_failures():
    report = make_report(
        (
            make_result("check-1", ValidationStatus.PASS),
            make_result("check-2", ValidationStatus.ERROR),
        )
    )

    assert report.overall_status == ValidationStatus.ERROR


def test_report_overall_status_is_pass():
    report = make_report(
        (
            make_result("check-1", ValidationStatus.PASS),
            make_result("check-2", ValidationStatus.SKIPPED),
        )
    )

    assert report.overall_status == ValidationStatus.PASS


def test_report_with_only_skipped_checks():
    report = make_report(
        (
            make_result("check-1", ValidationStatus.SKIPPED),
        )
    )

    assert report.overall_status == ValidationStatus.SKIPPED


def test_report_rejects_duplicate_check_ids():
    result = make_result("duplicate")

    with pytest.raises(ValueError, match="duplicate check IDs"):
        make_report((result, result))


def test_report_rejects_invalid_timestamps():
    started_at = datetime.now(timezone.utc)

    with pytest.raises(ValueError, match="precede start time"):
        ValidationReport(
            report_id="report-002",
            database_name="phoenix_restore",
            started_at=started_at,
            completed_at=started_at - timedelta(seconds=1),
            results=(),
        )


def test_validation_result_is_immutable():
    result = make_result()

    with pytest.raises(AttributeError):
        result.status = ValidationStatus.FAIL
