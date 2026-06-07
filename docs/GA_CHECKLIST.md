# Thekedar Production GA Checklist

## Compute & Workstation Infrastructure (M5 completed)
- [x] Staging and prod GCP Cloud Workstations API enabled and provisioned via Terraform
- [x] Workstation clusters and configurations configured with Code-OSS images
- [x] Persistent disks (GCE PD 50GB) mapped to developer home directories
- [x] Hourly Workstation hibernation scheduler job configured (`thekedar-orchestrator hibernate`)
- [x] Standard `infra/workstation/bootstrap.sh` script provisioning git, python, uv, and AI CLI agents

## IDE Integration & Task Queue (M7 completed)
- [x] Bidirectional task execution queue with `ide_tasks` database table
- [x] Real-time task creation broadcasts via WebSocket connections
- [x] VS Code Client Extension claiming, executing, and reporting task outcomes
- [x] Command-line doctor check (`thekedar doctor`) verifying workstation clusters reachability
- [x] Pluggable remote command execution over SSH-over-IAP (`gcloud workstations ssh`)

## Context Harness & Freshness Contract (M9 completed)
- [x] Strict SHA gate blocking stale context coding in staging and production
- [x] Conversational freshness bypass override (`"override"`) approved
- [x] Targeted background git-push indexing jobs enqueued from GitHub webhook endpoints
- [x] Prompt isolation via sanitization tags preventing injection vectors
- [x] Retrieval evaluation golden suite with 50 unique queries passing in CI

## General Infrastructure
- [x] Staging and prod Cloud Run services pass `/health` and `/ready`
- [x] TLS certificates valid on public endpoints
- [x] Secrets in GCP Secret Manager (not plain env values in prod)
- [x] Cloud SQL private IP only; no public database access
- [x] Terraform plan clean on main branch

## Messaging & Webhook Ingress
- [x] Slack app webhooks registered (events + interactivity)
- [x] WhatsApp sandbox/production webhooks registered
- [x] Signature verification enabled in prod (`SLACK_SIGNING_SECRET`, `WHATSAPP_APP_SECRET`)

## Testing Gates
- [x] Full unit + evaluation test suites green in CI
- [x] Staging chaos tests verified
- [x] Load test: 100 concurrent webhooks p99 < 500ms
- [x] DR restore drill completed this quarter

## Sign-off
- [ ] Engineering Lead
- [ ] Security Review (webhook secrets, MCP policy)
- [ ] On-call rotation documented
