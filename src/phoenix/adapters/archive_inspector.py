
"""PostgreSQL archive inspection using Docker."""

import subprocess

from pathlib import Path

from phoenix.domain.inspection import ArchiveInspectionResult


class PostgresArchiveInspector:
    """Inspects PostgreSQL custom-format archives."""

    def __init__(
        self,
        image: str = "postgres:16",
        timeout_seconds: int = 60,
    ):
        self.image = image
        self.timeout_seconds = timeout_seconds

    def inspect(self, archive_path: Path) -> ArchiveInspectionResult:
        """Inspect an archive using pg_restore --list."""

        archive_path = archive_path.expanduser().resolve()

        if not archive_path.exists():
            raise FileNotFoundError(
                f"Backup file does not exist: {archive_path}"
            )

        if not archive_path.is_file():
            raise ValueError(
                f"Backup path is not a file: {archive_path}"
            )

        command = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--mount",
            (
                "type=bind,"
                f"source={archive_path},"
                "target=/backup.dump,"
                "readonly"
            ),
            self.image,
            "pg_restore",
            "--list",
            "/backup.dump",
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )

        except subprocess.TimeoutExpired:
            return ArchiveInspectionResult(
                valid=False,
                archive_path=str(archive_path),
                postgres_version=self.image,
                object_count=0,
                archive_listing="",
                error_message="Archive inspection timed out.",
            )

        except FileNotFoundError:
            raise RuntimeError(
                "Docker executable was not found. "
                "Ensure Docker Desktop is installed and available in PATH."
            )

        if result.returncode != 0:
            return ArchiveInspectionResult(
                valid=False,
                archive_path=str(archive_path),
                postgres_version=self.image,
                object_count=0,
                archive_listing="",
                error_message=result.stderr.strip()
                or "PostgreSQL archive inspection failed.",
            )

        listing = result.stdout

        object_count = sum(
            1
            for line in listing.splitlines()
            if line.strip()
            and not line.lstrip().startswith(";")
        )

        return ArchiveInspectionResult(
            valid=True,
            archive_path=str(archive_path),
            postgres_version=self.image,
            object_count=object_count,
            archive_listing=listing,
        )
