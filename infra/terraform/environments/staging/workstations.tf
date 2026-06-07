# infra/terraform/environments/staging/workstations.tf
# Google Cloud Workstations Infrastructure for Thekedar Cloud Development Environments

# 1. Enable APIs
resource "google_project_service" "workstations_api" {
  project = var.project_id
  service = "workstations.googleapis.com"
  disable_on_destroy = false
}

# 2. Workstation Network & Subnet Requirements
# Workstations typically require a cluster inside a VPC.
# Assumes VPC is already defined or default is used.
resource "google_workstations_workstation_cluster" "thekedar_cluster" {
  provider               = google
  project                = var.project_id
  workstation_cluster_id = "thekedar-workstation-cluster"
  location               = var.region
  display_name           = "Thekedar Workstation Cluster"

  # Use default VPC if not customized
  network    = "default"
  subnetwork = "default"

  depends_on = [google_project_service.workstations_api]
}

# 3. Workstation Configuration
resource "google_workstations_workstation_config" "thekedar_config" {
  provider               = google
  project                = var.project_id
  workstation_config_id  = "thekedar-workstation-config"
  workstation_cluster_id = google_workstations_workstation_cluster.thekedar_cluster.workstation_cluster_id
  location               = var.region
  display_name           = "Thekedar Workstation Config"

  # Disable public IP, use IAP tunnel instead for SSH
  container {
    image = "us-central1-docker.pkg.dev/cloud-workstations-images/prebuilt/code-oss:latest"
  }

  persistent_directories {
    mount_path = "/home"
    gce_pd {
      size_gb        = 50
      reclaim_policy = "DELETE"
    }
  }

  # Configurable idle timeout / auto-hibernation
  idle_timeout = "1800s" # 30 minutes
}

# 4. IAM Permissions for Orchestrator Service Account
# Ensure the Orchestrator Service Account can manage workstations and connect via SSH (IAP tunnel)
resource "google_project_iam_member" "orchestrator_workstations_admin" {
  project = var.project_id
  role    = "roles/workstations.admin"
  member  = "serviceAccount:thekedar-orchestrator@${var.project_id}.iam.gserviceaccount.com"
}

resource "google_project_iam_member" "orchestrator_iap_accessor" {
  project = var.project_id
  role    = "roles/iap.tunnelResourceAccessor"
  member  = "serviceAccount:thekedar-orchestrator@${var.project_id}.iam.gserviceaccount.com"
}

# 5. Cloud Scheduler Job for Active Hibernation Checks
# Triggers hibernation job to shut down idle workstations proactively
resource "google_cloud_scheduler_job" "hibernate_idle_workstations" {
  name        = "thekedar-workstation-hibernate"
  description = "Triggers proactive hibernation checks for idle workstations"
  schedule    = "0 * * * *" # Every hour
  region      = var.region
  project     = var.project_id

  http_target {
    http_method = "POST"
    uri         = "https://orchestrator.${var.project_id}.a.run.app/ops/hibernate"
    
    oidc_token {
      service_account_email = "thekedar-orchestrator@${var.project_id}.iam.gserviceaccount.com"
    }
  }
}
