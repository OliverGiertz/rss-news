#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${BASE_URL:-}" ]]; then
  echo "BASE_URL fehlt (z. B. https://news.vanityontour.de)"
  exit 1
fi

if [[ -z "${APP_ADMIN_USERNAME:-}" || -z "${APP_ADMIN_PASSWORD:-}" ]]; then
  echo "APP_ADMIN_USERNAME/APP_ADMIN_PASSWORD fehlen"
  exit 1
fi

cookie_file="$(mktemp)"
trap 'rm -f "$cookie_file"' EXIT

echo "[1/4] Healthcheck"
curl -fsS "${BASE_URL}/health" | grep -q '"status":"ok"'

echo "[2/4] Login"
curl -fsS -c "$cookie_file" \
  -H "Content-Type: application/json" \
  -X POST "${BASE_URL}/auth/login" \
  -d "{\"username\":\"${APP_ADMIN_USERNAME}\",\"password\":\"${APP_ADMIN_PASSWORD}\"}" \
  | grep -q '"ok":true'

echo "[3/4] Protected Endpoint"
curl -fsS -b "$cookie_file" "${BASE_URL}/api/protected" | grep -q '"ok":true'

echo "[4/4] Pipeline Status"
curl -fsS -b "$cookie_file" "${BASE_URL}/api/pipeline/status" | grep -q '"stage":"skeleton+db"'

echo "Smoke test erfolgreich."
