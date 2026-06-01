# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Reporting a vulnerability

**Do not** open a public GitHub issue for security vulnerabilities.

Email the maintainers with:

- Description and impact
- Steps to reproduce
- Affected component (webhook-ingress, dashboard-hub, orchestrator, etc.)

We aim to acknowledge reports within 72 hours.

## Security model

- **Webhook ingress** — HMAC signature verification for Slack, WhatsApp, and GitHub when `THEKEDAR_REQUIRE_WEBHOOK_SIGNATURE=true` (mandatory in staging/prod).
- **Dashboard API** — JWT bearer tokens with `tenant_id` claim; all widgets and approvals are tenant-scoped.
- **Secrets** — Never commit `.env`; production uses GCP Secret Manager.
- **MCP policy** — Tool allowlists enforced before GitHub side effects in the orchestrator.

## Hardening checklist for self-hosted deploys

- [ ] Set strong `THEKEDAR_JWT_SECRET`
- [ ] Enable `THEKEDAR_REQUIRE_WEBHOOK_SIGNATURE=true`
- [ ] Do not expose Postgres/Redis ports to the public internet
- [ ] Use HTTPS (reverse proxy or Cloud Run)
- [ ] Rotate Slack/GitHub/Jira tokens regularly

See also [docs/GA_CHECKLIST.md](docs/GA_CHECKLIST.md) for production gates.
