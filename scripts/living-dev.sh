#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
mkdir -p .runtime
export APP_ENV=demo
export DATABASE_URL="sqlite:///$ROOT_DIR/.runtime/living-demo.db"
export OPENAI_API_KEY=''
export CORS_ORIGINS='http://localhost:3000,http://127.0.0.1:3000,http://localhost:3100,http://127.0.0.1:3100'
export NEXT_PUBLIC_API_BASE_URL='http://127.0.0.1:8001'
"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/backend/scripts/living_demo.py"
"$ROOT_DIR/.venv/bin/python" -m uvicorn app.main:app --app-dir "$ROOT_DIR/backend" --host 127.0.0.1 --port 8001 &
MISI_API_PID=$!
trap 'kill "$MISI_API_PID" 2>/dev/null || true' EXIT INT TERM
if [[ "${MISI_FRONTEND_MODE:-development}" == "production" ]]; then
  pnpm --dir "$ROOT_DIR/frontend" build
  pnpm --dir "$ROOT_DIR/frontend" start --hostname 127.0.0.1 --port "${MISI_FRONTEND_PORT:-3000}"
else
  pnpm --dir "$ROOT_DIR/frontend" dev --hostname 127.0.0.1 --port "${MISI_FRONTEND_PORT:-3000}"
fi
