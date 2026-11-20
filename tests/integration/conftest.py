
"""Fixtures for Phoenix integration tests."""

import subprocess
import time
import uuid
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def docker_available():
    """Check whether Docker Engine is available."""

    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


@pytest.fixture
def require_docker(docker_available):
    """Skip Docker-dependent tests if Docker is unavailable."""

    if not docker_available:
        pytest.skip("Docker Engine is not available.")


@pytest.fixture
def postgres_test_dump(tmp_path, require_docker):
    """Generate a real PostgreSQL custom-format backup."""

    container_name = f"phoenix-source-{uuid.uuid4().hex[:10]}"
    dump_inside_container = "/tmp/phoenix-test.dump"
    dump_on_host = tmp_path / "phoenix-test.dump"

    run_command = [
        "docker",
        "run",
        "-d",
        "--name",
        container_name,
        "--network",
        "none",
        "-e",
        "POSTGRES_PASSWORD=test_password",
        "postgres:16",
    ]

    container_id = None

    try:
        result = subprocess.run(
            run_command,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

        if result.returncode != 0:
            pytest.fail(
                f"Could not start test PostgreSQL: {result.stderr}"
            )

        container_id = result.stdout.strip()

        # Wait until PostgreSQL is ready.
        ready = False

        for _ in range(60):
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    container_id,
                    "pg_isready",
                    "-h",
                    "127.0.0.1",
                    "-U",
                    "postgres",
                ],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )

            if result.returncode == 0:
                ready = True
                break

            time.sleep(1)

        if not ready:
            pytest.fail("Test PostgreSQL did not become ready.")

        # Create deterministic test data.
        subprocess.run(
            [
                "docker",
                "exec",
                container_id,
                "psql",
                "-U",
                "postgres",
                "-d",
                "postgres",
                "-c",
                """
                CREATE DATABASE phoenix_test;
                """,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )

        subprocess.run(
            [
                "docker",
                "exec",
                container_id,
                "psql",
                "-U",
                "postgres",
                "-d",
                "phoenix_test",
                "-c",
                """
                CREATE TABLE recovery_test (
                    id INTEGER PRIMARY KEY,
                    value TEXT NOT NULL
                );

                INSERT INTO recovery_test VALUES
                    (1, 'phoenix-alpha'),
                    (2, 'phoenix-beta'),
                    (3, 'phoenix-gamma');
                """,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )

        # Generate a real PostgreSQL custom-format dump.
        subprocess.run(
            [
                "docker",
                "exec",
                container_id,
                "pg_dump",
                "-U",
                "postgres",
                "-Fc",
                "-d",
                "phoenix_test",
                "-f",
                dump_inside_container,
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )

        # Copy the dump into the pytest temporary directory.
        subprocess.run(
            [
                "docker",
                "cp",
                f"{container_id}:{dump_inside_container}",
                str(dump_on_host),
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )

        yield dump_on_host

    finally:
        if container_id:
            subprocess.run(
                ["docker", "rm", "-f", container_id],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
