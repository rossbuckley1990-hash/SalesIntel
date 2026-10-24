from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.ingestion.tracker_upload import (
    TrackerFileTooLargeError,
    UnsupportedTrackerFormatError,
    import_tracker_upload,
)
from app.schemas import TrackerImportSummary

router = APIRouter(prefix="/api", tags=["upload"])

UPLOAD_READ_CHUNK_BYTES = 1024 * 1024
ALLOWED_TRACKER_CONTENT_TYPES = {
    ".csv": {
        "application/csv",
        "application/octet-stream",
        "application/vnd.ms-excel",
        "text/csv",
        "text/plain",
    },
    ".xlsx": {
        "application/octet-stream",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    },
}


@router.post("/upload-tracker", response_model=TrackerImportSummary)
async def upload_tracker(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TrackerImportSummary:
    try:
        filename = _validate_tracker_upload_metadata(file)
        content = await _read_upload_with_limit(file, settings.max_upload_bytes)
        return import_tracker_upload(
            db,
            filename=filename,
            content=content,
            max_bytes=settings.max_upload_bytes,
        )
    except UnsupportedTrackerFormatError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except TrackerFileTooLargeError as exc:
        raise HTTPException(
            status_code=413,
            detail=str(exc),
        ) from exc


def _validate_tracker_upload_metadata(file: UploadFile) -> str:
    filename = file.filename or ""
    extension = Path(filename).suffix.lower()
    allowed_content_types = ALLOWED_TRACKER_CONTENT_TYPES.get(extension)
    if allowed_content_types is None:
        raise UnsupportedTrackerFormatError(
            "Unsupported tracker file type. Upload a .csv or .xlsx file."
        )

    content_type = (file.content_type or "").split(";", maxsplit=1)[0].strip().lower()
    if content_type and content_type not in allowed_content_types:
        raise UnsupportedTrackerFormatError(
            "Unsupported tracker content type. Upload a CSV or XLSX tracker file."
        )
    return filename


async def _read_upload_with_limit(file: UploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total_bytes = 0
    while chunk := await file.read(UPLOAD_READ_CHUNK_BYTES):
        total_bytes += len(chunk)
        if total_bytes > max_bytes:
            raise TrackerFileTooLargeError(
                f"Tracker upload exceeds the {_format_upload_limit(max_bytes)} limit."
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _format_upload_limit(max_bytes: int) -> str:
    limit_mb = max_bytes / (1024 * 1024)
    return f"{limit_mb:g}MB"
