resource "google_artifact_registry_repository" "thekedar" {
  location      = var.region
  repository_id = "thekedar"
  description   = "Thekedar container images"
  format        = "DOCKER"
}

module "webhook_ingress" {
  source = "../../modules/cloud-run"

  project_id   = var.project_id
  region       = var.region
  service_name = "webhook-ingress"
  image        = var.webhook_ingress_image
  environment  = var.environment

  env_vars = {
    THEKEDAR_ENVIRONMENT         = var.environment
    THEKEDAR_SERVICE_NAME        = "webhook-ingress"
    THEKEDAR_STRICT_INTEGRATIONS = "true"
    THEKEDAR_VALIDATE_ON_STARTUP = "true"
  }

  allow_unauthenticated = true
}

module "inbound_pubsub" {
  source = "../../modules/pubsub-dlq"

  project_id = var.project_id
  region     = var.region
}

module "memorystore" {
  source = "../../modules/memorystore"

  project_id = var.project_id
  region     = var.region
}

module "cloud_sql" {
  source = "../../modules/cloud-sql"

  project_id = var.project_id
  region     = var.region
}

resource "google_cloud_scheduler_job" "dlq_replay" {
  name        = "thekedar-dlq-replay"
  description = "Replay DLQ messages every 5 minutes"
  schedule    = "*/5 * * * *"
  region      = var.region
  project     = var.project_id

  http_target {
    http_method = "POST"
    uri         = "${var.dlq_replay_url}/ops/replay-dlq"
  }
}

resource "google_cloud_scheduler_job" "approval_ttl" {
  name        = "thekedar-approval-ttl"
  description = "Expire stale approvals"
  schedule    = "0 * * * *"
  region      = var.region
  project     = var.project_id

  http_target {
    http_method = "POST"
    uri         = "${var.approval_ttl_url}/internal/expire-approvals"
  }
}
