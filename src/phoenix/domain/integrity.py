from dataclasses import dataclass


@dataclass(frozen=True)
class IntegrityVerificationResult:
    verified: bool
    stored_checksum: str
    current_checksum: str