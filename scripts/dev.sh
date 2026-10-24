#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ ! -x "$ROOT_DIR/.venv/bin/uvicorn" ]; then
  echo "Backend dependencies are not installed. Run: python3 -m venv .venv && . .venv/bin/activate && python -m pip install -e \"backend[dev]\""
  exit 1
fi

if [ ! -d "$ROOT_DIR/frontend/node_modules" ]; then
  echo "Frontend dependencies are not installed. Run: pnpm install"
  exit 1
fi

cleanup() {
  jobs -p | xargs -r kill
}
trap cleanup EXIT

(
  cd "$ROOT_DIR"
  "$ROOT_DIR/.venv/bin/uvicorn" app.main:app --app-dir "$ROOT_DIR/backend" --reload --port 8000
) &

(
  cd "$ROOT_DIR/frontend"
  pnpm dev
) &

wait
