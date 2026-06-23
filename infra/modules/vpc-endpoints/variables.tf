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
  description = "AWS region; used to construct endpoint service names."
}

variable "vpc_id" {
  type        = string
  description = "ID of the VPC in which to create the endpoints."
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Subnet IDs for interface endpoint ENI placement (private-app subnets)."
}

variable "private_route_table_ids" {
  type        = list(string)
  description = "Private route table IDs associated with the S3 gateway endpoint."
}

variable "vpc_endpoint_sg_id" {
  type        = string
  description = "Security group ID to attach to interface endpoints (HTTPS-only from VPC CIDR)."
}
