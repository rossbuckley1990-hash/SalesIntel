"""Migration 0020 on an existing single-user database, and parity with the models, on SQLite and PostgreSQL."""
from datetime import UTC, datetime
import json
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, inspect, text

from app.config import get_settings
from app.db import Base
import app.models  # noqa: F401
from scripts.db_preflight import reconcile
from tenancy_support import BACKENDS, database, require_postgres_in_ci

ALEMBIC = Config(str(Path(__file__).parents[1] / "alembic.ini"))
NOW = datetime(2026, 11, 5, tzinfo=UTC).isoformat()


def migrate(url: str, monkeypatch, target: str, down: bool = False):
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    (command.downgrade if down else command.upgrade)(ALEMBIC, target)
    get_settings.cache_clear()


def url_of(engine) -> str:
    return engine.url.render_as_string(hide_password=False)


def seed_single_user_records(engine):
    """What a SalesIntel 2.0 install holds at revision 0019."""
    with engine.begin() as c:
        account = c.execute(text("INSERT INTO si_accounts (name, key, kind, company_number, status, watched, notes, created_at, updated_at) "
                                 "VALUES ('Orbit Group', 'orbit group', 'private', '01234567', 'prospect', false, '', :t, :t) RETURNING id"), {"t": NOW}).scalar()
        c.execute(text("INSERT INTO si_account_links (account_id, entity_type, entity_id, name_seen, basis, confirmed, created_at) "
                       "VALUES (:a, 'market_opportunity', 7, 'ORBIT', 'created_from', true, :t)"), {"a": account, "t": NOW})
        c.execute(text("INSERT INTO si_deals (opportunity_id, account_id, title, stage, origin, services, work_type, qualification, value_basis, next_step, "
                       "scope, quote, handover, outcome_reason, created_at, updated_at) VALUES (42, :a, 'PPM', 'qualify', '{}', '[]', '', '{}', 'unknown', '', "
                       "'{}', '{}', '{}', '', :t, :t)"), {"a": account, "t": NOW})
        c.execute(text("INSERT INTO si_preferences (key, value) VALUES ('territory', :v)"), {"v": json.dumps(["Yorkshire"])})
        c.execute(text("INSERT INTO prospects (dedup_key, name, status, data, created_at, updated_at) VALUES ('orbit', 'Orbit', 'new', '{}', :t, :t)"), {"t": NOW})


@pytest.mark.parametrize("kind", BACKENDS)
def test_existing_records_move_into_the_local_workspace_and_nothing_is_lost(kind, tmp_path, monkeypatch):
    require_postgres_in_ci()
    with database(kind, tmp_path) as engine:
        url = url_of(engine)
        migrate(url, monkeypatch, "0019_salesintel_crm")
        seed_single_user_records(engine)
        migrate(url, monkeypatch, "head")
        with engine.connect() as c:
            assert c.execute(text("SELECT id, slug FROM organisations")).all() == [(1, "local")]
            for table in ("si_accounts", "si_account_links", "si_deals", "prospects", "si_preferences"):
                assert c.execute(text(f"SELECT DISTINCT organisation_id FROM {table}")).scalars().all() == [1], table
            assert c.execute(text("SELECT opportunity_id FROM si_deals")).scalar() == 42
            assert json.loads(c.execute(text("SELECT value FROM si_preferences WHERE key = 'territory'")).scalar()) == ["Yorkshire"] \
                if kind == "sqlite" else c.execute(text("SELECT value FROM si_preferences WHERE key = 'territory'")).scalar() == ["Yorkshire"]
        # A second company may now hold the same company number; the same workspace still may not.
        with engine.begin() as c:
            org = c.execute(text("INSERT INTO organisations (name, slug, industry, created_at) VALUES ('Beta', 'beta', 'fire_and_security', :t) RETURNING id"), {"t": NOW}).scalar()
            assert org == 2  # the sequence was advanced past the local workspace
            c.execute(text("INSERT INTO si_accounts (organisation_id, name, key, kind, company_number, status, watched, notes, created_at, updated_at) "
                           "VALUES (:o, 'Orbit Group', 'orbit group', 'private', '01234567', 'prospect', false, '', :t, :t)"), {"o": org, "t": NOW})
        with pytest.raises(Exception), engine.begin() as c:
            c.execute(text("INSERT INTO si_accounts (organisation_id, name, key, kind, company_number, status, watched, notes, created_at, updated_at) "
                           "VALUES (1, 'Dup', 'dup', 'private', '01234567', 'prospect', false, '', :t, :t)"), {"t": NOW})
        # Downgrading would mix two companies' records, so it is refused while another workspace exists.
        with pytest.raises(RuntimeError, match="other workspaces exist"):
            migrate(url, monkeypatch, "0019_salesintel_crm", down=True)
        with engine.begin() as c:
            c.execute(text("DELETE FROM organisations WHERE id = 2"))  # PostgreSQL cascades to its records
        if kind == "sqlite":  # SQLite does not enforce the cascade, so the orphaned record still blocks a downgrade
            with pytest.raises(RuntimeError, match="other workspaces exist"):
                migrate(url, monkeypatch, "0019_salesintel_crm", down=True)
            with engine.begin() as c:
                c.execute(text("DELETE FROM si_accounts WHERE organisation_id = 2"))
        else:
            with engine.connect() as c:
                assert c.execute(text("SELECT COUNT(*) FROM si_accounts WHERE organisation_id = 2")).scalar() == 0
        migrate(url, monkeypatch, "0019_salesintel_crm", down=True)
        migrate(url, monkeypatch, "head")
        with engine.connect() as c:
            assert c.execute(text("SELECT COUNT(*) FROM si_accounts")).scalar() == 1


def _shape(engine) -> dict:
    insp = inspect(engine)
    shape = {}
    for table in insp.get_table_names():
        if table == "alembic_version":
            continue
        shape[table] = {
            "columns": {c["name"]: (str(c["type"]).split("(")[0].upper(), c["nullable"]) for c in insp.get_columns(table)},
            "unique": sorted(tuple(u["column_names"]) for u in insp.get_unique_constraints(table)),
            "fks": sorted((tuple(f["constrained_columns"]), f["referred_table"]) for f in insp.get_foreign_keys(table)),
            "pk": tuple(insp.get_pk_constraint(table)["constrained_columns"]),
        }
    return shape


@pytest.mark.parametrize("kind", BACKENDS)
def test_migrated_schema_matches_the_models(kind, tmp_path, monkeypatch):
    require_postgres_in_ci()
    with database(kind, tmp_path) as migrated:
        migrate(url_of(migrated), monkeypatch, "head")
        (tmp_path / "m").mkdir()
        with database(kind, tmp_path / "m") as models:
            Base.metadata.create_all(models)
            want, have = _shape(models), _shape(migrated)
            tenant = [t for t in ("si_accounts", "si_account_links", "si_sites", "si_contacts", "si_drafts", "si_activities", "si_tasks", "si_deals",
                                  "si_saved_views", "si_funnel_events", "si_preferences", "si_lead_states", "prospects", "prospect_searches",
                                  "organisations", "users", "memberships", "invitations", "si_audit_events")]
            for table in tenant:
                assert have[table]["columns"] == want[table]["columns"], table
                assert have[table]["unique"] == want[table]["unique"], table
                assert have[table]["pk"] == want[table]["pk"], table
                assert {fk for fk in have[table]["fks"]} == {fk for fk in want[table]["fks"]}, table
            assert set(have) == set(want)
        if kind == "sqlite":
            db_file = Path(migrated.url.database)
            other = tmp_path / "models.db"
            e = create_engine(f"sqlite:///{other}")
            Base.metadata.create_all(e)
            e.dispose()
            assert reconcile(other, db_file)["stamp_safe"] is True
