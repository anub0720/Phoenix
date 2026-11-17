
from dataclasses import dataclass


@dataclass(frozen=True)
class RestoreResult:
    success: bool
    backup_name: str
    container_id: str | None
    duration_seconds: float
    error_message: str | None = None
    retained: bool = False
