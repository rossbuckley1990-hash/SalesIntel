#!/usr/bin/env bash
# Hosted-mode browser acceptance: the real API with signed (development) tokens and workspaces,
# on an isolated synthetic database. No credentials, no paid calls (APP_ENV=demo refuses them).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p .runtime
TEST_DIR="$(mktemp -d "$ROOT/.runtime/hosted-e2e-XXXXXX")"
export APP_ENV=demo DATABASE_URL="sqlite:///$TEST_DIR/hosted.db" OPENAI_API_KEY='' ANTHROPIC_API_KEY=''
export CORS_ORIGINS='http://127.0.0.1:3101' NEXT_PUBLIC_API_BASE_URL='http://127.0.0.1:8012' NEXT_PUBLIC_AUTH_MODE=dev
# Research is replayed offline (synthetic pages, adversarial content included): no network, no API credit.
export RESEARCH_PROVIDER=replay RESEARCH_WORKER=inline
# Shared public notices are loaded as the single-user installer would; workspaces start empty.
AUTH_MODE=local PYTHONPATH=backend .venv/bin/python backend/scripts/salesintel_fixtures.py
AUTH_MODE=local PYTHONPATH=backend .venv/bin/python backend/scripts/shadow_fixtures.py   # real captured notices + one synthetic organisation
AUTH_MODE=dev .venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8012 &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT INT TERM
pnpm --dir frontend dev --hostname 127.0.0.1 --port 3101
