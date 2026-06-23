variable "project_name" {
  type        = string
  description = "Short name for the project; used as a prefix in all resource names."
  default     = "loan-origination"
}

variable "environment" {
  type        = string
  description = "Environment label (e.g. demo, staging, prod)."
  default     = "demo"
}

variable "region" {
  type        = string
  description = "AWS region where the state bucket is created."
  default     = "us-east-1"
}

variable "state_bucket_name" {
  type        = string
  description = "Globally unique S3 bucket name for Terraform state storage."

  validation {
    condition     = length(var.state_bucket_name) >= 3 && length(var.state_bucket_name) <= 63
    error_message = "S3 bucket names must be between 3 and 63 characters."
  }
}

variable "lock_table_name" {
  type        = string
  description = "DynamoDB table name used for Terraform state locking."
  default     = "loan-origination-tf-lock"
}
