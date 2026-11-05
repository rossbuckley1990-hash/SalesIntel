#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"

check_endpoint() {
  local label="$1"
  local path="$2"

  printf "Checking %s... " "$label"
  curl --fail --silent --show-error "$API_BASE_URL$path" >/dev/null
  printf "ok\n"
}

check_endpoint "health" "/health"
check_endpoint "version" "/api/version"
check_endpoint "dashboard" "/api/dashboard"
check_endpoint "opportunities" "/api/opportunities"
check_endpoint "market signals" "/api/market-signals"
check_endpoint "executive actions" "/api/executive-actions"
check_endpoint "LE1 finance summary" "/api/finance-forecast/summary"
check_endpoint "executive report" "/api/reports/executive-summary"

printf "SalesIntel backend smoke test passed against %s\n" "$API_BASE_URL"
