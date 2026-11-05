from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers.buyers import router as buyers_router
from app.routers.competitors import router as competitors_router
from app.routers.dashboard import router as dashboard_router
from app.routers.enrichment import router as enrichment_router
from app.routers.evidence_observations import router as evidence_observations_router
from app.routers.executive_actions import router as executive_actions_router
from app.routers.finance_forecasts import router as finance_forecasts_router
from app.routers.health import router as health_router
from app.routers.intelligence import router as intelligence_router
from app.routers.universal_research_jobs import router as universal_research_jobs_router
from app.routers.market_signals import router as market_signals_router
from app.routers.opportunities import router as opportunities_router
from app.routers.reports import router as reports_router
from app.routers.sources import router as sources_router
from app.routers.upload import router as upload_router
from app.routers.version import router as version_router
from app.routers.living import router as living_router
from app.routers.virtual_sensor import router as virtual_sensor_router
from app.routers.site_research import router as site_research_router
from app.routers.public_contacts import router as public_contacts_router
from app.routers.public_estates import router as public_estates_router
from app.routers.rightclick_x import router as rightclick_x_router
from app.routers.research_dossiers import router as research_dossiers_router
from app.routers.public_sources import router as public_sources_router
from app.routers.evidence_graph import router as evidence_graph_router
from app.routers.research_investigations import router as research_investigations_router
from app.routers.market_opportunities import router as market_opportunities_router
from app.routers.prospects import router as prospects_router
from app.routers.market_cross_source import router as market_cross_source_router
from app.routers.market_network import router as market_network_router


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        description="Backend API for SalesIntel.",
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
    application.include_router(evidence_observations_router)
    application.include_router(virtual_sensor_router)
    application.include_router(site_research_router)
    application.include_router(reports_router)
    application.include_router(intelligence_router)
    application.include_router(public_contacts_router)
    application.include_router(public_estates_router)
    application.include_router(rightclick_x_router)
    application.include_router(research_dossiers_router)
    application.include_router(evidence_graph_router)
    application.include_router(research_investigations_router)
    application.include_router(market_opportunities_router)
    application.include_router(prospects_router)
    application.include_router(market_cross_source_router)
    application.include_router(market_network_router)
    application.include_router(public_sources_router)
    application.include_router(universal_research_jobs_router)
    application.include_router(upload_router)
    application.include_router(sources_router)
    application.include_router(living_router)
    return application


app = create_app()
