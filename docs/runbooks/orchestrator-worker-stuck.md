# On-call runbook — orchestrator worker stuck

## Symptoms
- Messages ACK'd but no replies
- Redis queue depth growing (`LLEN thekedar:queue:inbound`)

## Immediate actions
1. Inspect orchestrator-worker logs for LangGraph or DB errors
2. Restart worker deployment (Cloud Run job or GKE pod)
3. Check DLQ / poison messages after 3 retries

## Recovery
- Reprocess idempotent messages only after fixing root cause
- Confirm workspace seed data exists for tenant mapping
