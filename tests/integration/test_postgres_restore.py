
"""Integration tests for real PostgreSQL restoration."""

import subprocess

import pytest

from phoenix.adapters.docker_restore_adapter import (
    DockerRestoreAdapter,
)


@pytest.mark.integration
@pytest.mark.docker
def test_restore_recovers_actual_data(
    postgres_test_dump,
):
    adapter = DockerRestoreAdapter()

    result = adapter.restore(
        backup_path=postgres_test_dump,
        backup_name="integration-backup",
        diagnostic_mode=True,
    )

    assert result.success is True
    assert result.container_id is not None
    assert result.retained is True

    container_id = result.container_id

    try:
        # Confirm the database was restored.
        query = subprocess.run(
            [
                "docker",
                "exec",
                container_id,
                "psql",
                "-U",
                "postgres",
                "-d",
                "phoenix_restore",
                "-t",
                "-A",
                "-c",
                "SELECT count(*) FROM recovery_test;",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )

        assert query.stdout.strip() == "3"

        # Verify actual restored values.
        query = subprocess.run(
            [
                "docker",
                "exec",
                container_id,
                "psql",
                "-U",
                "postgres",
                "-d",
                "phoenix_restore",
                "-t",
                "-A",
                "-c",
                "SELECT value FROM recovery_test ORDER BY id;",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )

        restored_values = query.stdout.strip().splitlines()

        assert restored_values == [
            "phoenix-alpha",
            "phoenix-beta",
            "phoenix-gamma",
        ]

    finally:
        adapter._remove_container(container_id)
