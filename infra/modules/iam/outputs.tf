output "runtime_exec_role_arn" {
  description = "ARN of the AgentCore Runtime execution role."
  value       = aws_iam_role.runtime_exec.arn
}

output "runtime_exec_role_name" {
  description = "Name of the AgentCore Runtime execution role."
  value       = aws_iam_role.runtime_exec.name
}

output "backend_role_arn" {
  description = "ARN of the FastAPI backend task role."
  value       = aws_iam_role.backend.arn
}

output "backend_role_name" {
  description = "Name of the FastAPI backend task role."
  value       = aws_iam_role.backend.name
}

output "gateway_tool_role_arn" {
  description = "ARN of the AgentCore Gateway tool execution role."
  value       = aws_iam_role.gateway_tool.arn
}

output "gateway_tool_role_name" {
  description = "Name of the AgentCore Gateway tool execution role."
  value       = aws_iam_role.gateway_tool.name
}
