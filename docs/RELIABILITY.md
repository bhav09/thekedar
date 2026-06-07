# Thekedar Reliability (M8)

Production-grade resilience: durable runs, DLQ replay, outbound outbox, fail-closed config, and SLO-oriented observability.

## SLO targets

| SLO | Target |
|-----|--------|
| Webhook ACK | p99 < 500ms |
| Run completion visibility | 95% first outbound within 5 min |
| Dashboard API | p99 < 2s |
| Data durability | RPO 5 min (Cloud SQL PITR) |
| Message durability | 0 lost after ACK (Pub/Sub + DLQ steady-state) |

## Architecture

- **Inbound:** Webhook ingress ACKs fast → Pub/Sub (staging/prod) or Redis queue (local)
- **Run ledger:** `run_steps` in PostgreSQL is source of truth; Redis checkpoint is cache
- **DLQ:** Failed worker processing → dead letter → `thekedar ops replay-dlq`
- **Outbox:** Slack/WhatsApp replies persisted in `outbound_notifications` with retry
- **Resilience:** `packages/resilience` — retry, circuit breaker, provider health registry

## Fail-closed production

In `staging` / `prod`:

- `THEKEDAR_DEMO_MODE=false` (enforced at startup)
- `THEKEDAR_LLM_PROVIDER=mock` blocked
- Missing GitHub/Jira/Slack tokens → `IntegrationError`, not silent mocks
- Default workspace seed (`T001`) only when `THEKEDAR_ALLOW_DEFAULT_SEED=true` and `local`

Validate before deploy:

```bash
uv run thekedar doctor --strict
```

## Operator runbooks

### DLQ depth > 0

1. Inspect: `redis-cli LLEN thekedar:queue:dlq` (local) or Cloud Monitoring alert
2. Dry-run replay: `uv run thekedar ops replay-dlq --dry-run`
3. Replay: `uv run thekedar ops replay-dlq --max-messages 50`
4. If poison message: fix worker, mark row failed in `dlq_messages`, skip replay

### Outbox stuck

1. Query `outbound_notifications` where `status='pending_retry'`
2. Check provider circuit state (Redis key `thekedar:circuit:slack_api`)
3. Worker drains outbox each loop; scale worker if backlog grows

### Worker crash mid-run

1. Pub/Sub redelivers message (or Redis message lost — use Pub/Sub in prod)
2. Worker uses `run_steps` idempotency; resume from last completed step
3. Redis checkpoint rebuilt from SQL on cache miss

### Approval/Resume Failure Runbook

If a human approval is submitted via the dashboard or Slack but the worker fails to resume the run:

1. **Verify Signature:** Check the worker logs for "Rejected resume event: invalid signature". This indicates a signature mismatch, usually caused by mismatched `THEKEDAR_JWT_SECRET` values across services. Ensure all services use the exact same secret.
2. **Check Redis Queue:** Inspect the resume queue length: `redis-cli LLEN thekedar:queue:resume`.
3. **Manual Re-trigger:** If the resume event was rejected or lost, the operator can manually re-trigger the resume by publishing a signed resume payload using the helper script `scripts/sign-resume.py`.

### Quarterly DR drill

```bash
./scripts/dr-drill.sh
```

## Configuration

See `.env.example` for M8 variables:

- `THEKEDAR_STRICT_INTEGRATIONS`
- `THEKEDAR_PROVIDER_RETRY_MAX`
- `THEKEDAR_OUTBOX_MAX_ATTEMPTS`
- `THEKEDAR_LLM_PRIMARY` / `THEKEDAR_LLM_FALLBACK`
- `THEKEDAR_OTEL_ENABLED`

## Demo vs production boundary

Demo mocks (`THE-42`, fake PR `/pull/1`, log-only Slack) run **only** when `THEKEDAR_DEMO_MODE=true` and `THEKEDAR_ENVIRONMENT=local`. See [demo-mode.md](demo-mode.md).
