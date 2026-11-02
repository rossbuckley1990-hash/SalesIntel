from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import REPO_ROOT, get_settings


class Base(DeclarativeBase):
    pass


def create_database_engine(database_url: str | None = None) -> Engine:
    active_database_url = _normalise_database_url(database_url or get_settings().database_url)
    return create_engine(active_database_url, **_engine_options_for_url(active_database_url))


def _normalise_database_url(database_url: str) -> str:
    url = make_url(database_url)
    url = _normalise_postgresql_driver(url)
    if url.drivername.startswith("sqlite") and url.database and url.database != ":memory:":
        database_path = Path(url.database)
        if not database_path.is_absolute():
            url = url.set(database=str((REPO_ROOT / database_path).resolve()))
    return url.render_as_string(hide_password=False)


def _normalise_postgresql_driver(url: URL) -> URL:
    if url.drivername in {"postgres", "postgresql"}:
        return url.set(drivername="postgresql+psycopg")
    return url


def _engine_options_for_url(database_url: str) -> dict[str, object]:
    url = make_url(database_url)
    if url.drivername.startswith("sqlite"):
        # Several workers share one file, so a writer waits instead of failing.
        return {"connect_args": {"check_same_thread": False, "timeout": 60}}
    if url.drivername.startswith("postgresql"):
        return {"pool_pre_ping": True}
    return {}


engine = create_database_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "sqlite":
        _apply_lightweight_schema_compatibility(engine)


def reset_db() -> None:
    import app.models  # noqa: F401

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _apply_lightweight_schema_compatibility(bind: Engine) -> None:
    inspector = inspect(bind)
    table_names = set(inspector.get_table_names())

    if "market_signals" in table_names:
        market_signal_columns = {
            column["name"] for column in inspector.get_columns("market_signals")
        }
        if "source_attribution" not in market_signal_columns:
            with bind.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE market_signals "
                        "ADD COLUMN source_attribution TEXT DEFAULT '' NOT NULL"
                    )
                )
        if "likely_mitie_fit" not in market_signal_columns:
            with bind.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE market_signals "
                        "ADD COLUMN likely_mitie_fit VARCHAR(40) DEFAULT 'Unknown' NOT NULL"
                    )
                )
        if "potential_disciplines" not in market_signal_columns:
            with bind.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE market_signals "
                        "ADD COLUMN potential_disciplines JSON DEFAULT '[]' NOT NULL"
                    )
                )
        if "ai_rationale" not in market_signal_columns:
            with bind.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE market_signals "
                        "ADD COLUMN ai_rationale TEXT DEFAULT '' NOT NULL"
                    )
                )

    if "field_intelligence" in table_names:
        field_intelligence_columns = {
            column["name"] for column in inspector.get_columns("field_intelligence")
        }
        if "recommended_next_step" not in field_intelligence_columns:
            with bind.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE field_intelligence "
                        "ADD COLUMN recommended_next_step TEXT DEFAULT '' NOT NULL"
                    )
                )
