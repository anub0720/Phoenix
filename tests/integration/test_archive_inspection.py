
"""Integration tests for PostgreSQL archive inspection."""

import pytest

from phoenix.adapters.postgres.archive_inspector import (
    PostgresArchiveInspector,
)


@pytest.mark.integration
@pytest.mark.docker
def test_real_postgres_archive_is_inspected(
    postgres_test_dump,
):
    inspector = PostgresArchiveInspector()

    result = inspector.inspect(postgres_test_dump)

    assert result.valid is True
    assert result.archive_path
    assert result.object_count > 0
    assert result.archive_listing
