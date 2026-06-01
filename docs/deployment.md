# Deployment Guide

## Self-hosted Docker (recommended for OSS / single team)

Run Thekedar on any VM or Kubernetes cluster with Docker Compose:

```bash
uv run thekedar init --mode local-live
docker compose up -d --build
./scripts/tunnel.sh   # for Slack/WhatsApp webhooks
```

Hardening:

- Set `THEKEDAR_DEMO_MODE=false`
- Set `THEKEDAR_JWT_SECRET` and `THEKEDAR_REQUIRE_WEBHOOK_SIGNATURE=true`
- Put nginx/Caddy in front for TLS
- Do not expose Postgres/Redis publicly

See [SECURITY.md](../SECURITY.md) and [docs/GA_CHECKLIST.md](GA_CHECKLIST.md).

## Environments (GCP)

| Env | GCP project | Trigger |
|---|---|---|
| staging | `thekedar-staging` | Push to `main` |
| prod | `thekedar-prod` | Manual `deploy-prod` workflow |

## One-time GCP setup

1. Create projects `thekedar-staging` and `thekedar-prod`
2. Enable APIs: Cloud Run, Artifact Registry, Secret Manager, Pub/Sub, Vertex AI
3. Bootstrap Terraform state bucket — see [infra/terraform/bootstrap/README.md](../infra/terraform/bootstrap/README.md)
4. Configure GitHub Actions secrets:
   - `GCP_WORKLOAD_IDENTITY_PROVIDER`
   - `GCP_SERVICE_ACCOUNT`

## Terraform (staging)

```bash
cd infra/terraform/environments/staging
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your project ID
terraform init
terraform plan
terraform apply
```

## Local Docker build

```bash
docker build -f infra/docker/webhook-ingress.Dockerfile -t thekedar-webhook-ingress:local .
docker run -p 8080:8080 thekedar-webhook-ingress:local
curl http://localhost:8080/health
```

## Webhook registration (M2)

| Platform | URL |
|---|---|
| WhatsApp | `https://api.thekedar.app/webhooks/whatsapp` |
| Slack | `https://api.thekedar.app/webhooks/slack` |

## Rollback

```bash
gcloud run services update-traffic webhook-ingress \
  --to-revisions=PREVIOUS_REVISION=100 \
  --region us-central1 \
  --project thekedar-staging
```
