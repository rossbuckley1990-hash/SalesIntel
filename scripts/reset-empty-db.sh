#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ ! -x "$ROOT_DIR/.venv/bin/python" ]; then
  echo "Python virtual environment is missing. Run:"
  echo "  python3 -m venv .venv"
  echo "  . .venv/bin/activate"
  echo "  python -m pip install -e \"backend[dev]\""
  exit 1
fi

"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/backend/scripts/reset_empty.py"
