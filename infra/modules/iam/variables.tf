variable "project_name" {
  type        = string
  description = "Short project identifier."
}

variable "environment" {
  type        = string
  description = "Deployment environment."
}

variable "region" {
  type        = string
  description = "AWS region (used in ARN construction)."
}

variable "bucket_arn" {
  type        = string
  description = "ARN of the documents S3 bucket; used to scope S3 IAM statements."
}

variable "kms_key_arn" {
  type        = string
  description = "ARN of the KMS CMK for the documents bucket; used in KMS IAM statements."
}

variable "log_group_prefix" {
  type        = string
  description = "CloudWatch log group name prefix for all project log groups (e.g. /loan-origination/demo)."
}

variable "bedrock_model_id" {
  type        = string
  description = "Bedrock foundation model ID the runtime role is allowed to invoke."
  default     = "anthropic.claude-3-5-sonnet-20241022-v2:0"
}
