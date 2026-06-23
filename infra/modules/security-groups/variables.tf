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
  description = "ID of the VPC in which to create the security groups."
}

variable "vpc_cidr" {
  type        = string
  description = "CIDR block of the VPC; used to scope VPC endpoint ingress rules."
}

variable "allowed_ingress_cidrs" {
  type        = list(string)
  description = "CIDRs allowed to reach the ALB on ports 80 and 443."
  default     = ["0.0.0.0/0"]
}

variable "app_port" {
  type        = number
  description = "TCP port on which the application layer listens."
  default     = 8000
}

variable "mock_service_port" {
  type        = number
  description = "TCP port on which mock service backends listen."
  default     = 8080
}
