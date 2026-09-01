variable "project_id" {
  description = "GCP project that owns the deployment resources."
  type        = string
}

variable "region" {
  description = "Cloud Run and Artifact Registry region."
  type        = string
  default     = "asia-northeast3"
}

variable "service_name" {
  description = "Cloud Run service name."
  type        = string
  default     = "trpg-mcp"
}

variable "repository_id" {
  description = "Artifact Registry Docker repository ID."
  type        = string
  default     = "trpg-mcp"
}

variable "image_tag" {
  description = "Immutable image tag to deploy."
  type        = string
  default     = "latest"
}

variable "supabase_url" {
  description = "Hosted Supabase project URL."
  type        = string
}

variable "supabase_auth_issuer" {
  description = "Supabase OAuth issuer URL."
  type        = string
}

variable "supabase_jwks_url" {
  description = "Supabase JWKS endpoint used for JWT verification."
  type        = string
}

variable "mcp_resource_url" {
  description = "Public MCP resource URL ending in /mcp."
  type        = string
}

variable "min_instance_count" {
  description = "Warm Cloud Run instances for initial production latency."
  type        = number
  default     = 1
}

variable "max_instance_count" {
  description = "Maximum Cloud Run instances."
  type        = number
  default     = 5
}

variable "concurrency" {
  description = "Maximum concurrent requests per Cloud Run instance."
  type        = number
  default     = 30
}
