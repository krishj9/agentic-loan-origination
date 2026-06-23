# ── Identity ───────────────────────────────────────────────────────────────────
variable "project_name" {
  type        = string
  description = "Short project identifier; prepended to all resource names."
  default     = "loan-origination"
}

variable "environment" {
  type        = string
  description = "Deployment environment label."
  default     = "demo"
}

variable "region" {
  type        = string
  description = "AWS region for all resources."
  default     = "us-east-1"
}

# ── Networking ─────────────────────────────────────────────────────────────────
variable "vpc_cidr" {
  type        = string
  description = "CIDR block for the VPC."
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  type        = list(string)
  description = "CIDRs for public subnets (one per AZ)."
  default     = ["10.0.0.0/24", "10.0.1.0/24"]
}

variable "private_app_subnet_cidrs" {
  type        = list(string)
  description = "CIDRs for private application subnets (one per AZ)."
  default     = ["10.0.10.0/24", "10.0.11.0/24"]
}

variable "private_data_subnet_cidrs" {
  type        = list(string)
  description = "CIDRs for private data / integration subnets (one per AZ)."
  default     = ["10.0.20.0/24", "10.0.21.0/24"]
}

variable "single_nat_gateway" {
  type        = bool
  description = "Use one NAT gateway (cost-optimised for demo) vs one per AZ (HA)."
  default     = true
}

variable "allowed_ingress_cidrs" {
  type        = list(string)
  description = "CIDRs allowed to reach the ALB. Default: open to internet."
  default     = ["0.0.0.0/0"]
}

variable "app_port" {
  type        = number
  description = "Port on which the backend application listens."
  default     = 8000
}

variable "mock_service_port" {
  type        = number
  description = "Port on which mock service backends listen."
  default     = 8080
}

# ── TLS / Edge ─────────────────────────────────────────────────────────────────
variable "domain_name" {
  type        = string
  description = "FQDN for the ACM certificate and ALB (e.g. demo.yourdomain.com)."
}

variable "route53_zone_id" {
  type        = string
  description = "Route53 hosted zone ID for automatic DNS validation. Leave empty for manual."
  default     = ""
}

# ── Storage lifecycle ──────────────────────────────────────────────────────────
variable "incoming_retention_days" {
  type        = number
  description = "Days before incoming/ objects are deleted."
  default     = 30
}

variable "extracted_retention_days" {
  type        = number
  description = "Days before extracted/ objects are deleted."
  default     = 60
}

variable "access_log_retention_days" {
  type        = number
  description = "Days before S3 access logs are deleted."
  default     = 90
}

variable "cors_allowed_origins" {
  type        = list(string)
  description = "Origins allowed for presigned PUT uploads (CORS). Add the deployed frontend URL."
  default     = ["http://localhost:5173"]
}

# ── Auth / Cognito ─────────────────────────────────────────────────────────────
variable "cognito_callback_urls" {
  type        = list(string)
  description = "OAuth2 redirect URIs after successful Cognito authentication."
  default     = ["http://localhost:5173"]
}

variable "cognito_logout_urls" {
  type        = list(string)
  description = "OAuth2 post-logout redirect URIs."
  default     = ["http://localhost:5173"]
}

variable "cognito_mfa_configuration" {
  type        = string
  description = "MFA policy for the Cognito user pool: OFF, OPTIONAL, or ON."
  default     = "OPTIONAL"
}

# ── Observability ──────────────────────────────────────────────────────────────
variable "log_retention_days" {
  type        = number
  description = "CloudWatch log group retention in days."
  default     = 30
}

variable "auth_failure_alarm_threshold" {
  type        = number
  description = "Auth failures per 5-min window before the alarm fires."
  default     = 10
}

variable "app_error_alarm_threshold" {
  type        = number
  description = "Application errors per 5-min window before the alarm fires."
  default     = 25
}

# ── AI / Bedrock ───────────────────────────────────────────────────────────────
variable "bedrock_model_id" {
  type        = string
  description = "Foundation model ID for the LangGraph supervisor and IAM policies."
  default     = "anthropic.claude-3-5-sonnet-20241022-v2:0"
}
