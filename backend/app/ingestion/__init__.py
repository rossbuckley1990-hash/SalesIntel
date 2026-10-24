from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class UploadFormat(StrEnum):
    CSV = "csv"
    XLSX = "xlsx"


@dataclass(frozen=True)
class UploadManifest:
    source_path: Path
    upload_format: UploadFormat
    submitted_by: str


class IngestionNotImplementedError(NotImplementedError):
    """Raised when a planned ingestion path is called before implementation."""


def plan_upload(manifest: UploadManifest) -> dict[str, str]:
    return {
        "source_path": str(manifest.source_path),
        "upload_format": manifest.upload_format.value,
        "submitted_by": manifest.submitted_by,
        "status": "planned",
    }

