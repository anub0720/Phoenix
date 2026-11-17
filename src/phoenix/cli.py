
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


def get_backup_service() -> BackupService:
    """Create the backup service with its SQLite adapter."""

    database_path = Path.home() / ".phoenix" / "phoenix.db"

    repository = SQLiteBackupRepository(database_path)

    return BackupService(repository)


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



if __name__ == "__main__":
    app()
