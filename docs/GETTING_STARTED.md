# Getting Started

This guide walks through local setup, first message, and troubleshooting.

## Prerequisites

- Docker Desktop (or Docker Engine + Compose)
- [uv](https://docs.astral.sh/uv/) for Python tooling
- Optional: [ngrok](https://ngrok.com/) or `cloudflared` for webhook tunnels

## Step 1 — Bootstrap

```bash
./scripts/bootstrap.sh --demo
```

This will:

1. Run `uv sync --all-packages --dev`
2. Create `.env` via `thekedar init` if missing
3. Start Postgres, Redis, webhook-ingress, orchestrator-worker, dashboard-hub
4. Wait for health checks

## Step 2 — Open the dashboard

Visit http://localhost:8081. The PWA fetches a JWT automatically in demo mode.

## Step 3 — Send a demo message

```bash
./scripts/send-demo-message.sh
```

Within a few seconds the orchestrator worker processes the message and you should see activity on the dashboard.

## Step 4 — Verify with doctor

```bash
uv run thekedar doctor
```

Optional integrations (Slack, Jira, GitHub) show as skipped until configured.

## Connect Slack (optional)

1. Create a Slack app — see [integrations/slack.md](integrations/slack.md)
2. Run `./scripts/tunnel.sh` and register the ngrok URL
3. Add `SLACK_SIGNING_SECRET` and `SLACK_BOT_TOKEN` to `.env`
4. Restart: `docker compose up -d --build`

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Dashboard shows "auth error" | Ensure dashboard-hub is running; check `THEKEDAR_DEMO_MODE=true` |
| No reply after demo message | Check `docker compose logs orchestrator-worker` |
| Webhook 401 | Set `SLACK_SIGNING_SECRET` or disable `THEKEDAR_REQUIRE_WEBHOOK_SIGNATURE` locally |
| Doctor fails on dashboard | Wait for services: `./scripts/wait-for-services.sh` |

## Next steps

- [workspace-config.md](workspace-config.md) — map Slack team IDs to tenants
- [deployment.md](deployment.md) — GCP production path
- [demo-mode.md](demo-mode.md) — what works without external accounts
