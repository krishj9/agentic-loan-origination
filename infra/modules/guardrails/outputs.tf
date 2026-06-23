output "guardrail_id" {
  description = "The ID of the Bedrock Guardrail"
  value       = aws_bedrock_guardrail.main.guardrail_id
}

output "guardrail_arn" {
  description = "The ARN of the Bedrock Guardrail"
  value       = aws_bedrock_guardrail.main.guardrail_arn
}

output "guardrail_version" {
  description = "The version of the Bedrock Guardrail"
  value       = aws_bedrock_guardrail_version.main.version
}
