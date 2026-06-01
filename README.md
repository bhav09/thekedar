# Thekedar

Headless MCP Orchestrator — connect WhatsApp, Slack, Jira, GitHub, and Cloud Workstations so your digital contractor works while your laptop is closed.

## Status

**M0** — Foundation scaffold with deployable `webhook-ingress` service (`/health`, `/ready`).

## Quick start (local dev)

Requires [uv](https://docs.astral.sh/uv/) and Docker.

```bash
# Install Python dependencies
uv sync --all-packages --dev

# Run tests
uv run pytest tests/unit -v

# Run API locally
uv run thekedar-webhook-ingress
# → http://localhost:8080/health

# Full local stack (Postgres + Redis + API)
docker compose up --build
```

## Project structure

```
packages/
  shared/            # Settings, schemas, middleware
  webhook-ingress/   # Public HTTPS ingress (M0)
  orchestrator/      # LangGraph worker (M2)
  message-adapter/   # WhatsApp + Slack (M2)
  ...
infra/terraform/     # GCP staging + prod
docs/                # Architecture & deployment guides
```

## Deployment

Production runs on **Google Cloud** (Cloud Run, GKE, Cloud Workstations). See [docs/deployment.md](docs/deployment.md).

M0 gate: `https://staging-api.thekedar.app/health` returns 200 after CI deploy.

## Configuration

All config via environment variables — see [.env.example](.env.example). Production secrets live in **GCP Secret Manager**.

## License

TBD
