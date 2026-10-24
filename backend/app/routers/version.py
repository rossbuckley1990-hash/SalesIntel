from fastapi import APIRouter

from app.config import get_settings
from app.schemas.version import VersionResponse

router = APIRouter(prefix="/api", tags=["version"])


@router.get("/version", response_model=VersionResponse)
def version() -> VersionResponse:
    settings = get_settings()
    return VersionResponse(
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
    )

