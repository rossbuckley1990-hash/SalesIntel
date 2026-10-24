from pathlib import Path
import os
import sys

from sqlalchemy import func, select
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings  # noqa: E402
from app.db import SessionLocal, reset_db  # noqa: E402
from app.models import (  # noqa: E402
    BuyerProfile,
    CompetitorProfile,
    ExecutiveAction,
    FinanceForecast,
    MarketSignal,
    Opportunity,
    OpportunityAIAnalysis,
    SourceRun,
)

NON_SQLITE_RESET_OVERRIDE = "MISI_ALLOW_DESTRUCTIVE_RESET"


def _ensure_reset_is_allowed() -> None:
    database_url = get_settings().database_url
    url = make_url(database_url)
    if url.drivername.startswith("sqlite"):
        return

    if os.getenv(NON_SQLITE_RESET_OVERRIDE) == "true":
        return

    safe_url = url.render_as_string(hide_password=True)
    raise SystemExit(
        "Refusing to reset a non-SQLite database without explicit approval. "
        f"Active DATABASE_URL is {safe_url}. Set {NON_SQLITE_RESET_OVERRIDE}=true "
        "only if you intentionally want to drop and recreate that database."
    )


def _table_counts() -> dict[str, int]:
    models = {
        "opportunities": Opportunity,
        "market_signals": MarketSignal,
        "buyer_profiles": BuyerProfile,
        "competitor_profiles": CompetitorProfile,
        "executive_actions": ExecutiveAction,
        "finance_forecasts": FinanceForecast,
        "opportunity_ai_analyses": OpportunityAIAnalysis,
        "source_runs": SourceRun,
    }
    with SessionLocal() as db:
        return {
            table_name: db.scalar(select(func.count(model.id))) or 0
            for table_name, model in models.items()
        }


if __name__ == "__main__":
    _ensure_reset_is_allowed()
    reset_db()
    print("MiSi database reset to empty tables. No sample or demo data inserted.")
    print(f"Empty table counts: {_table_counts()}")
