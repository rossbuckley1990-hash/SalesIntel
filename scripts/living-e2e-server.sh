#!/usr/bin/env bash
set -euo pipefail
MISI_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$MISI_ROOT"
mkdir -p .runtime
MISI_TEST_DIR="$(mktemp -d "$MISI_ROOT/.runtime/e2e-XXXXXX")"
export APP_ENV=demo DATABASE_URL="sqlite:///$MISI_TEST_DIR/living-demo.db" OPENAI_API_KEY=''
export CORS_ORIGINS='http://127.0.0.1:3100' NEXT_PUBLIC_API_BASE_URL='http://127.0.0.1:8011'
.venv/bin/python backend/scripts/living_demo.py
PYTHONPATH=backend .venv/bin/python backend/scripts/salesintel_fixtures.py
PYTHONPATH=backend .venv/bin/python backend/scripts/atlas_fixtures.py   # a fictional market for Contract Atlas
PYTHONPATH=backend .venv/bin/python backend/scripts/living_fixtures.py  # a fictional depot programme and a live tender
.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8011 &
MISI_API_PID=$!
trap 'kill "$MISI_API_PID" 2>/dev/null || true' EXIT INT TERM
pnpm --dir frontend dev --hostname 127.0.0.1 --port 3100
