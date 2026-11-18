
"""Phoenix command-line interface."""

from pathlib import Path

import typer

from phoenix import __version__
from phoenix.backup.service import BackupService
from phoenix.adapters.sqlite_backup_repository import (
    SQLiteBackupRepository,
)
from phoenix.adapters.postgres.archive_inspector import (
    PostgresArchiveInspector,
)
from phoenix.restore.service import (
    RestoreService,
    BackupIntegrityError,
)
from phoenix.adapters.docker_restore_adapter import DockerRestoreAdapter

app = typer.Typer(
    name="phoenix",
    help="Automated PostgreSQL recovery testing.",
    no_args_is_help=True,
)

backup_app = typer.Typer(
    name="backup",
    help="Manage PostgreSQL backup artifacts.",
    no_args_is_help=True,
)

app.add_typer(backup_app, name="backup")
restore_app = typer.Typer(
    name="restore",
    help="Manage PostgreSQL restore environments.",
    no_args_is_help=True,
)

app.add_typer(restore_app, name="restore")

def get_backup_service() -> BackupService:
    """Create the backup service with its SQLite adapter."""

    database_path = Path.home() / ".phoenix" / "phoenix.db"

    repository = SQLiteBackupRepository(database_path)

    return BackupService(repository)
def get_restore_service() -> RestoreService:
    """Create the restore service and its dependencies."""

    backup_service = get_backup_service()
    restore_adapter = DockerRestoreAdapter()

    return RestoreService(
        backup_service=backup_service,
        restore_adapter=restore_adapter,
    )

@app.command()
def version():
    """Display Phoenix version."""
    typer.echo(f"Phoenix v{__version__}")


@backup_app.command("register")
def register_backup(
    path: Path = typer.Argument(
        ...,
        help="Path to the PostgreSQL backup file.",
        exists=False,
    ),
    name: str = typer.Option(
        ...,
        "--name",
        "-n",
        help="Display name for this backup.",
    ),
):
    """Register a PostgreSQL backup artifact."""

    service = get_backup_service()

    try:
        artifact = service.register_backup(path, name)

        typer.secho(
            f"Backup '{artifact.display_name}' registered successfully.",
            fg=typer.colors.GREEN,
        )

        typer.echo(f"ID: {artifact.id}")
        typer.echo(f"Size: {artifact.size_bytes:,} bytes")
        typer.echo(f"SHA-256: {artifact.checksum}")

    except (FileNotFoundError, ValueError) as error:
        typer.secho(str(error), fg=typer.colors.RED)
        raise typer.Exit(code=1)


@backup_app.command("list")
def list_backups():
    """List registered backup artifacts."""

    service = get_backup_service()
    backups = service.list_backups()

    if not backups:
        typer.echo("No backups registered.")
        return

    for backup in backups:
        typer.echo(
            f"{backup.display_name} | "
            f"{backup.format} | "
            f"{backup.size_bytes:,} bytes | "
            f"{backup.id}"
        )


@backup_app.command("verify")
def verify_backup(
    name: str = typer.Argument(
        ...,
        help="Registered backup name.",
    ),
):
    """Verify a registered backup's integrity."""

    service = get_backup_service()

    try:
        result = service.verify_backup_integrity(name)

        typer.echo(f"Backup: {name}\n")

        if result.verified:
            typer.secho(
                "INTEGRITY: PASS",
                fg=typer.colors.GREEN,
            )
        else:
            typer.secho(
                "INTEGRITY: FAIL",
                fg=typer.colors.RED,
            )

        typer.echo(f"Stored checksum:  {result.stored_checksum}")
        typer.echo(f"Current checksum: {result.current_checksum}")

        if not result.verified:
            typer.echo(
                "\nWARNING: Backup has changed since registration."
            )
            raise typer.Exit(code=1)

    except (LookupError, FileNotFoundError) as error:
        typer.secho(str(error), fg=typer.colors.RED)
        raise typer.Exit(code=1)



@backup_app.command("inspect")
def inspect_backup(
    name: str = typer.Argument(
        ...,
        help="Registered backup name.",
    ),
):
    """Inspect backup integrity and PostgreSQL archive structure."""

    service = get_backup_service()
    inspector = PostgresArchiveInspector()

    try:
        # Check 1: Verify file integrity.
        integrity = service.verify_backup_integrity(name)

        typer.echo(f"Backup: {name}\n")

        if integrity.verified:
            typer.secho(
                "INTEGRITY: PASS",
                fg=typer.colors.GREEN,
            )
        else:
            typer.secho(
                "INTEGRITY: FAIL",
                fg=typer.colors.RED,
            )

        typer.echo(
            f"Stored checksum:  {integrity.stored_checksum}"
        )
        typer.echo(
            f"Current checksum: {integrity.current_checksum}"
        )

        # Check 2: Inspect PostgreSQL archive structure.
        result = service.inspect_backup(name, inspector)

        if result.valid:
            typer.secho(
                "\nARCHIVE INSPECTION: PASS",
                fg=typer.colors.GREEN,
            )

            typer.echo(f"Path: {result.archive_path}")
            typer.echo(f"Image: {result.postgres_version}")
            typer.echo(f"Objects found: {result.object_count}")

            typer.echo("\nArchive contents:\n")
            typer.echo(result.archive_listing)

        else:
            typer.secho(
                "\nARCHIVE INSPECTION: FAIL",
                fg=typer.colors.RED,
            )
            typer.echo(result.error_message)

        # Overall result: both checks must pass.
        if not integrity.verified or not result.valid:
            raise typer.Exit(code=1)

    except (LookupError, FileNotFoundError) as error:
        typer.secho(str(error), fg=typer.colors.RED)
        raise typer.Exit(code=1)


@backup_app.command("restore")
def restore_backup(
    name: str = typer.Argument(
        ...,
        help="Registered backup name to restore.",
    ),
    diagnostic: bool = typer.Option(
        False,
        "--diagnostic",
        help="Retain the temporary container for investigation.",
    ),
):
    """Restore a registered PostgreSQL backup in an isolated container."""

    service = get_restore_service()

    typer.echo(f"Starting restore for '{name}'...")

    try:
        result = service.restore_backup(
            display_name=name,
            diagnostic_mode=diagnostic,
        )

    except (LookupError, FileNotFoundError, BackupIntegrityError) as error:
        typer.secho(
            f"RESTORE ABORTED: {error}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    typer.echo(f"\nBackup: {result.backup_name}")
    typer.echo(f"Duration: {result.duration_seconds:.2f} seconds")

    if result.success:
        typer.secho(
            "\nRESTORE: SUCCESS",
            fg=typer.colors.GREEN,
        )
    else:
        typer.secho(
            "\nRESTORE: FAILED",
            fg=typer.colors.RED,
        )
        if result.error_message:
            typer.echo(f"Error: {result.error_message}")

    if result.container_id:
        typer.echo(f"Container ID: {result.container_id}")

    if result.retained:
        typer.secho(
            "Container retained for investigation.",
            fg=typer.colors.YELLOW,
        )
    else:
        typer.echo("Temporary container cleaned up.")

    if not result.success:
        raise typer.Exit(code=1)

@restore_app.command("cleanup")
def cleanup_restore_containers(
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip the confirmation prompt.",
    ),
):
    """Remove containers owned by Phoenix restore operations."""

    adapter = DockerRestoreAdapter()

    try:
        container_ids = adapter.list_managed_containers()

        if not container_ids:
            typer.echo("No Phoenix restore containers found.")
            return

        typer.echo(
            f"Found {len(container_ids)} Phoenix restore container(s):"
        )

        for container_id in container_ids:
            typer.echo(f"  {container_id}")

        if not yes:
            confirmed = typer.confirm(
                "Remove these containers?",
                default=False,
            )
            if not confirmed:
                typer.echo("Cleanup cancelled.")
                return

        removed = adapter.cleanup_managed_containers()

        typer.secho(
            f"Removed {len(removed)} container(s).",
            fg=typer.colors.GREEN,
        )

    except RuntimeError as error:
        typer.secho(str(error), fg=typer.colors.RED)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
