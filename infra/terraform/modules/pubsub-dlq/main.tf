variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "inbound_topic" {
  type    = string
  default = "thekedar.inbound.messages"
}

variable "dlq_topic" {
  type    = string
  default = "thekedar.inbound.dlq"
}

variable "subscription" {
  type    = string
  default = "thekedar.inbound.messages-worker"
}

variable "max_delivery_attempts" {
  type    = number
  default = 5
}

variable "ack_deadline_seconds" {
  type    = number
  default = 600
}

resource "google_pubsub_topic" "inbound" {
  name = var.inbound_topic
}

resource "google_pubsub_topic" "dlq" {
  name = var.dlq_topic
}

resource "google_pubsub_subscription" "worker" {
  name  = var.subscription
  topic = google_pubsub_topic.inbound.name

  ack_deadline_seconds = var.ack_deadline_seconds

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dlq.id
    max_delivery_attempts = var.max_delivery_attempts
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
}

resource "google_pubsub_subscription" "dlq_monitor" {
  name  = "${var.dlq_topic}-monitor"
  topic = google_pubsub_topic.dlq.name

  ack_deadline_seconds = 60
}

output "inbound_topic" {
  value = google_pubsub_topic.inbound.name
}

output "dlq_topic" {
  value = google_pubsub_topic.dlq.name
}

output "subscription" {
  value = google_pubsub_subscription.worker.name
}
