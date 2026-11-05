from pathlib import Path

from sqlalchemy import inspect

from app.config import REPO_ROOT
from app.db import Base, create_database_engine
import app.models  # noqa: F401


def test_models_create_against_sqlite() -> None:
    engine = create_database_engine("sqlite:///:memory:")

    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    assert set(inspector.get_table_names()) == {
        "buyer_profiles",
        "organisations",
        "users",
        "memberships",
        "invitations",
        "si_audit_events",
        "si_lead_states",
        "si_research_jobs",
        "si_spend_budgets",
        "si_idempotency",
        "si_suppressions",
        "shadow_hypotheses",
        "shadow_hypothesis_revisions",
        "si_dossiers",
        "si_lead_feedback",
        "si_gap_requests",
        "si_review_decisions",
        "competitor_profiles",
        "enrichment_runs",
        "evidence_observations",
        "executive_actions",
        "field_intelligence",
        "finance_forecasts",
        "lfb_import_runs",
        "lfb_inspection_matches",
        "lfb_incidents",
        "market_signals",
        "market_source_states",
        "market_source_revisions",
        "market_entities",
        "market_awards",
        "market_entity_evidence",
        "market_relationships",
        "market_opportunities",
        "market_contracts",
        "market_contract_links",
        "market_observations",
        "market_hypotheses",
        "market_hypothesis_revisions",
        "market_opportunity_revisions",
        "market_opportunity_dossiers",
        "prospect_searches",
        "prospects",
        "si_account_links",
        "si_accounts",
        "si_activities",
        "si_contacts",
        "si_deals",
        "si_drafts",
        "si_funnel_events",
        "si_preferences",
        "si_saved_views",
        "si_sites",
        "si_tasks",
        "opportunity_ai_analyses",
        "opportunity_enrichments",
        "opportunities",
        "public_site_references",
        "research_contact_snapshots",
        "research_leads",
        "research_lead_actions",
        "research_investigations",
        "research_lead_feedback",
        "saved_research_runs",
        "source_runs",
        "living_assets",
        "living_action_details",
        "living_audit_events",
        "living_decisions",
        "living_evidence_reviews",
        "living_import_previews",
        "living_outcomes",
        "living_requirements",
        "living_scenarios",
        "living_snapshots",
    }


def test_relative_sqlite_database_urls_resolve_from_repo_root() -> None:
    engine = create_database_engine("sqlite:///./misi-demo-test.db")

    assert Path(engine.url.database).is_absolute()
    assert Path(engine.url.database) == REPO_ROOT / "misi-demo-test.db"


def test_bare_postgresql_urls_use_psycopg_driver() -> None:
    engine = create_database_engine("postgresql://misi:secret@localhost:5432/misi")

    assert engine.url.drivername == "postgresql+psycopg"
    assert engine.dialect.name == "postgresql"
    assert engine.dialect.driver == "psycopg"
    assert engine.pool._pre_ping is True

    engine.dispose()


def test_postgres_url_alias_is_supported() -> None:
    engine = create_database_engine("postgres://misi:secret@localhost:5432/misi")

    assert engine.url.drivername == "postgresql+psycopg"

    engine.dispose()
