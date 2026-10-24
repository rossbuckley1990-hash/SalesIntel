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
        "competitor_profiles",
        "enrichment_runs",
        "executive_actions",
        "field_intelligence",
        "finance_forecasts",
        "market_signals",
        "opportunity_ai_analyses",
        "opportunity_enrichments",
        "opportunities",
        "source_runs",
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
