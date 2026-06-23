# Demo environment root composition.
# Wires all Phase-1 modules together.

locals {
  log_group_prefix = "/${var.project_name}/${var.environment}"
}

# ── Networking ─────────────────────────────────────────────────────────────────
module "network" {
  source = "../../modules/network"

  project_name              = var.project_name
  environment               = var.environment
  vpc_cidr                  = var.vpc_cidr
  public_subnet_cidrs       = var.public_subnet_cidrs
  private_app_subnet_cidrs  = var.private_app_subnet_cidrs
  private_data_subnet_cidrs = var.private_data_subnet_cidrs
  single_nat_gateway        = var.single_nat_gateway
}

# ── Security groups ────────────────────────────────────────────────────────────
module "security_groups" {
  source = "../../modules/security-groups"

  project_name          = var.project_name
  environment           = var.environment
  vpc_id                = module.network.vpc_id
  vpc_cidr              = module.network.vpc_cidr_block
  allowed_ingress_cidrs = var.allowed_ingress_cidrs
  app_port              = var.app_port
  mock_service_port     = var.mock_service_port
}

# ── VPC endpoints ──────────────────────────────────────────────────────────────
module "vpc_endpoints" {
  source = "../../modules/vpc-endpoints"

  project_name            = var.project_name
  environment             = var.environment
  region                  = var.region
  vpc_id                  = module.network.vpc_id
  private_subnet_ids      = module.network.private_app_subnet_ids
  private_route_table_ids = module.network.private_route_table_ids
  vpc_endpoint_sg_id      = module.security_groups.vpc_endpoint_sg_id
}

# ── Observability ──────────────────────────────────────────────────────────────
# Created before IAM so the log group prefix is available.
module "observability" {
  source = "../../modules/observability"

  project_name                 = var.project_name
  environment                  = var.environment
  log_retention_days           = var.log_retention_days
  auth_failure_alarm_threshold = var.auth_failure_alarm_threshold
  app_error_alarm_threshold    = var.app_error_alarm_threshold
}

# ── Storage ────────────────────────────────────────────────────────────────────
module "storage" {
  source = "../../modules/storage"

  project_name              = var.project_name
  environment               = var.environment
  incoming_retention_days   = var.incoming_retention_days
  extracted_retention_days  = var.extracted_retention_days
  access_log_retention_days = var.access_log_retention_days
  cors_allowed_origins      = var.cors_allowed_origins
}

# ── IAM ────────────────────────────────────────────────────────────────────────
module "iam" {
  source = "../../modules/iam"

  project_name     = var.project_name
  environment      = var.environment
  region           = var.region
  bucket_arn       = module.storage.bucket_arn
  kms_key_arn      = module.storage.kms_key_arn
  log_group_prefix = local.log_group_prefix
  bedrock_model_id = var.bedrock_model_id
}

# ── Edge (ALB + TLS) ───────────────────────────────────────────────────────────
module "edge" {
  source = "../../modules/edge"

  project_name       = var.project_name
  environment        = var.environment
  vpc_id             = module.network.vpc_id
  public_subnet_ids  = module.network.public_subnet_ids
  alb_sg_id          = module.security_groups.alb_sg_id
  domain_name        = var.domain_name
  route53_zone_id    = var.route53_zone_id
  app_port           = var.app_port
  access_logs_bucket = module.storage.access_logs_bucket_id
}

# ── Cognito auth ───────────────────────────────────────────────────────────────
module "auth" {
  source = "../../modules/auth"

  project_name      = var.project_name
  environment       = var.environment
  callback_urls     = var.cognito_callback_urls
  logout_urls       = var.cognito_logout_urls
  mfa_configuration = var.cognito_mfa_configuration
}

# ── AgentCore Runtime + Gateway ────────────────────────────────────────────────
module "agentcore" {
  source = "../../modules/agentcore"

  project_name     = var.project_name
  environment      = var.environment
  region           = var.region
  runtime_role_arn = module.iam.runtime_exec_role_arn
  gateway_role_arn = module.iam.gateway_tool_role_arn
  bedrock_model_id = var.bedrock_model_id
}

# ── Bedrock Guardrails ─────────────────────────────────────────────────────────
module "guardrails" {
  source = "../../modules/guardrails"

  project_name = var.project_name
  environment  = var.environment
}
