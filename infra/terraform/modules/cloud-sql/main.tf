variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "instance_name" {
  type    = string
  default = "thekedar-sql"
}

variable "database_version" {
  type    = string
  default = "POSTGRES_15"
}

variable "tier" {
  type    = string
  default = "db-custom-2-7680"
}

resource "google_sql_database_instance" "thekedar" {
  name             = var.instance_name
  database_version = var.database_version
  region           = var.region
  project          = var.project_id

  settings {
    tier = var.tier

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      start_time                     = "03:00"
      transaction_log_retention_days = 7
      backup_retention_settings {
        retained_backups = 14
      }
    }

    ip_configuration {
      ipv4_enabled = true
    }
  }

  deletion_protection = true
}

output "connection_name" {
  value = google_sql_database_instance.thekedar.connection_name
}

output "instance_name" {
  value = google_sql_database_instance.thekedar.name
}
