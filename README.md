# Thekedar

Headless MCP Orchestrator — connect WhatsApp, Slack, Jira, GitHub, and Cloud Workstations so your digital contractor works while your laptop is closed.

## Status

**M1** — MCP policy engine, `thekedar mcp ping github` CLI, Bifrost docker-compose + K8s/Terraform skeleton.

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

# Verify MCP registry + policy (M1)
uv run thekedar mcp ping github

# Full local stack (Postgres + Redis + API + Bifrost)
docker compose up --build
# → Bifrost UI http://localhost:8090
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
