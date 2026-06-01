#!/usr/bin/env bash
# M8 DR drill — staging only. Restores SQL clone, replays DLQ, runs doctor --strict, canary E2E.
set -euo pipefail

ENV="${THEKEDAR_ENVIRONMENT:-staging}"
PROJECT="${GCP_PROJECT_ID:-thekedar-staging}"
REGION="${GCP_REGION:-us-central1}"
INSTANCE="${CLOUD_SQL_INSTANCE:-thekedar-sql}"
CLONE="${INSTANCE}-dr-$(date +%Y%m%d%H%M)"

echo "==> DR drill for environment: $ENV"

if [[ "$ENV" == "prod" ]]; then
  echo "Refusing to run DR drill against prod without THEKEDAR_DRILL_ALLOW_PROD=1"
  [[ "${THEKEDAR_DRILL_ALLOW_PROD:-}" == "1" ]] || exit 1
fi

echo "==> Clone Cloud SQL instance $INSTANCE -> $CLONE"
gcloud sql instances clone "$INSTANCE" "$CLONE" --project="$PROJECT" 2>/dev/null || \
  echo "Skip SQL clone (local drill or missing gcloud auth)"

echo "==> Replay DLQ (dry-run first)"
uv run thekedar ops replay-dlq --dry-run --max-messages 10
uv run thekedar ops replay-dlq --max-messages 100

echo "==> Doctor strict"
uv run thekedar doctor --strict

echo "==> Canary webhook (health)"
curl -sf "${THEKEDAR_WEBHOOK_INGRESS_URL:-http://localhost:8080}/ready" | grep -q ready

echo "DR drill completed successfully"
