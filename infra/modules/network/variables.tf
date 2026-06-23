variable "project_name" {
  type        = string
  description = "Short project identifier; prepended to all resource names."
}

variable "environment" {
  type        = string
  description = "Deployment environment (e.g. demo, staging, prod)."
}

variable "vpc_cidr" {
  type        = string
  description = "CIDR block for the VPC."
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  type        = list(string)
  description = "CIDR blocks for public subnets, one per AZ."
  default     = ["10.0.0.0/24", "10.0.1.0/24"]
}

variable "private_app_subnet_cidrs" {
  type        = list(string)
  description = "CIDR blocks for private application subnets, one per AZ."
  default     = ["10.0.10.0/24", "10.0.11.0/24"]
}

variable "private_data_subnet_cidrs" {
  type        = list(string)
  description = "CIDR blocks for private data / integration subnets, one per AZ."
  default     = ["10.0.20.0/24", "10.0.21.0/24"]
}

variable "single_nat_gateway" {
  type        = bool
  description = "Use a single shared NAT gateway (cost-optimised for demo). Set false for per-AZ HA."
  default     = true
}
