
"""Domain models for PostgreSQL archive inspection."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ArchiveInspectionResult:
    """Represents the result of inspecting a PostgreSQL archive."""

    valid: bool
    archive_path: str
    postgres_version: str
    object_count: int
    archive_listing: str
    error_message: str | None = None
