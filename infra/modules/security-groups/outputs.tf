output "alb_sg_id" {
  description = "Security group ID for the Application Load Balancer."
  value       = aws_security_group.alb.id
}

output "app_sg_id" {
  description = "Security group ID for the application tier."
  value       = aws_security_group.app.id
}

output "mock_service_sg_id" {
  description = "Security group ID for the mock service backends."
  value       = aws_security_group.mock_service.id
}

output "vpc_endpoint_sg_id" {
  description = "Security group ID for interface VPC endpoints."
  value       = aws_security_group.vpc_endpoint.id
}
