from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.db import init_db  # noqa: E402


if __name__ == "__main__":
    init_db()
    print("Database tables are up to date.")

