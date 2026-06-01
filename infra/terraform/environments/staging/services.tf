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
    THEKEDAR_ENVIRONMENT  = var.environment
    THEKEDAR_SERVICE_NAME = "webhook-ingress"
  }

  allow_unauthenticated = true # Public webhook ingress behind LB in M2
}
