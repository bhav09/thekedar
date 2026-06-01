variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "instance_name" {
  type    = string
  default = "thekedar-redis"
}

variable "memory_gb" {
  type    = number
  default = 1
}

variable "tier" {
  description = "STANDARD_HA for production HA"
  type        = string
  default     = "STANDARD_HA"
}

resource "google_redis_instance" "thekedar" {
  name           = var.instance_name
  tier           = var.tier
  memory_size_gb = var.memory_gb
  region         = var.region
  project        = var.project_id

  redis_version     = "REDIS_7_0"
  display_name      = "Thekedar Redis"
  authorized_network = "projects/${var.project_id}/global/networks/default"
}

output "host" {
  value = google_redis_instance.thekedar.host
}

output "port" {
  value = google_redis_instance.thekedar.port
}
