output "s3_endpoint_id" {
  description = "ID of the S3 gateway endpoint."
  value       = aws_vpc_endpoint.s3.id
}

output "cloudwatch_logs_endpoint_id" {
  description = "ID of the CloudWatch Logs interface endpoint."
  value       = aws_vpc_endpoint.cloudwatch_logs.id
}

output "bedrock_runtime_endpoint_id" {
  description = "ID of the Bedrock Runtime interface endpoint."
  value       = aws_vpc_endpoint.bedrock_runtime.id
}

output "ssm_endpoint_id" {
  description = "ID of the SSM interface endpoint."
  value       = aws_vpc_endpoint.ssm.id
}
