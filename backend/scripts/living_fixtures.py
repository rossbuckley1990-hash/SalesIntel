"""Load the fictional Living Opportunity records (Fernhill Parcels, Ashby Vale Council) into an isolated test database.

Browser tests and screenshots only. It refuses to run unless APP_ENV is demo, so it can never write fictional records
into a real workspace."""
import os
import sys

from app.db import Base, SessionLocal, engine
import app.models  # noqa: F401
from app.services.living_fixtures import load

if os.environ.get("APP_ENV") != "demo":
    sys.exit("living_fixtures.py only runs with APP_ENV=demo")

if __name__ == '__main__':
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        print(load(db))
        db.commit()
