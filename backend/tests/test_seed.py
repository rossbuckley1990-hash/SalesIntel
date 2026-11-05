import os
from pathlib import Path
import subprocess
import sys

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.db import Base, create_database_engine
from app.models import (
    BuyerProfile,
    CompetitorProfile,
    ExecutiveAction,
    FinanceForecast,
    MarketSignal,
    Opportunity,
)
from app.services.seed import seed_sample_data

EXPECTED_COUNTS = {
    "opportunities": 25,
    "market_signals": 15,
    "buyer_profiles": 10,
    "competitor_profiles": 8,
    "executive_actions": 15,
    "finance_forecasts": 12,
}


def test_seed_service_inserts_sample_records() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(bind=engine)

    with testing_session() as db:
        counts = seed_sample_data(db)

        assert counts == EXPECTED_COUNTS
        assert db.scalar(select(func.count(Opportunity.id))) == 25
        assert db.scalar(select(func.count(MarketSignal.id))) == 15
        assert db.scalar(select(func.count(BuyerProfile.id))) == 10
        assert db.scalar(select(func.count(CompetitorProfile.id))) == 8
        assert db.scalar(select(func.count(ExecutiveAction.id))) == 15
        assert db.scalar(select(func.count(FinanceForecast.id))) == 12
        assert db.scalar(select(func.count(func.distinct(FinanceForecast.start_month)))) == 12


def test_seed_script_inserts_sample_records(tmp_path: Path) -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "seed.db"
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_path}",
        "APP_ENV": "test",
        "PYTHONPATH": str(backend_dir),
    }

    result = subprocess.run(
        [sys.executable, "scripts/seed.py", "--reset"],
        cwd=backend_dir,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Inserted sample records" in result.stdout

    engine = create_database_engine(f"sqlite:///{db_path}")
    testing_session = sessionmaker(bind=engine)
    with testing_session() as db:
        assert db.scalar(select(func.count(Opportunity.id))) == 25
        assert db.scalar(select(func.count(MarketSignal.id))) == 15
        assert db.scalar(select(func.count(BuyerProfile.id))) == 10
        assert db.scalar(select(func.count(CompetitorProfile.id))) == 8
        assert db.scalar(select(func.count(ExecutiveAction.id))) == 15
        assert db.scalar(select(func.count(FinanceForecast.id))) == 12


def test_reset_empty_script_creates_empty_tables_without_demo_data(tmp_path: Path) -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "empty.db"
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_path}",
        "APP_ENV": "test",
        "PYTHONPATH": str(backend_dir),
    }

    result = subprocess.run(
        [sys.executable, "scripts/reset_empty.py"],
        cwd=backend_dir,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "No sample or demo data inserted" in result.stdout

    engine = create_database_engine(f"sqlite:///{db_path}")
    testing_session = sessionmaker(bind=engine)
    with testing_session() as db:
        assert db.scalar(select(func.count(Opportunity.id))) == 0
        assert db.scalar(select(func.count(MarketSignal.id))) == 0
        assert db.scalar(select(func.count(BuyerProfile.id))) == 0
        assert db.scalar(select(func.count(CompetitorProfile.id))) == 0
        assert db.scalar(select(func.count(ExecutiveAction.id))) == 0
        assert db.scalar(select(func.count(FinanceForecast.id))) == 0


def test_reset_empty_script_refuses_non_sqlite_without_override() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "DATABASE_URL": "postgresql://misi:secret@localhost:5432/misi",
        "PYTHONPATH": str(backend_dir),
        "MISI_ALLOW_DESTRUCTIVE_RESET": "",
    }

    result = subprocess.run(
        [sys.executable, "scripts/reset_empty.py"],
        cwd=backend_dir,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "Refusing to reset a non-SQLite database" in result.stderr
    assert "secret" not in result.stderr
