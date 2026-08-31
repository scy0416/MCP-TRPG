locals {
  image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.repository_id}/server:${var.image_tag}"
}

resource "google_project_service" "required" {
  for_each = toset([
    "artifactregistry.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
  ])

  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "server" {
  location      = var.region
  repository_id = var.repository_id
  description   = "MCP-TRPG container images"
  format        = "DOCKER"

  depends_on = [google_project_service.required]
}

resource "google_service_account" "runtime" {
  account_id   = "${var.service_name}-runtime"
  display_name = "${var.service_name} Cloud Run runtime"
}

resource "google_secret_manager_secret" "supabase_publishable_key" {
  secret_id = "${var.service_name}-supabase-publishable-key"

  replication {
    auto {}
  }

  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_iam_member" "runtime_publishable_key" {
  secret_id = google_secret_manager_secret.supabase_publishable_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_cloud_run_v2_service" "server" {
  name                = var.service_name
  location            = var.region
  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.runtime.email

    scaling {
      min_instance_count = var.min_instance_count
      max_instance_count = var.max_instance_count
    }

    max_instance_request_concurrency = var.concurrency

    containers {
      image = local.image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      env {
        name  = "SUPABASE_URL"
        value = var.supabase_url
      }

      env {
        name  = "SUPABASE_AUTH_ISSUER"
        value = var.supabase_auth_issuer
      }

      env {
        name  = "SUPABASE_JWKS_URL"
        value = var.supabase_jwks_url
      }

      env {
        name  = "MCP_RESOURCE_URL"
        value = var.mcp_resource_url
      }

      env {
        name = "SUPABASE_PUBLISHABLE_KEY"

        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.supabase_publishable_key.secret_id
            version = "latest"
          }
        }
      }
    }

    timeout = "300s"
  }

  depends_on = [google_artifact_registry_repository.server]
}

# Cloud Run must receive the request so the application can enforce Supabase OAuth.
resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  name     = google_cloud_run_v2_service.server.name
  location = google_cloud_run_v2_service.server.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
