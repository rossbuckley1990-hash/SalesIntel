#!/usr/bin/env bash
# The blind review, run locally by whoever runs the evaluation.
#
# What it starts:
# - the real app, on this Mac only (127.0.0.1);
# - on a fresh, private database that holds nothing but review decisions;
# - with no credentials and no paid calls (APP_ENV=demo refuses them; research is replayed offline).
#
# Who uses what:
# - Reviewers never use this. They get offline review packs, downloaded from it.
# - The private key stays in ~/.salesintel/evaluation until you reveal it, after the review is locked.
#
#   scripts/evaluation-server.sh [path/to/review.db]      (default: ~/.salesintel/evaluation/review.db)
#   then open http://127.0.0.1:3051 and go to Blind review.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
DB="${1:-$HOME/.salesintel/evaluation/review.db}"
mkdir -p "$(dirname "$DB")"
chmod 700 "$(dirname "$DB")"
export APP_ENV=demo DATABASE_URL="sqlite:///$DB" OPENAI_API_KEY= ANTHROPIC_API_KEY=
export CORS_ORIGINS='http://127.0.0.1:3051' NEXT_PUBLIC_API_BASE_URL='http://127.0.0.1:8051' NEXT_PUBLIC_AUTH_MODE=dev
export RESEARCH_PROVIDER=replay RESEARCH_WORKER=inline
AUTH_MODE=dev PYTHONPATH=backend .venv/bin/alembic -c backend/alembic.ini upgrade head
AUTH_MODE=dev .venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8051 &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT INT TERM
pnpm --dir frontend dev --hostname 127.0.0.1 --port 3051
