#!/usr/bin/env bash
set -euo pipefail

deadline=$((SECONDS + 120))
until curl -sf "http://localhost:8080/health" >/dev/null 2>&1; do
  if (( SECONDS > deadline )); then
    echo "Timed out waiting for webhook-ingress"
    exit 1
  fi
  sleep 2
done

until curl -sf -X POST "http://localhost:8081/api/v1/auth/token" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id":"default"}' >/dev/null 2>&1; do
  if (( SECONDS > deadline )); then
    echo "Timed out waiting for dashboard-hub"
    exit 1
  fi
  sleep 2
done

echo "Services healthy."
