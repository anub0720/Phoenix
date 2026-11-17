
import pytest

from pathlib import Path
from unittest.mock import patch, MagicMock

from phoenix.adapters.postgres.archive_inspector import (
    PostgresArchiveInspector,
)


def test_missing_archive_is_rejected(tmp_path):
    inspector = PostgresArchiveInspector()

    with pytest.raises(FileNotFoundError):
        inspector.inspect(tmp_path / "missing.dump")


@patch("phoenix.adapters.postgres.archive_inspector.subprocess.run")
def test_successful_archive_inspection(mock_run, tmp_path):
    backup = tmp_path / "valid.dump"
    backup.write_bytes(b"dummy backup")

    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=(
            "; Archive created at 2026-11-12\n"
            "1; 1259 16384 TABLE public users postgres\n"
            "2; 1259 16385 TABLE public orders postgres\n"
        ),
        stderr="",
    )

    inspector = PostgresArchiveInspector()

    result = inspector.inspect(backup)

    assert result.valid is True
    assert result.object_count == 2


@patch("phoenix.adapters.postgres.archive_inspector.subprocess.run")
def test_invalid_archive_returns_failure(mock_run, tmp_path):
    backup = tmp_path / "invalid.dump"
    backup.write_bytes(b"invalid data")

    mock_run.return_value = MagicMock(
        returncode=1,
        stdout="",
        stderr="pg_restore: error: input file does not appear to be a valid archive",
    )

    inspector = PostgresArchiveInspector()

    result = inspector.inspect(backup)

    assert result.valid is False
    assert "valid archive" in result.error_message
