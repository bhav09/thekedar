# On-call runbook — webhook ingress down

## Symptoms
- Slack/WhatsApp messages not acknowledged
- `/health` returns non-200 on webhook-ingress Cloud Run service

## Immediate actions
1. Check Cloud Run revision status: `gcloud run services describe thekedar-webhook-ingress --region=us-central1`
2. Verify Redis and Postgres connectivity from the service VPC
3. Roll back to previous revision if a bad deploy landed in the last hour

## Escalation
- Page platform on-call if p99 ACK latency > 500ms for 5 minutes
