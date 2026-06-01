# Bootstrap: create GCS bucket for Terraform state (run once manually)
#
#   gcloud storage buckets create gs://thekedar-terraform-state \
#     --project=THEKEDAR_ORG_PROJECT \
#     --location=us-central1 \
#     --uniform-bucket-level-access
#
# Enable versioning:
#   gcloud storage buckets update gs://thekedar-terraform-state --versioning
