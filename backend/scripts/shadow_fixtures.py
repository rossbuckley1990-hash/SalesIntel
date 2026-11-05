"""Load the Shadow Radar fixtures into DATABASE_URL (see app/services/shadow_fixtures.py)."""
from sqlalchemy.orm import Session

from app.db import Base, engine
import app.models  # noqa: F401
from app.services.shadow_fixtures import load
from app.tenancy import SYSTEM

Base.metadata.create_all(engine)
with Session(engine) as db:
    db.info[SYSTEM] = True
    print(load(db))
    db.commit()
