terraform {
  required_version = ">= 1.6"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.40"
    }
  }

  # Uncomment after bootstrap creates the state bucket:
  # backend "gcs" {
  #   bucket = "thekedar-terraform-state"
  #   prefix = "staging"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
