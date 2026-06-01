#!/usr/bin/env bash
set -euo pipefail

curl -sS -X POST "http://localhost:8080/webhooks/slack" \
  -H "Content-Type: application/json" \
  -d '{
    "team_id": "T001",
    "event": {
      "type": "message",
      "user": "U_DEMO",
      "text": "Hello @Architect list open issues",
      "channel": "C_DEMO",
      "ts": "12345.678"
    }
  }'

echo ""
echo "Demo Slack message enqueued. Check dashboard at http://localhost:8081"
