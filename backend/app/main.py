from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers.buyers import router as buyers_router
from app.routers.competitors import router as competitors_router
from app.routers.dashboard import router as dashboard_router
from app.routers.enrichment import router as enrichment_router
from app.routers.executive_actions import router as executive_actions_router
from app.routers.finance_forecasts import router as finance_forecasts_router
from app.routers.health import router as health_router
from app.routers.intelligence import router as intelligence_router
from app.routers.market_signals import router as market_signals_router
from app.routers.opportunities import router as opportunities_router
from app.routers.reports import router as reports_router
from app.routers.sources import router as sources_router
from app.routers.upload import router as upload_router
from app.routers.version import router as version_router


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        description="Backend API for Mitie Sales Intelligence.",
        version=settings.app_version,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health_router)
    application.include_router(version_router)
    application.include_router(opportunities_router)
    application.include_router(market_signals_router)
    application.include_router(buyers_router)
    application.include_router(competitors_router)
    application.include_router(executive_actions_router)
    application.include_router(finance_forecasts_router)
    application.include_router(dashboard_router)
    application.include_router(enrichment_router)
    application.include_router(reports_router)
    application.include_router(intelligence_router)
    application.include_router(upload_router)
    application.include_router(sources_router)
    return application


app = create_app()
