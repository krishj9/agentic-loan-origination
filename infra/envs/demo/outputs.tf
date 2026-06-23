# ── Networking ─────────────────────────────────────────────────────────────────
output "vpc_id" {
  description = "VPC ID."
  value       = module.network.vpc_id
}

output "public_subnet_ids" {
  description = "Public subnet IDs."
  value       = module.network.public_subnet_ids
}

output "private_app_subnet_ids" {
  description = "Private application subnet IDs."
  value       = module.network.private_app_subnet_ids
}

# ── Load balancer ──────────────────────────────────────────────────────────────
output "alb_dns_name" {
  description = "ALB DNS name — use as API endpoint before custom domain is wired."
  value       = module.edge.alb_dns_name
}

output "alb_arn" {
  description = "ALB ARN."
  value       = module.edge.alb_arn
}

output "app_target_group_arn" {
  description = "ARN of the application target group (register ECS tasks here)."
  value       = module.edge.app_target_group_arn
}

# ── Auth ───────────────────────────────────────────────────────────────────────
output "cognito_user_pool_id" {
  description = "Cognito user pool ID — set as COGNITO_USER_POOL_ID in backend .env."
  value       = module.auth.user_pool_id
}

output "cognito_spa_client_id" {
  description = "Cognito SPA app client ID — set as VITE_COGNITO_CLIENT_ID in frontend .env."
  value       = module.auth.spa_client_id
}

output "cognito_hosted_ui_domain" {
  description = "Cognito hosted UI domain prefix."
  value       = module.auth.hosted_ui_domain
}

output "oidc_discovery_url" {
  description = "OIDC discovery URL for JWT validation."
  value       = module.auth.oidc_discovery_url
}

# ── Storage ────────────────────────────────────────────────────────────────────
output "documents_bucket_name" {
  description = "Documents S3 bucket name — set as S3_BUCKET_NAME in .env files."
  value       = module.storage.bucket_id
}

output "documents_kms_key_arn" {
  description = "KMS CMK ARN for the documents bucket."
  value       = module.storage.kms_key_arn
}

# ── IAM ────────────────────────────────────────────────────────────────────────
output "runtime_exec_role_arn" {
  description = "AgentCore Runtime execution role ARN."
  value       = module.iam.runtime_exec_role_arn
}

output "backend_role_arn" {
  description = "FastAPI backend task role ARN."
  value       = module.iam.backend_role_arn
}

# ── AgentCore ──────────────────────────────────────────────────────────────────
output "agentcore_runtime_arn" {
  description = "AgentCore Runtime ARN — set as AGENTCORE_RUNTIME_ARN in .env files."
  value       = module.agentcore.runtime_arn
}

output "agentcore_gateway_arn" {
  description = "AgentCore Gateway ARN — set as AGENTCORE_GATEWAY_ARN in .env files."
  value       = module.agentcore.gateway_arn
}

output "agentcore_gateway_endpoint_url" {
  description = "AgentCore Gateway endpoint URL."
  value       = module.agentcore.gateway_endpoint_url
}

output "agentcore_provisioning_status" {
  description = "AgentCore provisioning status (ok | skipped | error)."
  value       = module.agentcore.provisioning_status
}

# ── Observability ──────────────────────────────────────────────────────────────
output "app_log_group_name" {
  description = "Application CloudWatch log group name."
  value       = module.observability.app_log_group_name
}

output "auth_log_group_name" {
  description = "Authentication CloudWatch log group name."
  value       = module.observability.auth_log_group_name
}

output "alarms_sns_topic_arn" {
  description = "SNS topic ARN for alarm notifications."
  value       = module.observability.alarms_sns_topic_arn
}

output "dashboard_name" {
  description = "CloudWatch dashboard name."
  value       = module.observability.dashboard_name
}
