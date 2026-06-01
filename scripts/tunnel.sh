#!/usr/bin/env bash
set -euo pipefail

if command -v ngrok >/dev/null 2>&1; then
  echo "Starting ngrok tunnel on port 8080…"
  echo "Register these URLs in Slack/Meta:"
  echo "  Slack events:       https://YOUR-NGROK/webhooks/slack"
  echo "  Slack interactive:  https://YOUR-NGROK/webhooks/slack/interactive"
  echo "  WhatsApp:           https://YOUR-NGROK/webhooks/whatsapp"
  echo "  GitHub:             https://YOUR-NGROK/webhooks/github"
  exec ngrok http 8080
fi

if command -v cloudflared >/dev/null 2>&1; then
  echo "Starting cloudflared tunnel on port 8080…"
  exec cloudflared tunnel --url http://localhost:8080
fi

echo "Install ngrok or cloudflared to expose webhooks."
exit 1
