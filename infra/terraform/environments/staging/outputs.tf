output "webhook_ingress_url" {
  description = "Cloud Run URL for webhook ingress"
  value       = module.webhook_ingress.service_url
}

output "artifact_registry_url" {
  description = "Docker repository URL"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.thekedar.name}"
}
