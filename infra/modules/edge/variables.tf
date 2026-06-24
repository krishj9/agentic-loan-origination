variable "project_name" {
  type        = string
  description = "Short project identifier."
}

variable "environment" {
  type        = string
  description = "Deployment environment."
}

variable "vpc_id" {
  type        = string
  description = "ID of the VPC."
}

variable "public_subnet_ids" {
  type        = list(string)
  description = "Public subnet IDs for ALB placement (one per AZ)."
}

variable "alb_sg_id" {
  type        = string
  description = "Security group ID to attach to the ALB."
}

variable "enable_ssl" {
  type        = bool
  description = "Enable HTTPS/TLS via an ACM certificate. When false the ALB serves plain HTTP on port 80 and no certificate is created."
  default     = false
}

variable "domain_name" {
  type        = string
  description = "FQDN for the ACM certificate and optional Route53 record (e.g. demo.example.com). Required when enable_ssl = true."
  default     = ""
}

variable "subject_alternative_names" {
  type        = list(string)
  description = "Additional domain names to add to the ACM certificate's SAN list."
  default     = []
}

variable "route53_zone_id" {
  type        = string
  description = "Route53 hosted zone ID for automatic DNS validation and ALB alias record. Leave empty for manual DNS validation."
  default     = ""
}

variable "app_port" {
  type        = number
  description = "Port on which the backend application listens."
  default     = 8000
}

variable "health_check_path" {
  type        = string
  description = "ALB health check path."
  default     = "/health"
}

variable "access_logs_bucket" {
  type        = string
  description = "S3 bucket for ALB access logs. Leave empty to disable access logging."
  default     = ""
}
