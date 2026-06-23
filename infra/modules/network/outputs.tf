output "vpc_id" {
  description = "ID of the VPC."
  value       = aws_vpc.main.id
}

output "vpc_cidr_block" {
  description = "CIDR block of the VPC."
  value       = aws_vpc.main.cidr_block
}

output "internet_gateway_id" {
  description = "ID of the Internet Gateway."
  value       = aws_internet_gateway.main.id
}

output "public_subnet_ids" {
  description = "IDs of the public subnets (one per AZ)."
  value       = aws_subnet.public[*].id
}

output "private_app_subnet_ids" {
  description = "IDs of the private application subnets (one per AZ)."
  value       = aws_subnet.private_app[*].id
}

output "private_data_subnet_ids" {
  description = "IDs of the private data / integration subnets (one per AZ)."
  value       = aws_subnet.private_data[*].id
}

output "private_route_table_ids" {
  description = "IDs of the private route tables (1 if single_nat, else one per AZ)."
  value       = aws_route_table.private[*].id
}

output "public_route_table_id" {
  description = "ID of the shared public route table."
  value       = aws_route_table.public.id
}

output "nat_gateway_ids" {
  description = "IDs of the NAT gateways."
  value       = aws_nat_gateway.main[*].id
}

output "availability_zones" {
  description = "AZ names used by this VPC (in subnet order)."
  value       = data.aws_availability_zones.available.names
}
