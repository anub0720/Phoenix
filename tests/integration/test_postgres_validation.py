
"""Integration tests for PostgreSQL recovery validation."""

import pytest

from phoenix.adapters.docker_restore_adapter import DockerRestoreAdapter
from phoenix.adapters.postgres.validation_adapter import (
    PostgresValidationAdapter,
)
from phoenix.domain.validation import ValidationStatus
from phoenix.validation.checks import PostgresValidationChecks
from phoenix.domain.validation import ValidationPlan
from phoenix.validation.service import ValidationService

@pytest.mark.integration
@pytest.mark.docker
def test_validation_checks_against_restored_postgres(postgres_test_dump):
    restore_adapter = DockerRestoreAdapter()

    restore_result = restore_adapter.restore(
        backup_path=postgres_test_dump,
        backup_name="validation-integration-backup",
        diagnostic_mode=True,
    )

    assert restore_result.success is True
    assert restore_result.container_id is not None
    assert restore_result.retained is True

    container_id = restore_result.container_id

    try:
        validation_adapter = PostgresValidationAdapter(
            database_name="phoenix_restore",
            database_user="postgres",
        )

        checks = PostgresValidationChecks(
            adapter=validation_adapter,
            container_id=container_id,
        )

        # 1. PostgreSQL should accept a query.
        connectivity = checks.check_database_connectivity()
        assert connectivity.status == ValidationStatus.PASS
        assert connectivity.actual == "1"

        # 2. The restored public schema should exist.
        schema = checks.check_schema_exists("public")
        assert schema.status == ValidationStatus.PASS

        # 3. The table created in the source database should exist.
        table = checks.check_table_exists(
            "public",
            "recovery_test",
        )
        assert table.status == ValidationStatus.PASS

        # 4. A table that was never created should not exist.
        missing_table = checks.check_table_exists(
            "public",
            "table_that_does_not_exist",
        )
        assert missing_table.status == ValidationStatus.FAIL

        # 5. The restored table should contain all three records.
        row_count = checks.check_row_count(
            "public",
            "recovery_test",
            expected_count=3,
        )
        assert row_count.status == ValidationStatus.PASS
        assert row_count.actual == "3"

        # 6. The default PostgreSQL procedural language should exist.
        extension = checks.check_extension_exists("plpgsql")
        assert extension.status == ValidationStatus.PASS

        # 7. A nonexistent extension should fail the expectation.
        missing_extension = checks.check_extension_exists(
            "phoenix_missing_extension"
        )
        assert missing_extension.status == ValidationStatus.FAIL

        # 8. The adapter must reject a write query.
        with pytest.raises(ValueError, match="Only SELECT"):
            validation_adapter.execute_scalar(
                container_id,
                "UPDATE recovery_test SET value = 'modified'",
            )

        # 9. Verify that validation did not change the recovered data.
        final_count = validation_adapter.execute_scalar(
            container_id,
            "SELECT COUNT(*) FROM public.recovery_test",
        )
        assert final_count == "3"
        
        # 10. Run a complete validation plan against the restored database.
        validation_service = ValidationService(checks)

        plan = ValidationPlan(
            database_name="phoenix_restore",
            schemas=("public",),
            tables=(
                ("public", "recovery_test"),
            ),
            row_counts=(
                ("public", "recovery_test", 3),
            ),
        )

        report = validation_service.validate(plan)

        assert report.database_name == "phoenix_restore"
        assert report.total_checks == 4
        assert report.passed == 4
        assert report.failed == 0
        assert report.errors == 0
        assert report.overall_status == ValidationStatus.PASS
        assert report.started_at <= report.completed_at
        assert report.report_id

    finally:
        restore_adapter._remove_container(container_id)
