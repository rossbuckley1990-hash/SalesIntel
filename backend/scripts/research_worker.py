"""Run durable research jobs outside the API process (RESEARCH_WORKER=off on the API)."""
import time

from app.db import engine
import app.models  # noqa: F401
from app.services import research_handlers  # noqa: F401
from app.services.jobs import run_one

if __name__ == "__main__":
    while True:
        if run_one(engine) is None:
            time.sleep(1)
