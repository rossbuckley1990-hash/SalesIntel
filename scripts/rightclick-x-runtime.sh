#!/usr/bin/env bash
set -euo pipefail

# Isolated local runtime. The operator-owned policy permits only the reviewed
# Planning Data England provider and GET capability. No demo or CLI authority.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RCX_DIR="$ROOT_DIR/.runtime/rightclick-x"
TOKEN_FILE="$ROOT_DIR/.runtime/rightclick-x.token"
if [[ ! -f "$RCX_DIR/bin/rcx.ts" ]]; then
  echo "The local source-discovery runtime is not installed. See docs/PUBLIC_SOURCE_NETWORK.md."
  exit 1
fi
if ! "$ROOT_DIR/.venv/bin/python" -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 8787)); s.close()' 2>/dev/null; then
  echo "Source-discovery port 8787 is already in use; no runtime was started or seeded."
  exit 1
fi
mkdir -p "$ROOT_DIR/.runtime/rightclick-workspace"
if [[ -L "$TOKEN_FILE" ]]; then
  echo "Refusing a symlink for the source-discovery token file."
  exit 1
fi
if [[ ! -f "$TOKEN_FILE" ]]; then
  umask 077
  "$ROOT_DIR/.venv/bin/python" -c 'import secrets,sys; open(sys.argv[1], "x").write(secrets.token_urlsafe(32))' "$TOKEN_FILE"
fi
chmod 600 "$TOKEN_FILE"
export RCX_TOKEN="$(cat "$TOKEN_FILE")"
export RCX_NAME="misi-public-discovery"
export RCX_STATE_FILE="$ROOT_DIR/.runtime/rightclick-x-state.json"
export RCX_WORKSPACE="$ROOT_DIR/.runtime/rightclick-workspace"
export RCX_EXECUTION_POLICY='{"allowedRisks":["read"],"allowedProviders":["openapi:planning-data-gov-uk-api"],"allowedCapabilities":["openapi:planning-data-gov-uk-api:search-entities-entity-extension-get"],"allowedOrigins":["https://www.planning.data.gov.uk","https://api.apis.guru","https://registry.modelcontextprotocol.io"]}'
unset OPENAI_API_KEY ANTHROPIC_API_KEY RCX_AUTH RCX_INVESTIGATE RCX_EXECUTE RCX_APPROVE RCX_RETRY RCX_ENVIRONMENT
cd "$RCX_DIR"
node bin/rcx.ts serve --host 127.0.0.1 --port 8787 &
RCX_SERVER_PID=$!
trap 'kill "$RCX_SERVER_PID" 2>/dev/null || true' EXIT INT TERM
"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/scripts/rightclick-x-seed.py" "$TOKEN_FILE" || true
wait "$RCX_SERVER_PID"
