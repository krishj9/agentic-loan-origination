variable "project_name" {
  type        = string
  description = "Short project identifier."
}

variable "environment" {
  type        = string
  description = "Deployment environment."
}

variable "callback_urls" {
  type        = list(string)
  description = "Allowed OAuth2 redirect URIs after successful authentication."
  default     = ["http://localhost:5173"]
}

variable "logout_urls" {
  type        = list(string)
  description = "Allowed logout redirect URIs."
  default     = ["http://localhost:5173"]
}

variable "mfa_configuration" {
  type        = string
  description = "MFA requirement: OFF, OPTIONAL, or ON."
  default     = "OPTIONAL"

  validation {
    condition     = contains(["OFF", "OPTIONAL", "ON"], var.mfa_configuration)
    error_message = "mfa_configuration must be OFF, OPTIONAL, or ON."
  }
}
