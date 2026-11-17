
import subprocess
import uuid
from pathlib import Path
import time
from phoenix.domain.restoration import RestoreResult


class DockerRestoreAdapter:
    def __init__(
        self,
        image: str = "postgres:16",
        memory_limit: str = "1g",
        cpu_limit: float = 1.0,
        pids_limit: int = 100,
        readiness_timeout: int = 60,
        restore_timeout: int = 300,
    ):
        self.image = image
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit
        self.pids_limit = pids_limit
        self.readiness_timeout = readiness_timeout
        self.restore_timeout = restore_timeout

    def _create_container(
        self,
        backup_path: Path,
        container_name: str,
    ) -> str:
        """Create an isolated PostgreSQL container for restoration."""

        backup_path = backup_path.resolve()

        command = [
            "docker",
            "run",
            "-d",
            "--name", container_name,
            "--network", "none",
            "--read-only",
           "--cap-drop",
            "ALL",
            "--cap-add",
            "CHOWN",
            "--cap-add",
            "SETUID",
            "--cap-add",
            "SETGID",
            "--security-opt", "no-new-privileges",
            "--memory", self.memory_limit,
            "--cpus", str(self.cpu_limit),
            "--pids-limit", str(self.pids_limit),
            "--tmpfs", "/var/lib/postgresql/data:rw,noexec,nosuid,size=512m",
            "--tmpfs", "/var/run/postgresql:rw,noexec,nosuid,size=16m",
            "--mount",
            (
                f"type=bind,source={backup_path},"
                "target=/backup.dump,readonly"
            ),
            "-e", "POSTGRES_PASSWORD=phoenix_temporary_password",
            self.image,
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=self.readiness_timeout,
            check=False,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to create restore container: {result.stderr.strip()}"
            )

        return result.stdout.strip()
    

    def _wait_for_postgres(self, container_id: str) -> None:
        """Wait until PostgreSQL accepts connections inside the container."""

        deadline = time.monotonic() + self.readiness_timeout

        while time.monotonic() < deadline:
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    container_id,
                    "pg_isready",
                    "-U",
                    "postgres",
                ],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )

            if result.returncode == 0:
                return

            time.sleep(1)

        raise TimeoutError(
            "PostgreSQL did not become ready before the readiness timeout."
        )

    def _restore_database(self, container_id: str) -> None:
        """Create a destination database and restore the archive into it."""

        create_result = subprocess.run(
            [
                "docker",
                "exec",
                container_id,
                "createdb",
                "-U",
                "postgres",
                "phoenix_restore",
            ],
            capture_output=True,
            text=True,
            timeout=self.readiness_timeout,
            check=False,
        )

        if create_result.returncode != 0:
            raise RuntimeError(
                "Failed to create restore database: "
                f"{create_result.stderr.strip()}"
            )

        restore_result = subprocess.run(
            [
                "docker",
                "exec",
                container_id,
                "pg_restore",
                "-U",
                "postgres",
                "-d",
                "phoenix_restore",
                "--exit-on-error",
                "/backup.dump",
            ],
            capture_output=True,
            text=True,
            timeout=self.restore_timeout,
            check=False,
        )

        if restore_result.returncode != 0:
            raise RuntimeError(
                "PostgreSQL restore failed: "
                f"{restore_result.stderr.strip()}"
            )

    def _remove_container(self, container_id: str) -> None:
        """Forcefully remove a temporary restore container."""

        result = subprocess.run(
            [
                "docker",
                "rm",
                "-f",
                container_id,
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to remove restore container: {result.stderr.strip()}"
            )
    def restore(
        self,
        backup_path: Path,
        backup_name: str,
        diagnostic_mode: bool = False,
    ) -> RestoreResult:
        """Restore a backup inside an isolated PostgreSQL container."""

        started_at = time.monotonic()

        container_id = None
        success = False
        retained = False
        error_message = None

        try:
            backup_path = Path(backup_path).resolve()

            if not backup_path.exists():
                raise FileNotFoundError(
                    f"Backup file does not exist: {backup_path}"
                )

            if not backup_path.is_file():
                raise ValueError(
                    f"Backup path is not a file: {backup_path}"
                )

            container_name = f"phoenix-restore-{uuid.uuid4().hex[:12]}"

            container_id = self._create_container(
                backup_path,
                container_name,
            )

            self._wait_for_postgres(container_id)

            self._restore_database(container_id)

            success = True

        except Exception as error:
            error_message = str(error)

        finally:
            if container_id:
                if diagnostic_mode:
                    retained = True
                else:
                    try:
                        self._remove_container(container_id)
                    except Exception as cleanup_error:
                        retained = True
                        success = False

                        cleanup_message = (
                            f"Container cleanup failed: {cleanup_error}"
                        )

                        if error_message:
                            error_message += f"\n{cleanup_message}"
                        else:
                            error_message = cleanup_message

        duration = time.monotonic() - started_at

        return RestoreResult(
            success=success,
            backup_name=backup_name,
            container_id=container_id,
            duration_seconds=duration,
            error_message=error_message,
            retained=retained,
        )
