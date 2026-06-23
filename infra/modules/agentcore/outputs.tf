output "runtime_arn" {
  description = "ARN of the provisioned AgentCore Runtime (or placeholder if unavailable)."
  value       = data.external.agentcore.result["runtime_arn"]
}

output "runtime_id" {
  description = "Short ID of the AgentCore Runtime."
  value       = data.external.agentcore.result["runtime_id"]
}

output "gateway_arn" {
  description = "ARN of the provisioned AgentCore Gateway (or placeholder if unavailable)."
  value       = data.external.agentcore.result["gateway_arn"]
}

output "gateway_id" {
  description = "Short ID of the AgentCore Gateway."
  value       = data.external.agentcore.result["gateway_id"]
}

output "gateway_endpoint_url" {
  description = "Endpoint URL for the AgentCore Gateway (used by the backend to route tool calls)."
  value       = data.external.agentcore.result["gateway_endpoint_url"]
}

output "provisioning_status" {
  description = "Provisioning status reported by the boto3 script (ok | skipped | error)."
  value       = data.external.agentcore.result["status"]
}
