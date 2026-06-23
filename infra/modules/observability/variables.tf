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

# ── P6-T10 additions ──────────────────────────────────────────────────────────

variable "drift_alarm_threshold" {
  type        = number
  description = "Number of drift events per 1-hour window that trigger the drift alarm."
  default     = 1
}

variable "accuracy_alarm_threshold_pct" {
  type        = number
  description = "Minimum acceptable golden-case accuracy percentage (0–100). Alarm fires when accuracy drops below this value."
  default     = 90
}
