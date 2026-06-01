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

variable "dlq_replay_url" {
  type        = string
  default     = "https://ops.example.com"
  description = "URL for DLQ replay job (Cloud Run ops endpoint)"
}

variable "approval_ttl_url" {
  type        = string
  default     = "https://worker.example.com"
  description = "URL for approval TTL expiry job"
}
