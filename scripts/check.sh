#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"$ROOT_DIR/.venv/bin/python" -m pytest "$ROOT_DIR/backend/tests"
CI="${CI:-true}" pnpm --dir "$ROOT_DIR/frontend" typecheck
CI="${CI:-true}" pnpm --dir "$ROOT_DIR/frontend" test
