# Demo mode

When `THEKEDAR_DEMO_MODE=true` (default in local Docker Compose):

- **Jira** returns mock issues (`THE-1`, `THE-42`) if `JIRA_*` vars are unset
- **GitHub** simulates branch/PR creation if `GITHUB_TOKEN` is unset
- **Workstation** boot/sync/test runs in simulation (no GCP required)
- **Dashboard auth** uses a local-only JWT secret; `/api/v1/auth/token` issues tokens without bootstrap secret
- **Outbound Slack/WhatsApp** logs replies instead of sending when tokens are missing

Demo mode is intended for evaluation and CI. For team or production use:

```bash
uv run thekedar init --mode local-live
# or
uv run thekedar init --mode gcp
```

Set `THEKEDAR_DEMO_MODE=false` and configure real integration tokens.
