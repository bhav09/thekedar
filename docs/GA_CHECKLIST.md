# Thekedar Production GA Checklist (M6)

## Infrastructure
- [ ] Staging and prod Cloud Run services pass `/health` and `/ready`
- [ ] TLS certificates valid on public endpoints
- [ ] Secrets in GCP Secret Manager (not plain env values in prod)
- [ ] Cloud SQL private IP only; no public database access
- [ ] Terraform plan clean on main branch

## Messaging
- [ ] Slack app webhooks registered (events + interactivity)
- [ ] WhatsApp sandbox/production webhooks registered
- [ ] Signature verification enabled in prod (`SLACK_SIGNING_SECRET`, `WHATSAPP_APP_SECRET`)

## Orchestrator
- [ ] Pub/Sub inbound topic + DLQ configured in staging/prod
- [ ] Workspace rows mapped for each tenant (Slack team / WhatsApp phone ID)
- [ ] Jira credentials tested against staging (`@Architect list issues`)
- [ ] GitHub token scoped for branch/PR creation

## Dashboard
- [ ] D0–D3 widgets loading on Cloud Run dashboard-hub
- [ ] Approval API tested (`POST /api/v1/approvals/{id}/approve`)
- [ ] PWA manifest served over HTTPS

## Compute
- [ ] Cloud Workstation config IDs set per workspace
- [ ] Hibernation cron/job scheduled (`thekedar-orchestrator hibernate`)

## Testing gates
- [ ] Unit + e2e tests green in CI
- [ ] Load test: 100 concurrent webhooks p99 < 500ms (`scripts/load_test_webhooks.py`)
- [ ] DR restore drill completed this quarter

## Sign-off
- [ ] Engineering lead
- [ ] Security review (webhook secrets, MCP policy)
- [ ] On-call rotation documented
