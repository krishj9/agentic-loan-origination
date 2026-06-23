variable "project_name" {
  type        = string
  description = "Short project identifier."
}

variable "environment" {
  type        = string
  description = "Deployment environment."
}

variable "incoming_retention_days" {
  type        = number
  description = "Days after which objects under incoming/ are deleted."
  default     = 30
}

variable "extracted_retention_days" {
  type        = number
  description = "Days after which objects under extracted/ are deleted."
  default     = 60
}

variable "access_log_retention_days" {
  type        = number
  description = "Days after which S3 access logs are deleted."
  default     = 90
}

variable "cors_allowed_origins" {
  type        = list(string)
  description = "Origins allowed for presigned PUT uploads (CORS). Include the frontend origin."
  default     = ["http://localhost:5173"]
}
