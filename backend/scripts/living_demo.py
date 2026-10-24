"""Create/reopen only the explicitly selected synthetic demo database."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from alembic import command
from alembic.config import Config
from app.config import get_settings
from app.db import SessionLocal
from app.services.living.demo import seed_living_demo

settings = get_settings()
if (
    settings.app_env != "demo"
    or not settings.database_url.startswith("sqlite:///")
    or not settings.database_url.endswith("living-demo.db")
):
    raise SystemExit("Use APP_ENV=demo and a separate SQLite living-demo.db path.")
command.upgrade(
    Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head"
)
with SessionLocal() as db:
    added = seed_living_demo(db)
print(
    "Synthetic demonstration prepared."
    if added
    else "Existing demonstration reopened; records preserved."
)
