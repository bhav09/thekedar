#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DEMO=false
for arg in "$@"; do
  case "$arg" in
    --demo) DEMO=true ;;
  esac
done

if [[ ! -f .env ]]; then
  echo "No .env found — running thekedar init --yes --mode local-demo"
  uv run thekedar init --yes --mode local-demo
fi

if [[ "$DEMO" == true ]]; then
  export THEKEDAR_DEMO_MODE=true
fi

uv sync --all-packages --dev
docker compose up -d --build postgres redis webhook-ingress orchestrator-worker dashboard-hub

"$ROOT/scripts/wait-for-services.sh"

echo ""
echo "Thekedar is up."
echo "  Dashboard:  http://localhost:8081"
echo "  Webhooks:   http://localhost:8080/webhooks/slack"
echo ""
echo "Send a demo message:"
echo "  ./scripts/send-demo-message.sh"
