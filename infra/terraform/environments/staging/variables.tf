variable "project_id" {
  type        = string
  description = "GCP project ID"
}

variable "region" {
  type        = string
  default     = "us-central1"
  description = "GCP region"
}

variable "environment" {
  type        = string
  description = "Environment name (staging, prod)"
}

variable "webhook_ingress_image" {
  type        = string
  description = "Container image for webhook-ingress Cloud Run service"
}
