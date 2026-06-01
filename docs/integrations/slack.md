# Slack integration

## 1. Create a Slack app

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App**
2. Enable **Event Subscriptions** → Request URL: `https://YOUR-TUNNEL/webhooks/slack`
3. Subscribe to bot events: `message.channels`, `message.im` (as needed)
4. Enable **Interactivity** → Request URL: `https://YOUR-TUNNEL/webhooks/slack/interactive`

## 2. Scopes

Bot token scopes (minimum):

- `chat:write`
- `channels:history` (if listening in channels)

Install the app to your workspace and copy the **Bot User OAuth Token**.

## 3. Environment variables

```bash
SLACK_SIGNING_SECRET=...
SLACK_BOT_TOKEN=xoxb-...
```

Add to `.env` and restart services.

## 4. Workspace mapping

Set your Slack **Team ID** (`T…`) in `config/workspace.yaml`:

```yaml
slack_team_id: T01234567
```

## 5. Tunnel

```bash
./scripts/tunnel.sh
```

Register the HTTPS URL in Slack app settings.

## 6. Test

Send a channel message: `@Architect list open issues`

Check logs: `docker compose logs orchestrator-worker`
