# Thekedar

Headless MCP orchestrator — connect WhatsApp, Slack, Jira, GitHub, and cloud dev environments so your agent keeps working while your laptop is closed.

Thekedar receives messages on public webhooks, ACKs fast, processes work asynchronously, and replies with summaries and PR links (never raw diffs in chat). A unified dashboard shows runs, ticket↔code traceability, approvals, cost, and audit trails.

## Architecture

```mermaid
flowchart TD
    Slack[Slack] --> Ingress[webhook-ingress]
    WhatsApp[WhatsApp] --> Ingress
    Ingress --> Redis[Redis queue]
    Redis --> Worker[orchestrator-worker]
    Worker --> Dashboard[dashboard-hub]
    Worker --> Jira[Jira API]
    Worker --> GitHub[GitHub API]
    Worker --> WS[Cloud Workstation]
```

## Quick start (5 minutes)

Requires [Docker](https://docs.docker.com/get-docker/) and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/bhav66d/thekedar.git
cd thekedar
./scripts/bootstrap.sh --demo
open http://localhost:8081
./scripts/send-demo-message.sh
```

Demo mode uses mock Jira/GitHub when tokens are not configured. See [docs/demo-mode.md](docs/demo-mode.md).

## Full local setup

```bash
uv sync --all-packages --dev
uv run thekedar init --yes --mode local-demo   # creates .env + config/workspace.yaml
docker compose up --build
uv run thekedar doctor
```

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:8081 |
| Webhook ingress | http://localhost:8080 |
| Health | http://localhost:8080/health |

## Connect real integrations

| Integration | Guide |
|-------------|-------|
| Slack | [docs/integrations/slack.md](docs/integrations/slack.md) |
| WhatsApp | [docs/integrations/whatsapp.md](docs/integrations/whatsapp.md) |
| Jira | [docs/integrations/jira.md](docs/integrations/jira.md) |
| GitHub | [docs/integrations/github.md](docs/integrations/github.md) |
| Multi-tenant workspaces | [docs/workspace-config.md](docs/workspace-config.md) |

Expose webhooks to the internet:

```bash
./scripts/tunnel.sh   # ngrok or cloudflared on port 8080
```

## Agent commands

Message these in Slack or WhatsApp (include the agent name or `@mention`):

| Agent | Example | What it does |
|-------|---------|--------------|
| `@Architect` | `@Architect list open issues` | Jira query / create |
| `@Architect` | `@Architect create issue: Auth hardening` | Create Jira task |
| `@Coder` | `@Coder fix THE-42 login bug` | Boot workstation → branch → PR |
| `@Status` | `@Status` | Snapshot of runs + workstation |

Include a Jira key (e.g. `THE-42`) for `@Coder` tasks. Keywords `merge`, `deploy`, or `force push` trigger an approval gate.

## CLI

```bash
uv run thekedar init          # interactive .env + workspace setup
uv run thekedar bootstrap     # sync deps + docker compose + doctor
uv run thekedar doctor        # health + credential checks
uv run thekedar mcp ping github
uv run thekedar-orchestrator hibernate   # idle workstation cleanup
```

Makefile shortcuts: `make demo`, `make test`, `make doctor`.

## Production (GCP)

Self-hosted Docker works for single-team deployments. For GCP (Cloud Run, GKE, Cloud Workstations), see [docs/deployment.md](docs/deployment.md).

## Configuration

All settings via environment variables — see [.env.example](.env.example). Run `uv run thekedar init` to generate a starter `.env`.

Key security settings:

| Variable | Purpose |
|----------|---------|
| `THEKEDAR_JWT_SECRET` | Dashboard + approval API auth (required in staging/prod) |
| `THEKEDAR_REQUIRE_WEBHOOK_SIGNATURE` | Reject unsigned Slack/WhatsApp/GitHub webhooks |
| `THEKEDAR_DEMO_MODE` | Mock integrations + relaxed auth for local eval |

## Development

```bash
uv run pytest tests -q
uv run ruff check packages tests
```

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Security

Report vulnerabilities per [SECURITY.md](SECURITY.md). Do not open public issues for security bugs.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
