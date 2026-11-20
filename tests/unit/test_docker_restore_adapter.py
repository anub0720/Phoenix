
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from phoenix.adapters.docker_restore_adapter import (
    DockerRestoreAdapter,
)


def completed_process(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(
        args=[],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_create_container_returns_container_id(tmp_path, monkeypatch):
    backup_path = tmp_path / "backup.dump"
    backup_path.write_bytes(b"sample backup")

    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return completed_process(stdout="container-123\n")

    monkeypatch.setattr(
        "phoenix.adapters.docker_restore_adapter.subprocess.run",
        fake_run,
    )

    adapter = DockerRestoreAdapter()
    container_id = adapter._create_container(
        backup_path,
        "phoenix-test",
    )

    assert container_id == "container-123"

    command = captured["command"]

    assert "--network" in command
    assert "none" in command
    assert "--read-only" in command
    assert "--cap-drop" in command
    assert "ALL" in command
    assert "--memory" in command
    assert "--cpus" in command
    assert "--pids-limit" in command
    assert "--mount" in command
    assert [
        command[index:index + 2]
        for index, value in enumerate(command[:-1])
        if value == "--label"
    ] == [
        ["--label", "com.phoenix.managed=true"],
        ["--label", "com.phoenix.purpose=restore"],
    ]


def test_create_container_raises_when_docker_fails(
    tmp_path,
    monkeypatch,
):
    backup_path = tmp_path / "backup.dump"
    backup_path.write_bytes(b"sample backup")

    monkeypatch.setattr(
        "phoenix.adapters.docker_restore_adapter.subprocess.run",
        lambda *args, **kwargs: completed_process(
            returncode=1,
            stderr="Docker error",
        ),
    )

    adapter = DockerRestoreAdapter()

    with pytest.raises(RuntimeError, match="Docker error"):
        adapter._create_container(
            backup_path,
            "phoenix-test",
        )


def test_wait_for_postgres_retries_until_ready(monkeypatch):
    responses = [
        completed_process(returncode=1),
        completed_process(returncode=0),
        completed_process(returncode=0),
    ]
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        return responses.pop(0)

    monkeypatch.setattr(
        "phoenix.adapters.docker_restore_adapter.subprocess.run",
        fake_run,
    )

    monkeypatch.setattr(
        "phoenix.adapters.docker_restore_adapter.time.sleep",
        lambda seconds: None,
    )

    adapter = DockerRestoreAdapter()

    adapter._wait_for_postgres("container-123")

    assert len(commands) == 3


def test_restore_database_creates_and_restores_database(
    monkeypatch,
):
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        return completed_process()

    monkeypatch.setattr(
        "phoenix.adapters.docker_restore_adapter.subprocess.run",
        fake_run,
    )

    adapter = DockerRestoreAdapter()
    adapter._restore_database("container-123")

    assert len(commands) == 2
    assert "createdb" in commands[0]
    assert "pg_restore" in commands[1]
    assert "--exit-on-error" in commands[1]
    assert "phoenix_restore" in commands[1]


def test_restore_database_raises_when_pg_restore_fails(
    monkeypatch,
):
    responses = [
        completed_process(),
        completed_process(
            returncode=1,
            stderr="Archive restore failed",
        ),
    ]

    monkeypatch.setattr(
        "phoenix.adapters.docker_restore_adapter.subprocess.run",
        lambda *args, **kwargs: responses.pop(0),
    )

    adapter = DockerRestoreAdapter()

    with pytest.raises(RuntimeError, match="Archive restore failed"):
        adapter._restore_database("container-123")


def test_remove_container_calls_docker_rm(monkeypatch):
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        if command[1] == "inspect":
            return completed_process(stdout="true|restore\n")
        return completed_process()

    monkeypatch.setattr(
        "phoenix.adapters.docker_restore_adapter.subprocess.run",
        fake_run,
    )

    adapter = DockerRestoreAdapter()
    adapter._remove_container("container-123")

    assert commands == [
        [
            "docker",
            "inspect",
            "--format",
            '{{ index .Config.Labels "com.phoenix.managed" }}|'
            '{{ index .Config.Labels "com.phoenix.purpose" }}',
            "container-123",
        ],
        ["docker", "rm", "-f", "container-123"],
    ]


def test_remove_container_refuses_unmanaged_container(monkeypatch):
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        return completed_process(stdout="false|restore\n")

    monkeypatch.setattr(
        "phoenix.adapters.docker_restore_adapter.subprocess.run",
        fake_run,
    )

    adapter = DockerRestoreAdapter()

    with pytest.raises(RuntimeError, match="Refusing to remove"):
        adapter._remove_container("unmanaged-container")

    assert len(commands) == 1
    assert commands[0][1] == "inspect"


def test_successful_restore_removes_container(
    tmp_path,
    monkeypatch,
):
    backup_path = tmp_path / "backup.dump"
    backup_path.write_bytes(b"sample backup")

    adapter = DockerRestoreAdapter()

    monkeypatch.setattr(
        adapter,
        "_create_container",
        lambda path, name: "container-123",
    )
    monkeypatch.setattr(
        adapter,
        "_wait_for_postgres",
        lambda container_id: None,
    )
    monkeypatch.setattr(
        adapter,
        "_restore_database",
        lambda container_id: None,
    )

    removed = []
    monkeypatch.setattr(
        adapter,
        "_remove_container",
        lambda container_id: removed.append(container_id),
    )

    result = adapter.restore(
        backup_path,
        "test-backup",
    )

    assert result.success is True
    assert result.container_id == "container-123"
    assert result.retained is False
    assert result.error_message is None
    assert removed == ["container-123"]


def test_diagnostic_restore_retains_container(
    tmp_path,
    monkeypatch,
):
    backup_path = tmp_path / "backup.dump"
    backup_path.write_bytes(b"sample backup")

    adapter = DockerRestoreAdapter()

    monkeypatch.setattr(
        adapter,
        "_create_container",
        lambda path, name: "container-456",
    )
    monkeypatch.setattr(
        adapter,
        "_wait_for_postgres",
        lambda container_id: None,
    )
    monkeypatch.setattr(
        adapter,
        "_restore_database",
        lambda container_id: None,
    )

    removed = []
    monkeypatch.setattr(
        adapter,
        "_remove_container",
        lambda container_id: removed.append(container_id),
    )

    result = adapter.restore(
        backup_path,
        "test-backup",
        diagnostic_mode=True,
    )

    assert result.success is True
    assert result.retained is True
    assert removed == []


def test_failed_restore_still_removes_container(
    tmp_path,
    monkeypatch,
):
    backup_path = tmp_path / "backup.dump"
    backup_path.write_bytes(b"sample backup")

    adapter = DockerRestoreAdapter()

    monkeypatch.setattr(
        adapter,
        "_create_container",
        lambda path, name: "container-789",
    )
    monkeypatch.setattr(
        adapter,
        "_wait_for_postgres",
        lambda container_id: None,
    )

    def fail_restore(container_id):
        raise RuntimeError("Restore failed")

    monkeypatch.setattr(
        adapter,
        "_restore_database",
        fail_restore,
    )

    removed = []
    monkeypatch.setattr(
        adapter,
        "_remove_container",
        lambda container_id: removed.append(container_id),
    )

    result = adapter.restore(
        backup_path,
        "test-backup",
    )

    assert result.success is False
    assert "Restore failed" in result.error_message
    assert removed == ["container-789"]


def test_missing_backup_does_not_create_container(
    tmp_path,
    monkeypatch,
):
    adapter = DockerRestoreAdapter()

    def unexpected_create(*args, **kwargs):
        pytest.fail("Container should not be created")

    monkeypatch.setattr(
        adapter,
        "_create_container",
        unexpected_create,
    )

    result = adapter.restore(
        tmp_path / "missing.dump",
        "missing-backup",
    )

    assert result.success is False
    assert "does not exist" in result.error_message
    assert result.container_id is None


def test_cleanup_failure_is_reported(
    tmp_path,
    monkeypatch,
):
    backup_path = tmp_path / "backup.dump"
    backup_path.write_bytes(b"sample backup")

    adapter = DockerRestoreAdapter()

    monkeypatch.setattr(
        adapter,
        "_create_container",
        lambda path, name: "container-cleanup",
    )
    monkeypatch.setattr(
        adapter,
        "_wait_for_postgres",
        lambda container_id: None,
    )
    monkeypatch.setattr(
        adapter,
        "_restore_database",
        lambda container_id: None,
    )

    def fail_cleanup(container_id):
        raise RuntimeError("Docker could not remove container")

    monkeypatch.setattr(
        adapter,
        "_remove_container",
        fail_cleanup,
    )

    result = adapter.restore(
        backup_path,
        "test-backup",
    )

    assert result.success is False
    assert result.retained is True
    assert "cleanup failed" in result.error_message.lower()
def test_restore_password_is_generated():
    adapter = DockerRestoreAdapter()

    password = adapter._generate_restore_password()

    assert password
    assert len(password) >= 32
def test_restore_passwords_are_unique():
    adapter = DockerRestoreAdapter()

    password_1 = adapter._generate_restore_password()
    password_2 = adapter._generate_restore_password()

    assert password_1 != password_2