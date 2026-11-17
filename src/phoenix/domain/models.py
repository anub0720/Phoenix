
"""Core domain models for Phoenix."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class BackupArtifact:
    """Represents a registered PostgreSQL backup artifact."""

    id: str
    display_name: str
    local_path: str
    format: str
    size_bytes: int
    checksum: str
    registered_at: datetime
