#!/usr/bin/env bash
# MiSi on this Mac's real database. Local data has no login, so this binds to this machine only.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
export APP_ENV=local
export DATABASE_URL="sqlite:///$ROOT_DIR/.runtime/false-alarm-pilot-v2.db"
export CORS_ORIGINS='http://localhost:3000,http://127.0.0.1:3000'
export NEXT_PUBLIC_API_BASE_URL='http://127.0.0.1:8001'
"$ROOT_DIR/.venv/bin/python" -m uvicorn app.main:app --app-dir "$ROOT_DIR/backend" --host 127.0.0.1 --port 8001 &
MISI_API_PID=$!
trap 'kill "$MISI_API_PID" 2>/dev/null || true' EXIT INT TERM
pnpm --dir "$ROOT_DIR/frontend" dev --hostname 127.0.0.1 --port 3000
