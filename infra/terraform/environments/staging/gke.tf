# Uncomment after GCP project and APIs are enabled (container.googleapis.com)
#
# module "gke_bifrost" {
#   source     = "../../modules/gke-bifrost"
#   project_id = var.project_id
#   region     = var.region
# }
#
# output "gke_cluster_name" {
#   value = module.gke_bifrost.cluster_name
# }
