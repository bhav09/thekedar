# Architecture

Thekedar is a **cloud-deployed** multi-connector orchestrator. See the full blueprint in the repo plan or `project.md`.

## Layers

1. **Ingress** — Cloud LB → `webhook-ingress` (fast ACK)
2. **Async pipeline** — Pub/Sub → `orchestrator-worker` (M2)
3. **Intelligence** — LangGraph + Bifrost MCP gateway on GKE (M1)
4. **Project management** — Atlassian Rovo MCP / Plane (M3)
5. **Compute** — Cloud Workstations (M5)
6. **Dashboard** — Hub API + PWA + Slack App Home (M2+)

## Local vs deployed

| | Local (`docker compose`) | Self-hosted Docker | Staging / Prod (GCP) |
|---|---|---|---|
| Purpose | Dev / demo | Single-team production | Managed scale |
| Webhooks | ngrok tunnel | Your TLS reverse proxy | `api.yourdomain.com` |
| Secrets | `.env` | `.env` or vault | Secret Manager |
| Auth | Demo JWT or configured secret | JWT required | JWT + webhook signatures required |

## OSS topology

Contributors typically run the **local-first** path: Postgres + Redis + three Python services (ingress, worker, dashboard). Bifrost MCP is optional (`docker compose --profile mcp up`).

Production GCP adds Pub/Sub, Cloud Run, GKE (Bifrost), and Cloud Workstations — see [deployment.md](deployment.md).

## MCP topology (M1+)

```
orchestrator-worker → Bifrost (GKE) → GitHub MCP sidecar
                                    → Atlassian Rovo MCP (remote)
                                    → shell/filesystem (Workstation only)
```

## ADRs

Architecture decision records live in `docs/adr/` (added as decisions are made).
