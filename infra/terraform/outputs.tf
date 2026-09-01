output "cloud_run_uri" {
  description = "Deployed Cloud Run service URI."
  value       = google_cloud_run_v2_service.server.uri
}

output "artifact_registry_repository" {
  description = "Artifact Registry repository resource name."
  value       = google_artifact_registry_repository.server.name
}

output "runtime_service_account" {
  description = "Cloud Run runtime service account email."
  value       = google_service_account.runtime.email
}

output "publishable_key_secret_id" {
  description = "Secret Manager ID whose value must be provisioned out of band."
  value       = google_secret_manager_secret.supabase_publishable_key.secret_id
}
