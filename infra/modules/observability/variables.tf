variable "project_name" {
  type        = string
  description = "Short project identifier."
}

variable "environment" {
  type        = string
  description = "Deployment environment."
}

variable "log_retention_days" {
  type        = number
  description = "CloudWatch log group retention period in days."
  default     = 30
}

variable "auth_failure_alarm_threshold" {
  type        = number
  description = "Authentication failures per 5-minute window that trigger the alarm."
  default     = 10
}

variable "app_error_alarm_threshold" {
  type        = number
  description = "Application errors per 5-minute window that trigger the alarm."
  default     = 25
}
