
import subprocess

import pytest

from phoenix.adapters.postgres.validation_adapter import (
    PostgresValidationAdapter,
)


def completed_process(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(
        args=[],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_execute_scalar_runs_psql_inside_container(monkeypatch):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return completed_process(stdout="1\n")

    monkeypatch.setattr(
        "phoenix.adapters.postgres.validation_adapter.subprocess.run",
        fake_run,
    )

    adapter = PostgresValidationAdapter()
    result = adapter.execute_scalar("container-123", "SELECT 1")

    command = captured["command"]

    assert result == "1"
    assert command[:4] == [
        "docker", "exec", "--user", "postgres"
    ]
    assert "container-123" in command
    assert "psql" in command
    assert "--no-psqlrc" in command
    assert "--quiet" in command
    assert "--tuples-only" in command
    assert "--set=ON_ERROR_STOP=1" in command
    assert "BEGIN TRANSACTION READ ONLY;" in command[-1]
    assert "SELECT 1" in command[-1]
    assert "COMMIT;" in command[-1]
    assert captured["kwargs"]["timeout"] == 30


def test_execute_scalar_uses_configured_database():
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return completed_process(stdout="1\n")

    # Patch subprocess for this test.
    import phoenix.adapters.postgres.validation_adapter as module

    original_run = module.subprocess.run
    module.subprocess.run = fake_run

    try:
        adapter = PostgresValidationAdapter(
            database_name="test_database",
            database_user="test_user",
        )
        adapter.execute_scalar("container-123", "SELECT 1")
    finally:
        module.subprocess.run = original_run

    command = captured["command"]

    assert "test_database" in command
    assert "test_user" in command


@pytest.mark.parametrize(
    "query",
    [
        "",
        "UPDATE users SET active = false",
        "DELETE FROM users",
        "SELECT 1; DROP TABLE users",
    ],
)
def test_execute_scalar_rejects_unsafe_queries(query):
    adapter = PostgresValidationAdapter()

    with pytest.raises(ValueError):
        adapter.execute_scalar("container-123", query)


def test_execute_scalar_rejects_empty_container_id():
    adapter = PostgresValidationAdapter()

    with pytest.raises(ValueError, match="Container ID"):
        adapter.execute_scalar("", "SELECT 1")


def test_execute_scalar_reports_postgres_errors(monkeypatch):
    monkeypatch.setattr(
        "phoenix.adapters.postgres.validation_adapter.subprocess.run",
        lambda *args, **kwargs: completed_process(
            returncode=1,
            stderr="relation does not exist",
        ),
    )

    adapter = PostgresValidationAdapter()

    with pytest.raises(RuntimeError, match="relation does not exist"):
        adapter.execute_scalar("container-123", "SELECT 1")


def test_execute_scalar_reports_timeout(monkeypatch):
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            cmd="docker exec",
            timeout=30,
        )

    monkeypatch.setattr(
        "phoenix.adapters.postgres.validation_adapter.subprocess.run",
        fake_run,
    )

    adapter = PostgresValidationAdapter()

    with pytest.raises(TimeoutError, match="exceeded its timeout"):
        adapter.execute_scalar("container-123", "SELECT 1")
