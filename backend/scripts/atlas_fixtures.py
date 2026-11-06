"""Load the fictional Contract Atlas market into the configured database (browser tests and screenshots only)."""
from app.db import SessionLocal
from app.services.atlas_fixtures import load

if __name__ == '__main__':
    with SessionLocal() as db:
        print(load(db))
        db.commit()
