#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PILOT_DB="${MISI_PILOT_DB:-$ROOT_DIR/.runtime/false-alarm-pilot-v2.db}"
API_PORT="${MISI_PILOT_API_PORT:-8002}"
FRONTEND_PORT="${MISI_PILOT_FRONTEND_PORT:-3100}"

if [[ ! -f "$PILOT_DB" ]]; then
  echo "Pilot database not found: $PILOT_DB. See docs/VIRTUAL_SENSOR.md to create it."
  exit 1
fi
export APP_ENV=local
export DATABASE_URL="sqlite:///$PILOT_DB"
export CORS_ORIGINS="http://localhost:$FRONTEND_PORT,http://127.0.0.1:$FRONTEND_PORT"
export NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:$API_PORT"
cd "$ROOT_DIR"
"$ROOT_DIR/.venv/bin/python" -c 'from app.db import init_db; init_db()'
MISI_RCX_PID=""
if [[ -z "${RIGHTCLICK_X_URL:-}" && -f "$ROOT_DIR/.runtime/rightclick-x/bin/rcx.ts" ]]; then
  bash "$ROOT_DIR/scripts/rightclick-x-runtime.sh" &
  MISI_RCX_PID=$!
  for _ in {1..40}; do
    [[ -f "$ROOT_DIR/.runtime/rightclick-x.token" ]] && break
    sleep 0.1
  done
  if [[ -f "$ROOT_DIR/.runtime/rightclick-x.token" && ! -L "$ROOT_DIR/.runtime/rightclick-x.token" ]]; then
    export RIGHTCLICK_X_URL="http://127.0.0.1:8787/mcp"
    export RIGHTCLICK_X_TOKEN="$(cat "$ROOT_DIR/.runtime/rightclick-x.token")"
  fi
fi
"$ROOT_DIR/.venv/bin/python" -m uvicorn app.main:app --app-dir "$ROOT_DIR/backend" --host 127.0.0.1 --port "$API_PORT" &
MISI_PILOT_API_PID=$!
trap 'kill "$MISI_PILOT_API_PID" 2>/dev/null || true; [[ -z "$MISI_RCX_PID" ]] || kill "$MISI_RCX_PID" 2>/dev/null || true' EXIT INT TERM
pnpm --dir "$ROOT_DIR/frontend" dev --hostname 127.0.0.1 --port "$FRONTEND_PORT"
